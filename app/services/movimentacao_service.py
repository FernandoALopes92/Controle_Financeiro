"""Regras de negócio de movimentações de conta (entradas e saídas).

Extraído de app/routes/movimentacoes.py para separar a lógica de negócio da
camada de view (Flask). A view só deve: validar/converter o formulário,
chamar este service, e traduzir o resultado (ou exceção) em flash/redirect/json.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta

from app.models import Categoria, Conta, Movimentacao, db


# ---------------------------------------------------------------------------
# Exceções de domínio (a view traduz em flash/redirect/json)
# ---------------------------------------------------------------------------
class MovimentacaoServiceError(Exception):
    """Erro genérico de regra de negócio ligado a movimentações de conta."""


class CategoriaInvalidaError(MovimentacaoServiceError):
    pass


class ContaInvalidaError(MovimentacaoServiceError):
    pass


class ContaInativaError(MovimentacaoServiceError):
    pass


class MovimentacaoBloqueadaError(MovimentacaoServiceError):
    """Faturas e transferências não podem ser editadas/excluídas por aqui."""


# ---------------------------------------------------------------------------
# Utilitários internos
# ---------------------------------------------------------------------------
def _ajustar_saldo(conta: Conta, tipo: str, valor: Decimal, *, reverter: bool = False) -> None:
    """Aplica (ou desfaz, se reverter=True) o efeito de uma movimentação no saldo da conta."""
    fator = Decimal("-1") if reverter else Decimal("1")
    if tipo == "receita":
        conta.saldo_atual += fator * valor
    elif tipo == "despesa":
        conta.saldo_atual -= fator * valor


def verificar_bloqueio(descricao: str) -> None:
    """Impede editar/excluir movimentações que na verdade são faturas ou transferências
    (essas têm telas próprias, mexer nelas aqui bagunçaria o saldo calculado em outro lugar)."""
    if not descricao:
        return
    if descricao.startswith("Fatura "):
        raise MovimentacaoBloqueadaError("Faturas devem ser manipuladas no módulo de Cartões.")
    if descricao.startswith("Entrada - Transferência") or descricao.startswith("Saída - Transferência"):
        raise MovimentacaoBloqueadaError(
            "Transferências devem ser editadas ou excluídas na aba de Transferências."
        )


def decidir_pago(pago_raw: Optional[str], data_dt: datetime) -> bool:
    """Decide o estado inicial de 'pago' quando o formulário não informa isso
    explicitamente (ex: vindo do modal rápido): datas futuras nascem pendentes,
    hoje ou passado já nasce pago (debita o saldo na hora)."""
    if pago_raw is not None:
        return pago_raw.lower() == "true"
    hoje = datetime.today().date()
    return data_dt.date() <= hoje


# ---------------------------------------------------------------------------
# Criar movimentação
# ---------------------------------------------------------------------------
@dataclass
class NovaMovimentacaoInput:
    data: datetime
    descricao: str
    categoria_id: int
    valor: Decimal
    conta_id: int
    pago: bool
    replicar: str  # "3_meses" | outro valor = não replica


def criar_movimentacao(dados: NovaMovimentacaoInput, *, usuario_id: int, familia_id: int) -> str:
    categoria = Categoria.query.filter_by(id=dados.categoria_id, familia_id=familia_id).first()
    if not categoria or not categoria.tipo:
        raise CategoriaInvalidaError("Categoria inválida ou sem tipo.")
    tipo = categoria.tipo

    conta = Conta.query.filter_by(id=dados.conta_id, familia_id=familia_id).first()
    if not conta:
        raise ContaInvalidaError("Conta inválida.")
    if not conta.status:
        raise ContaInativaError("Erro: Não é possível registrar movimentações em uma conta inativa.")

    if dados.pago:
        _ajustar_saldo(conta, tipo, dados.valor)

    db.session.add(Movimentacao(
        usuario_id=usuario_id,
        familia_id=familia_id,
        data=dados.data,
        descricao=dados.descricao,
        categoria_id=dados.categoria_id,
        tipo=tipo,
        valor=dados.valor,
        conta_id=dados.conta_id,
        pago=dados.pago,
    ))

    if dados.replicar == "3_meses":
        for i in range(1, 4):
            data_futura = dados.data + relativedelta(months=i)
            db.session.add(Movimentacao(
                usuario_id=usuario_id,
                familia_id=familia_id,
                data=data_futura,
                descricao=dados.descricao,
                categoria_id=dados.categoria_id,
                tipo=tipo,
                valor=dados.valor,
                conta_id=dados.conta_id,
                pago=False,  # clones futuros nascem pendentes, não descontam saldo agora
            ))

    db.session.commit()
    return "Movimentação cadastrada com sucesso!"


# ---------------------------------------------------------------------------
# Editar movimentação
# ---------------------------------------------------------------------------
@dataclass
class EditarMovimentacaoInput:
    data: datetime
    descricao: str
    categoria_id: int
    valor: Decimal
    conta_id: int
    pago: bool


def atualizar_movimentacao(mov: Movimentacao, dados: EditarMovimentacaoInput, *, familia_id: int) -> str:
    if not mov.conta.status:
        raise ContaInativaError(
            "Erro: Esta conta está encerrada/inativa. Reative a conta nas configurações antes de alterar seu histórico."
        )
    verificar_bloqueio(mov.descricao)

    categoria = Categoria.query.filter_by(id=dados.categoria_id, familia_id=familia_id).first()
    if not categoria:
        raise CategoriaInvalidaError("Categoria inválida.")
    tipo_novo = categoria.tipo

    # 1. Estorna o efeito antigo no saldo, se a movimentação estava paga
    if mov.pago:
        conta_antiga = Conta.query.filter_by(id=mov.conta_id, familia_id=familia_id).first()
        if conta_antiga:
            _ajustar_saldo(conta_antiga, mov.tipo, mov.valor, reverter=True)

    conta_destino = Conta.query.filter_by(id=dados.conta_id, familia_id=familia_id).first()
    if not conta_destino:
        raise ContaInvalidaError("Conta inválida.")

    # 2. Atualiza os dados
    mov.data = dados.data
    mov.descricao = dados.descricao
    mov.categoria_id = dados.categoria_id
    mov.tipo = tipo_novo
    mov.valor = dados.valor
    mov.conta_id = dados.conta_id
    mov.pago = dados.pago

    # 3. Aplica o novo efeito no saldo, se a nova versão está paga
    if mov.pago:
        _ajustar_saldo(conta_destino, mov.tipo, mov.valor, reverter=False)

    db.session.commit()
    return "Movimentação atualizada com sucesso!"


# ---------------------------------------------------------------------------
# Excluir movimentação
# ---------------------------------------------------------------------------
def excluir_movimentacao(mov: Movimentacao, *, familia_id: int) -> None:
    if not mov.conta.status:
        raise ContaInativaError(
            "Erro: Esta conta está encerrada/inativa. Reative a conta nas configurações antes de alterar seu histórico."
        )
    verificar_bloqueio(mov.descricao)

    if mov.pago and mov.conta:
        _ajustar_saldo(mov.conta, mov.tipo, mov.valor, reverter=True)

    db.session.delete(mov)
    db.session.commit()