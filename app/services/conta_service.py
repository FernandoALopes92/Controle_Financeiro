"""Regras de negócio de contas: ajuste de saldo ao editar e decisão de
exclusão (apagar de vez vs. inativar) ao excluir.

Extraído de app/routes/contas.py para separar a lógica de negócio da
camada de view (Flask).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import Optional

from sqlalchemy import or_

from app.models import Conta, Movimentacao, PagamentoFatura, Transferencia, db


# ---------------------------------------------------------------------------
# Exceções de domínio (a view traduz em flash/redirect)
# ---------------------------------------------------------------------------
class ContaServiceError(Exception):
    """Erro genérico de regra de negócio ligado a contas."""


class ContaComSaldoError(ContaServiceError):
    """A conta ainda tem saldo diferente de zero, não pode ser encerrada."""


class ContaComPendenciaError(ContaServiceError):
    """A conta tem lançamentos pendentes (não pagos), não pode ser encerrada."""


# ---------------------------------------------------------------------------
# Editar conta
# ---------------------------------------------------------------------------
@dataclass
class EditarContaInput:
    nome: str
    data: Optional[date_type]
    saldo_inicial: float
    tipo: str
    logo_filename: Optional[str] = None


def atualizar_conta(conta: Conta, dados: EditarContaInput) -> str:
    # O saldo inicial pode ser corrigido a qualquer momento (ex: erro de digitação
    # no cadastro). Quando isso acontece, o saldo ATUAL precisa ser ajustado pela
    # mesma diferença (delta), para não perder o histórico de movimentações já
    # lançadas em cima do saldo inicial antigo.
    antigo_saldo_inicial = float(conta.saldo_inicial or 0)
    delta = dados.saldo_inicial - antigo_saldo_inicial

    conta.nome = dados.nome
    conta.data = dados.data
    conta.tipo = dados.tipo
    conta.saldo_inicial = dados.saldo_inicial
    conta.saldo_atual = float(conta.saldo_atual or 0) + delta

    if dados.logo_filename:
        conta.logo = dados.logo_filename

    db.session.commit()
    return "Conta atualizada com sucesso!"


# ---------------------------------------------------------------------------
# Excluir / reativar conta
# ---------------------------------------------------------------------------
def _conta_tem_historico(conta: Conta, familia_id: int) -> bool:
    """True se a conta já foi usada em algum lançamento, transferência ou
    pagamento de fatura (qualquer um deles impede apagar de verdade, pois
    deixaria registros apontando para uma conta que não existe mais)."""
    if Movimentacao.query.filter_by(conta_id=conta.id, familia_id=familia_id).first():
        return True
    if PagamentoFatura.query.filter_by(conta_id=conta.id, familia_id=familia_id).first():
        return True
    return (
        Transferencia.query.filter(
            Transferencia.familia_id == familia_id,
            or_(Transferencia.conta_origem_id == conta.id, Transferencia.conta_destino_id == conta.id),
        ).first()
        is not None
    )


def excluir_conta(conta: Conta, *, familia_id: int) -> str:
    # CONTA NUNCA USADA -> apaga de verdade, mesmo com saldo: sem nenhum
    # lançamento, o saldo é apenas o "saldo inicial" digitado no cadastro,
    # não há dinheiro a transferir nem histórico a preservar.
    if not _conta_tem_historico(conta, familia_id):
        db.session.delete(conta)
        db.session.commit()
        return "Conta excluída permanentemente do sistema!"

    # CONTA COM HISTÓRICO -> só pode ser inativada (soft delete), e para isso
    # precisa estar zerada e sem pendências.
    # REGRA 1: usa round(...) para não deixar dízimas de ponto flutuante
    # (ex: 0.00001) bloquearem o encerramento.
    if round(float(conta.saldo_atual), 2) != 0.00:
        raise ContaComSaldoError(
            f"A conta não pode ser encerrada. Transfira ou zere o saldo atual de "
            f"R$ {conta.saldo_atual:.2f} primeiro."
        )

    # REGRA 2: não pode ter lançamento pendente em aberto
    if Movimentacao.query.filter_by(conta_id=conta.id, familia_id=familia_id, pago=False).first():
        raise ContaComPendenciaError(
            "Existem lançamentos pendentes atrelados a esta conta. Resolva-os antes de encerrar."
        )

    conta.status = False
    db.session.commit()
    return "Conta inativada com sucesso! O histórico foi mantido e você pode reativá-la na lista de contas."


def reativar_conta(conta: Conta) -> str:
    if conta.status:
        return "A conta já está ativa."
    conta.status = True
    db.session.commit()
    return "Conta reativada com sucesso!"
