"""Regras de negócio de contas: ajuste de saldo ao editar e decisão de
exclusão (apagar de vez vs. inativar) ao excluir.

Extraído de app/routes/contas.py para separar a lógica de negócio da
camada de view (Flask).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import Optional

from app.models import Conta, Movimentacao, db


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
# Excluir conta
# ---------------------------------------------------------------------------
def excluir_conta(conta: Conta, *, familia_id: int) -> str:
    # REGRA 1: a conta precisa estar zerada. Usa round(...) para não deixar
    # dízimas de ponto flutuante (ex: 0.00001) bloquearem a exclusão.
    if round(float(conta.saldo_atual), 2) != 0.00:
        raise ContaComSaldoError(
            f"A conta não pode ser encerrada. Transfira ou zere o saldo atual de "
            f"R$ {conta.saldo_atual:.2f} primeiro."
        )

    movimentacoes_query = Movimentacao.query.filter_by(conta_id=conta.id, familia_id=familia_id)
    qtd_movimentacoes = movimentacoes_query.count()

    # REGRA 2: não pode ter lançamento pendente em aberto
    tem_pendencia = movimentacoes_query.filter_by(pago=False).first()
    if tem_pendencia:
        raise ContaComPendenciaError(
            "Existem lançamentos pendentes atrelados a esta conta. Resolva-os antes de encerrar."
        )

    if qtd_movimentacoes == 0:
        # Conta nunca foi usada -> apaga fisicamente do banco
        db.session.delete(conta)
        mensagem = "Conta excluída permanentemente do sistema!"
    else:
        # Conta tem histórico -> inativa (soft delete), preserva o passado
        conta.status = False
        mensagem = "Conta inativada com sucesso! O histórico financeiro foi mantido."

    db.session.commit()
    return mensagem