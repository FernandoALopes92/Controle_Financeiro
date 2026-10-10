"""Regras de negócio de transferências entre contas.

Extraído de app/routes/transferencias.py para separar a lógica de negócio da
camada de view (Flask). A view só deve: validar/converter o formulário,
chamar este service, e traduzir o resultado (ou exceção) em flash/redirect.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from app.models import Conta, Movimentacao, Transferencia, db


# ---------------------------------------------------------------------------
# Exceções de domínio (a view traduz em flash/redirect)
# ---------------------------------------------------------------------------
class TransferenciaServiceError(Exception):
    """Erro genérico de regra de negócio ligado a transferências."""


class ContasInvalidasError(TransferenciaServiceError):
    pass


class ContasIguaisError(TransferenciaServiceError):
    pass


class ContaInativaError(TransferenciaServiceError):
    pass

class ValorTransferenciaInvalidoError(TransferenciaServiceError):
    pass

class SaldoInsuficienteError(TransferenciaServiceError):
    def __init__(self, mensagem: str, saldo_disponivel: Decimal):
        self.saldo_disponivel = saldo_disponivel
        super().__init__(mensagem)


# ---------------------------------------------------------------------------
# Utilitários internos
# ---------------------------------------------------------------------------
def _validar_valor_transferencia(valor: Decimal) -> None:
    if not isinstance(valor, Decimal) or not valor.is_finite() or valor <= Decimal("0"):
        raise ValorTransferenciaInvalidoError(
            "O valor da transferência deve ser maior que zero."
        )
    

def _apagar_movimentacoes_da_transferencia(
    transferencia: Transferencia,
) -> None:
    """Remove somente as movimentações vinculadas à transferência."""
    movimentacoes = Movimentacao.query.filter_by(
        transferencia_id=transferencia.id
    ).all()

    for mov in movimentacoes:
        db.session.delete(mov)



def _criar_movimentacoes_espelho(
    *, transferencia_id: int, conta_origem: Conta, conta_destino: Conta, valor: Decimal, data, usuario_id: int, familia_id: int
) -> None:
    db.session.add(Movimentacao(
        transferencia_id=transferencia_id,
        usuario_id=usuario_id,
        familia_id=familia_id,
        conta_id=conta_origem.id,
        categoria_id=None,
        tipo="transferencia",
        valor=valor,
        descricao=f"Saída - Transferência para {conta_destino.nome}",
        data=data,
        pago=None,
    ))
    db.session.add(Movimentacao(
        transferencia_id=transferencia_id,
        usuario_id=usuario_id,
        familia_id=familia_id,
        conta_id=conta_destino.id,
        categoria_id=None,
        tipo="transferencia",
        valor=valor,
        descricao=f"Entrada - Transferência de {conta_origem.nome}",
        data=data,
        pago=None,
    ))


# ---------------------------------------------------------------------------
# Criar transferência
# ---------------------------------------------------------------------------
@dataclass
class NovaTransferenciaInput:
    origem_id: int
    destino_id: int
    valor: Decimal
    data: date
    descricao: Optional[str]


def criar_transferencia(dados: NovaTransferenciaInput, *, usuario_id: int, familia_id: int) -> str:
    _validar_valor_transferencia(dados.valor)

    if dados.origem_id == dados.destino_id:
        raise ContasIguaisError("A conta de origem e destino devem ser diferentes.")

    conta_origem = Conta.query.filter_by(id=dados.origem_id, familia_id=familia_id).first()
    conta_destino = Conta.query.filter_by(id=dados.destino_id, familia_id=familia_id).first()
    if not conta_origem or not conta_destino:
        raise ContasInvalidasError("Uma ou ambas as contas são inválidas ou não pertencem à sua família.")

    if not conta_origem.status or not conta_destino.status:
        raise ContaInativaError("Erro: Não é possível realizar transferências envolvendo contas inativas.")

    if conta_origem.saldo_atual is None or conta_origem.saldo_atual < dados.valor:
        raise SaldoInsuficienteError(
            "Saldo insuficiente na conta de origem.", conta_origem.saldo_atual or Decimal("0.00")
        )

    conta_origem.saldo_atual -= dados.valor
    conta_destino.saldo_atual += dados.valor

    transferencia = Transferencia(
        usuario_id=usuario_id,
        familia_id=familia_id,
        conta_origem_id=conta_origem.id,
        conta_destino_id=conta_destino.id,
        valor=dados.valor,
        data_transferencia=dados.data,
        observacoes=dados.descricao,
    )

    db.session.add(transferencia)
    db.session.flush()

    _criar_movimentacoes_espelho(
        transferencia_id=transferencia.id, conta_origem=conta_origem, conta_destino=conta_destino, 
        valor=dados.valor, data=dados.data, usuario_id=usuario_id, familia_id=familia_id,
    )

    db.session.commit()
    return "Transferência realizada com sucesso!"


# ---------------------------------------------------------------------------
# Excluir transferência
# ---------------------------------------------------------------------------
def excluir_transferencia(transferencia: Transferencia) -> None:
    if not transferencia.conta_origem.status or not transferencia.conta_destino.status:
        raise ContaInativaError(
            "Erro: Esta transação envolve uma conta inativa. Reative a conta primeiro para fazer alterações."
        )

    # Estorna os saldos
    transferencia.conta_origem.saldo_atual += transferencia.valor
    transferencia.conta_destino.saldo_atual -= transferencia.valor

    _apagar_movimentacoes_da_transferencia(transferencia)

    db.session.delete(transferencia)
    db.session.commit()


# ---------------------------------------------------------------------------
# Editar transferência
# ---------------------------------------------------------------------------
@dataclass
class EditarTransferenciaInput:
    origem_id: int
    destino_id: int
    valor: Decimal
    data: date
    descricao: Optional[str]


def atualizar_transferencia(
    transferencia: Transferencia, dados: EditarTransferenciaInput, *, usuario_id: int, familia_id: int
) -> str:
    if not transferencia.conta_origem.status or not transferencia.conta_destino.status:
        raise ContaInativaError(
            "Erro: Esta transação envolve uma conta inativa. Reative a conta primeiro para fazer alterações."
        )

    _validar_valor_transferencia(dados.valor)
    
    if dados.origem_id == dados.destino_id:
        raise ContasIguaisError("A conta de origem e destino devem ser diferentes.")

    conta_origem = Conta.query.filter_by(id=dados.origem_id, status=True, familia_id=familia_id).first()
    conta_destino = Conta.query.filter_by(id=dados.destino_id, status=True, familia_id=familia_id).first()
    if not conta_origem or not conta_destino:
        raise ContasInvalidasError("Conta de origem ou destino não encontrada ou inativa.")

    # Saldo virtual: se a conta de origem continua a mesma, projeta o estorno antes de validar
    saldo_projetado = conta_origem.saldo_atual
    if conta_origem.id == transferencia.conta_origem_id:
        saldo_projetado += transferencia.valor

    if saldo_projetado is None or saldo_projetado < dados.valor:
        raise SaldoInsuficienteError(
            f"Saldo insuficiente. O saldo disponível (considerando o estorno) é R$ {saldo_projetado:.2f}.",
            saldo_projetado or Decimal("0.00"),
        )

    # Desfaz o efeito antigo (usando as contas originais gravadas na transferência)
    transferencia.conta_origem.saldo_atual += transferencia.valor
    transferencia.conta_destino.saldo_atual -= transferencia.valor

    # Aplica o efeito novo
    conta_origem.saldo_atual -= dados.valor
    conta_destino.saldo_atual += dados.valor

    _apagar_movimentacoes_da_transferencia(transferencia)

    transferencia.conta_origem_id = conta_origem.id
    transferencia.conta_destino_id = conta_destino.id
    transferencia.valor = dados.valor
    transferencia.data_transferencia = dados.data
    transferencia.observacoes = dados.descricao

    _criar_movimentacoes_espelho(
        transferencia_id=transferencia.id, conta_origem=conta_origem, conta_destino=conta_destino, 
        valor=dados.valor, data=dados.data, usuario_id=usuario_id, familia_id=familia_id,
    )

    db.session.commit()
    return "Transferência atualizada com sucesso!"