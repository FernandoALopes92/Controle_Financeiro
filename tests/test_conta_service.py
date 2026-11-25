"""Primeiro arquivo de teste do projeto — cobre o app/services/conta_service.py.

Como rodar (com o .venv já ativado, na raiz do projeto):
    pytest

Como rodar só este arquivo:
    pytest tests/test_conta_service.py -v
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models import Categoria, Conta, Movimentacao, Transferencia
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


def _lancar_movimentacao(db, conta, usuario, pago=True):
    """Cria uma movimentação qualquer na conta (para ela ter 'histórico')."""
    cat = Categoria(nome="Teste", tipo="despesa", familia_id=conta.familia_id)
    db.session.add(cat)
    db.session.flush()
    db.session.add(Movimentacao(
        usuario_id=usuario.id, familia_id=conta.familia_id, data=date(2026, 1, 5),
        descricao="Lançamento", categoria_id=cat.id, tipo="despesa",
        valor=Decimal("10.00"), conta_id=conta.id, pago=pago,
    ))
    db.session.commit()


def test_excluir_conta_com_saldo_e_historico_bloqueia(db, conta, usuario):
    """Conta COM movimentações e com saldo não pode ser encerrada."""
    _lancar_movimentacao(db, conta, usuario)

    with pytest.raises(conta_service.ContaComSaldoError):
        conta_service.excluir_conta(conta, familia_id=conta.familia_id)


def test_excluir_conta_com_saldo_mas_sem_movimentacoes_apaga_de_verdade(db, conta):
    """Conta nunca usada: o saldo é só o saldo inicial do cadastro, então
    pode ser apagada mesmo com saldo diferente de zero."""
    assert float(conta.saldo_atual) == 100.00
    conta_id = conta.id

    mensagem = conta_service.excluir_conta(conta, familia_id=conta.familia_id)

    assert "excluída permanentemente" in mensagem
    assert db.session.get(Conta, conta_id) is None


def test_excluir_conta_zerada_com_historico_apenas_inativa(db, conta, usuario):
    _lancar_movimentacao(db, conta, usuario, pago=True)
    conta.saldo_atual = Decimal("0.00")
    db.session.commit()

    mensagem = conta_service.excluir_conta(conta, familia_id=conta.familia_id)

    assert "inativada" in mensagem
    assert conta.status is False


def test_excluir_conta_com_pendencia_bloqueia_inativacao(db, conta, usuario):
    _lancar_movimentacao(db, conta, usuario, pago=False)
    conta.saldo_atual = Decimal("0.00")
    db.session.commit()

    with pytest.raises(conta_service.ContaComPendenciaError):
        conta_service.excluir_conta(conta, familia_id=conta.familia_id)


def test_conta_so_com_transferencia_nao_e_apagada(db, conta, conta_destino, usuario):
    """Conta que só aparece em transferência (zerada) tem histórico: deve
    ser inativada, nunca apagada (apagar quebraria a chave estrangeira)."""
    db.session.add(Transferencia(
        usuario_id=usuario.id, familia_id=conta.familia_id,
        conta_origem_id=conta.id, conta_destino_id=conta_destino.id,
        valor=Decimal("100.00"), data_transferencia=date(2026, 1, 6),
    ))
    conta.saldo_atual = Decimal("0.00")
    db.session.commit()

    mensagem = conta_service.excluir_conta(conta, familia_id=conta.familia_id)

    assert "inativada" in mensagem
    assert db.session.get(Conta, conta.id) is not None


def test_excluir_conta_zerada_sem_historico_apaga_de_verdade(db, conta):
    """Uma conta zerada e que nunca teve nenhuma movimentação lançada
    deve ser apagada de verdade (hard delete), não só inativada."""
    conta.saldo_atual = Decimal("0.00")
    db.session.commit()

    mensagem = conta_service.excluir_conta(conta, familia_id=conta.familia_id)

    assert "excluída permanentemente" in mensagem


def test_reativar_conta_inativa(db, conta):
    conta.status = False
    db.session.commit()

    mensagem = conta_service.reativar_conta(conta)

    assert "reativada" in mensagem
    assert conta.status is True
