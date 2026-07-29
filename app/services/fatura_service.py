"""Regras de negócio do ciclo de vida da fatura: fechar, reabrir, pagar e estornar.

Extraído de app/routes/faturas.py para separar a lógica de negócio da camada
de view (Flask). A view só deve: validar o formulário, chamar este service,
e traduzir o resultado (ou exceção) em flash/redirect.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from app.models import Conta, Fatura, MeioPagamento, Movimentacao, MovimentacaoCartao, PagamentoFatura, db
from app.services import cartao_service


# ---------------------------------------------------------------------------
# Exceções de domínio (a view traduz em flash/redirect)
# ---------------------------------------------------------------------------
class FaturaServiceError(Exception):
    """Erro genérico de regra de negócio ligado a faturas."""


class FaturaJaFechadaError(FaturaServiceError):
    pass


class FaturaJaAbertaError(FaturaServiceError):
    pass


class FaturaPrecisaEstarFechadaError(FaturaServiceError):
    pass


class FaturaSemSaldoError(FaturaServiceError):
    pass


class ContaInvalidaError(FaturaServiceError):
    pass


class SaldoInsuficienteError(FaturaServiceError):
    pass


class SemPagamentoParaEstornarError(FaturaServiceError):
    pass


# ---------------------------------------------------------------------------
# Utilitários internos
# ---------------------------------------------------------------------------
def _nome_fatura(fatura: Fatura) -> str:
    return f"Fatura {fatura.cartao.nome} {fatura.mes:02d}/{str(fatura.ano)[-2:]}"


def _mes_ano_seguinte(mes: int, ano: int) -> tuple[int, int]:
    return (1, ano + 1) if mes == 12 else (mes + 1, ano)


def _obter_ou_criar_fatura_seguinte(fatura: Fatura, familia_id: int) -> Fatura:
    """Busca (ou cria) a fatura do mês seguinte, para onde o saldo rotativo é transferido."""
    proximo_mes, proximo_ano = _mes_ano_seguinte(fatura.mes, fatura.ano)
    fatura_proxima = Fatura.query.filter_by(
        cartao_id=fatura.cartao_id, mes=proximo_mes, ano=proximo_ano, familia_id=familia_id
    ).first()
    if not fatura_proxima:
        cartao_ref = MeioPagamento.query.filter_by(id=fatura.cartao_id, familia_id=familia_id).first()
        dia_fech = min(cartao_ref.fechamento_dia, monthrange(proximo_ano, proximo_mes)[1])
        dia_venc = min(cartao_ref.vencimento_dia, monthrange(proximo_ano, proximo_mes)[1])
        fatura_proxima = Fatura(
            cartao_id=fatura.cartao_id,
            mes=proximo_mes,
            ano=proximo_ano,
            data_fechamento=date(proximo_ano, proximo_mes, dia_fech),
            data_vencimento=date(proximo_ano, proximo_mes, dia_venc),
            status="aberta",
            saldo=Decimal("0.00"),
            familia_id=familia_id,  # CORREÇÃO: faltava esse campo (causava erro ao rolar saldo pra próxima fatura)
        )
        db.session.add(fatura_proxima)
        db.session.flush()
    return fatura_proxima


# ---------------------------------------------------------------------------
# Fechar fatura
# ---------------------------------------------------------------------------
def fechar_fatura(fatura: Fatura, *, usuario_id: int, familia_id: int) -> str:
    if fatura.status != "aberta":
        raise FaturaJaFechadaError("Fatura já está fechada.")

    cartao_service.recalcular_saldo_fatura(fatura.id)
    db.session.refresh(fatura)

    if not fatura.saldo or fatura.saldo <= 0:
        db.session.delete(fatura)
        db.session.commit()
        return "Fatura zerada foi excluída automaticamente."

    fatura.status = "fechada"
    fatura.data_fechamento = date.today()

    nome_fatura_desc = _nome_fatura(fatura)
    mov_existente = Movimentacao.query.filter_by(
        descricao=nome_fatura_desc, pago=False, familia_id=familia_id
    ).first()

    if mov_existente:
        mov_existente.valor = fatura.saldo
        mov_existente.data = fatura.data_vencimento
    else:
        db.session.add(Movimentacao(
            usuario_id=usuario_id,
            familia_id=familia_id,
            data=fatura.data_vencimento,
            descricao=nome_fatura_desc,
            categoria_id=None,
            tipo="despesa",
            valor=fatura.saldo,
            conta_id=None,
            pago=False,
        ))

    db.session.commit()
    return "Fatura fechada e enviada para suas contas a pagar!"


# ---------------------------------------------------------------------------
# Reabrir fatura
# ---------------------------------------------------------------------------
def reabrir_fatura(fatura: Fatura, *, familia_id: int) -> str:
    if fatura.status != "fechada":
        raise FaturaJaAbertaError("A fatura já está aberta.")

    fatura.status = "aberta"
    nome_fatura_desc = _nome_fatura(fatura)
    mov_pendente = Movimentacao.query.filter_by(
        descricao=nome_fatura_desc, pago=False, familia_id=familia_id
    ).first()
    if mov_pendente:
        db.session.delete(mov_pendente)

    db.session.commit()
    return "Fatura reaberta com sucesso."


# ---------------------------------------------------------------------------
# Pagar fatura
# ---------------------------------------------------------------------------
@dataclass
class PagamentoFaturaInput:
    conta_id: int
    valor: Decimal
    data_pagamento: date


def pagar_fatura(fatura: Fatura, dados: PagamentoFaturaInput, *, usuario_id: int, familia_id: int) -> str:
    conta = Conta.query.filter_by(id=dados.conta_id, familia_id=familia_id).first()
    if not conta:
        raise ContaInvalidaError("Conta selecionada inválida.")

    if fatura.status != "fechada":
        raise FaturaPrecisaEstarFechadaError("A fatura precisa estar fechada para ser paga.")

    if not fatura.saldo or fatura.saldo <= 0:
        raise FaturaSemSaldoError("Fatura sem valor a pagar.")

    if conta.saldo_atual < dados.valor:
        raise SaldoInsuficienteError("Saldo insuficiente na conta selecionada.")

    pagamento = PagamentoFatura(
        usuario_id=usuario_id,
        familia_id=familia_id,
        conta_id=dados.conta_id,
        fatura_id=fatura.id,
        valor_pago=dados.valor,
        data_pagamento=dados.data_pagamento,
    )
    db.session.add(pagamento)
    db.session.flush()

    nome_fatura_desc = _nome_fatura(fatura)
    movimentacao = Movimentacao.query.filter_by(
        descricao=nome_fatura_desc, pago=False, familia_id=familia_id
    ).first()

    if movimentacao:
        movimentacao.data = dados.data_pagamento
        movimentacao.valor = dados.valor
        movimentacao.conta_id = dados.conta_id
        movimentacao.pago = True
        movimentacao.pagamento_fatura_id = pagamento.id
    else:
        db.session.add(Movimentacao(
            usuario_id=usuario_id,
            familia_id=familia_id,
            data=dados.data_pagamento,
            descricao=nome_fatura_desc,
            categoria_id=None,
            tipo="despesa",
            valor=dados.valor,
            conta_id=dados.conta_id,
            pago=True,
            pagamento_fatura_id=pagamento.id,
        ))

    conta.saldo_atual -= dados.valor
    saldo_restante = fatura.saldo - dados.valor

    if saldo_restante > 0:
        fatura_proxima = _obter_ou_criar_fatura_seguinte(fatura, familia_id)

        db.session.add(MovimentacaoCartao(
            descricao="Rotativo transferido p/ próxima fatura",
            valor=-saldo_restante,
            data_compra=dados.data_pagamento,
            cartao_id=fatura.cartao_id,
            categoria_id=None,
            usuario_id=usuario_id,
            familia_id=familia_id,
            numero_parcelas=1,
            parcela_atual=1,
            fatura_id=fatura.id,
        ))
        db.session.add(MovimentacaoCartao(
            descricao=f"Saldo pendente fatura {fatura.mes:02d}/{str(fatura.ano)[-2:]}",
            valor=saldo_restante,
            data_compra=dados.data_pagamento,
            cartao_id=fatura.cartao_id,
            categoria_id=None,
            usuario_id=usuario_id,
            familia_id=familia_id,
            numero_parcelas=1,
            parcela_atual=1,
            fatura_id=fatura_proxima.id,
        ))

        fatura.status = "pago_parcial"
        db.session.commit()
        cartao_service.recalcular_saldo_fatura(fatura.id)
        cartao_service.recalcular_saldo_fatura(fatura_proxima.id)
        return f"Pagamento parcial. R$ {saldo_restante:.2f} rolados para a fatura seguinte."

    fatura.status = "pago"
    db.session.commit()
    cartao_service.recalcular_saldo_fatura(fatura.id)
    return "Fatura paga com sucesso."


# ---------------------------------------------------------------------------
# Estornar pagamento
# ---------------------------------------------------------------------------
def estornar_pagamento(fatura: Fatura, *, familia_id: int, usuario_id: int) -> str:
    if fatura.status not in ("pago", "pago_parcial"):
        raise SemPagamentoParaEstornarError("Esta fatura não possui pagamentos para estornar.")

    pagamento = PagamentoFatura.query.filter_by(fatura_id=fatura.id, familia_id=familia_id).first()
    fatura_proxima: Optional[Fatura] = None
    status_anterior = fatura.status

    if pagamento:
        conta = Conta.query.filter_by(id=pagamento.conta_id, familia_id=familia_id).first()
        if conta:
            conta.saldo_atual += pagamento.valor_pago

        movimentacao = Movimentacao.query.filter_by(
            pagamento_fatura_id=pagamento.id, familia_id=familia_id
        ).first()
        if movimentacao:
            db.session.delete(movimentacao)

        if status_anterior == "pago_parcial":
            MovimentacaoCartao.query.filter_by(
                fatura_id=fatura.id,
                familia_id=familia_id,
                descricao="Rotativo transferido p/ próxima fatura",
            ).delete()

            proximo_mes, proximo_ano = _mes_ano_seguinte(fatura.mes, fatura.ano)
            fatura_proxima = Fatura.query.filter_by(
                cartao_id=fatura.cartao_id, mes=proximo_mes, ano=proximo_ano, familia_id=familia_id
            ).first()
            if fatura_proxima:
                MovimentacaoCartao.query.filter_by(
                    fatura_id=fatura_proxima.id,
                    familia_id=familia_id,
                    descricao=f"Saldo pendente fatura {fatura.mes:02d}/{str(fatura.ano)[-2:]}",
                ).delete()

        db.session.delete(pagamento)

    fatura.status = "fechada"
    db.session.commit()

    cartao_service.recalcular_saldo_fatura(fatura.id)
    if status_anterior == "pago_parcial" and fatura_proxima:
        cartao_service.recalcular_saldo_fatura(fatura_proxima.id)

    db.session.refresh(fatura)
    db.session.add(Movimentacao(
        usuario_id=usuario_id,
        familia_id=familia_id,
        data=fatura.data_vencimento,
        descricao=_nome_fatura(fatura),
        categoria_id=None,
        tipo="despesa",
        valor=fatura.saldo,
        conta_id=None,
        pago=False,
    ))
    db.session.commit()

    return "Pagamento estornado! O dinheiro voltou para a conta corrente e os saldos foram restaurados."