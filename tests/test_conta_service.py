"""Primeiro arquivo de teste do projeto — cobre o app/services/conta_service.py.

Como rodar (com o .venv já ativado, na raiz do projeto):
    pytest

Como rodar só este arquivo:
    pytest tests/test_conta_service.py -v
"""
from decimal import Decimal

import pytest

from app.services import conta_service


def test_atualizar_conta_ajusta_saldo_atual_pelo_delta(conta):
    """Se o saldo inicial mudar de 100 para 150 (uma diferença de +50),
    o saldo atual precisa subir na mesma proporção — essa é a regra que
    o conta_service.atualizar_conta() deveria garantir."""
    dados = conta_service.EditarContaInput(
        nome=conta.nome,
        data=conta.data,
        saldo_inicial=150.00,
        tipo=conta.tipo,
    )

    conta_service.atualizar_conta(conta, dados)

    assert float(conta.saldo_atual) == 150.00


def test_excluir_conta_com_saldo_bloqueia_exclusao(conta):
    """Uma conta que ainda tem saldo (diferente de zero) não pode ser
    excluída — o service deve recusar, levantando ContaComSaldoError."""
    with pytest.raises(conta_service.ContaComSaldoError):
        conta_service.excluir_conta(conta, familia_id=conta.familia_id)


def test_excluir_conta_zerada_sem_historico_apaga_de_verdade(db, conta):
    """Uma conta zerada e que nunca teve nenhuma movimentação lançada
    deve ser apagada de verdade (hard delete), não só inativada."""
    conta.saldo_atual = Decimal("0.00")
    db.session.commit()

    mensagem = conta_service.excluir_conta(conta, familia_id=conta.familia_id)

    assert "excluída permanentemente" in mensagem