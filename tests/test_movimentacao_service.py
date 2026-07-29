"""Testes do app/services/movimentacao_service.py.

Como rodar só este arquivo:
    pytest tests/test_movimentacao_service.py -v
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models import Movimentacao
from app.services import movimentacao_service as mov_service


def _nova_movimentacao_input(categoria_id, conta_id, valor="30.00", pago=True):
    return mov_service.NovaMovimentacaoInput(
        data=date(2026, 1, 5),
        descricao="Compra no mercado",
        categoria_id=categoria_id,
        valor=Decimal(valor),
        conta_id=conta_id,
        pago=pago,
        replicar=None,
    )


def test_criar_movimentacao_despesa_paga_debita_saldo(db, conta, categoria_despesa, usuario):
    dados = _nova_movimentacao_input(categoria_despesa.id, conta.id, valor="30.00", pago=True)

    mov_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=conta.familia_id)

    assert float(conta.saldo_atual) == 70.00  # 100 - 30


def test_criar_movimentacao_receita_paga_credita_saldo(db, conta, categoria_receita, usuario):
    dados = _nova_movimentacao_input(categoria_receita.id, conta.id, valor="50.00", pago=True)

    mov_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=conta.familia_id)

    assert float(conta.saldo_atual) == 150.00  # 100 + 50


def test_criar_movimentacao_nao_paga_nao_mexe_no_saldo(db, conta, categoria_despesa, usuario):
    dados = _nova_movimentacao_input(categoria_despesa.id, conta.id, valor="30.00", pago=False)

    mov_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=conta.familia_id)

    assert float(conta.saldo_atual) == 100.00  # nada muda, ainda não foi "paga"


def test_criar_movimentacao_em_conta_inativa_e_bloqueada(db, conta, categoria_despesa, usuario):
    conta.status = False
    db.session.commit()

    dados = _nova_movimentacao_input(categoria_despesa.id, conta.id)

    with pytest.raises(mov_service.ContaInativaError):
        mov_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=conta.familia_id)


def test_editar_movimentacao_estorna_valor_antigo_e_aplica_o_novo(db, conta, categoria_despesa, usuario):
    # Simula uma movimentação já lançada e paga (débito de 30 já aplicado no saldo)
    mov = Movimentacao(
        usuario_id=usuario.id, familia_id=conta.familia_id, data=date(2026, 1, 5),
        descricao="Compra mercado", categoria_id=categoria_despesa.id, tipo="despesa",
        valor=Decimal("30.00"), conta_id=conta.id, pago=True,
    )
    conta.saldo_atual -= Decimal("30.00")
    db.session.add(mov)
    db.session.commit()
    assert float(conta.saldo_atual) == 70.00

    # Edita o valor de 30 para 50 (mesma conta, continua paga)
    dados = mov_service.EditarMovimentacaoInput(
        data=date(2026, 1, 6), descricao="Compra mercado (corrigida)",
        categoria_id=categoria_despesa.id, valor=Decimal("50.00"), conta_id=conta.id, pago=True,
    )
    mov_service.atualizar_movimentacao(mov, dados, familia_id=conta.familia_id)

    # Esperado: estorna os 30 antigos (volta pra 100) e aplica os 50 novos (vai pra 50)
    assert float(conta.saldo_atual) == 50.00


def test_excluir_movimentacao_paga_estorna_saldo(db, conta, categoria_despesa, usuario):
    mov = Movimentacao(
        usuario_id=usuario.id, familia_id=conta.familia_id, data=date(2026, 1, 5),
        descricao="Compra mercado", categoria_id=categoria_despesa.id, tipo="despesa",
        valor=Decimal("30.00"), conta_id=conta.id, pago=True,
    )
    conta.saldo_atual -= Decimal("30.00")
    db.session.add(mov)
    db.session.commit()
    assert float(conta.saldo_atual) == 70.00

    mov_service.excluir_movimentacao(mov, familia_id=conta.familia_id)

    assert float(conta.saldo_atual) == 100.00  # os 30 voltaram


def test_editar_movimentacao_de_fatura_e_bloqueada(db, conta, categoria_despesa, usuario):
    """Uma movimentação de fatura (criada pelo fatura_service) não pode ser
    editada pela tela normal de movimentações — tem que ser pelo módulo de cartões."""
    mov = Movimentacao(
        usuario_id=usuario.id, familia_id=conta.familia_id, data=date(2026, 1, 10),
        descricao="Fatura Nubank 07/26", categoria_id=None, tipo="despesa",
        valor=Decimal("500.00"), conta_id=conta.id, pago=False,
    )
    db.session.add(mov)
    db.session.commit()

    dados = mov_service.EditarMovimentacaoInput(
        data=date(2026, 1, 10), descricao="Fatura Nubank 07/26",
        categoria_id=categoria_despesa.id, valor=Decimal("500.00"), conta_id=conta.id, pago=False,
    )

    with pytest.raises(mov_service.MovimentacaoBloqueadaError):
        mov_service.atualizar_movimentacao(mov, dados, familia_id=conta.familia_id)