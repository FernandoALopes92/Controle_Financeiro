"""Testes do app/services/cartao_service.py — compras à vista, parceladas,
e o ciclo de mover/excluir movimentações de cartão entre faturas.

Como rodar só este arquivo:
    pytest tests/test_cartao_service.py -v
"""
from datetime import datetime
from decimal import Decimal

import pytest

from app.models import Fatura, MovimentacaoCartao
from app.services import cartao_service


def _dados_avista(cartao, categoria, fatura_mes_ano="7-2026", valor="50.00", replicar="nao"):
    return cartao_service.NovaMovimentacaoInput(
        descricao="Compra teste", valor=Decimal(valor), data_compra=datetime(2026, 7, 5),
        cartao_id=cartao.id, categoria_id=categoria.id, fatura_mes_ano=fatura_mes_ano,
        tipo_pagamento="avista", tipo_valor=None, numero_parcelas=1, replicar=replicar,
    )


def _dados_parcelado(cartao, categoria, valor="100.00", numero_parcelas=3, tipo_valor=None):
    return cartao_service.NovaMovimentacaoInput(
        descricao="Compra parcelada", valor=Decimal(valor), data_compra=datetime(2026, 7, 5),
        cartao_id=cartao.id, categoria_id=categoria.id, fatura_mes_ano="7-2026",
        tipo_pagamento="parcelado", tipo_valor=tipo_valor, numero_parcelas=numero_parcelas, replicar="nao",
    )


# ---------------------------------------------------------------------------
# Criar movimentação
# ---------------------------------------------------------------------------
def test_criar_compra_a_vista_gera_uma_movimentacao_e_atualiza_fatura(db, cartao, categoria_despesa, usuario, familia):
    dados = _dados_avista(cartao, categoria_despesa)

    mensagem, faturas_modificadas = cartao_service.criar_movimentacao(
        dados, usuario_id=usuario.id, familia_id=familia.id
    )

    assert "à vista" in mensagem
    assert MovimentacaoCartao.query.count() == 1

    fatura = Fatura.query.filter_by(cartao_id=cartao.id, mes=7, ano=2026, familia_id=familia.id).first()
    assert fatura is not None
    assert float(fatura.saldo) == 50.00
    assert fatura.id in faturas_modificadas


def test_criar_compra_parcelada_gera_uma_movimentacao_por_parcela(db, cartao, categoria_despesa, usuario, familia):
    dados = _dados_parcelado(cartao, categoria_despesa, valor="100.00", numero_parcelas=3)

    mensagem, faturas_modificadas = cartao_service.criar_movimentacao(
        dados, usuario_id=usuario.id, familia_id=familia.id
    )

    assert "3 parcelas" in mensagem
    assert MovimentacaoCartao.query.count() == 3
    assert len(faturas_modificadas) == 3  # uma fatura por mês (Jul, Ago, Set)

    # Sem tipo_valor="total", cada parcela vale o valor cheio informado (100 cada)
    soma_faturas = sum(f.saldo for f in Fatura.query.filter_by(cartao_id=cartao.id, familia_id=familia.id).all())
    assert float(soma_faturas) == 300.00


def test_criar_compra_parcelada_valor_total_divide_com_residuo_na_primeira_parcela(
    db, cartao, categoria_despesa, usuario, familia
):
    """Compra de R$100 em 3x 'valor total': 100/3 = 33.33 com sobra de 0.01,
    que a primeira parcela absorve (33.34 + 33.33 + 33.33 = 100.00 certinho)."""
    dados = _dados_parcelado(cartao, categoria_despesa, valor="100.00", numero_parcelas=3, tipo_valor="total")

    cartao_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=familia.id)

    parcelas = MovimentacaoCartao.query.order_by(MovimentacaoCartao.parcela_atual).all()
    valores = [float(p.valor) for p in parcelas]

    assert valores == [33.34, 33.33, 33.33]
    assert round(sum(valores), 2) == 100.00  # nenhum centavo se perde no arredondamento


def test_criar_movimentacao_em_fatura_fechada_e_bloqueada(db, cartao, categoria_despesa, usuario, familia):
    fatura_fechada = Fatura(
        cartao_id=cartao.id, mes=7, ano=2026,
        data_fechamento=datetime(2026, 7, 10), data_vencimento=datetime(2026, 7, 20),
        status="fechada", saldo=Decimal("0.00"), familia_id=familia.id,
    )
    db.session.add(fatura_fechada)
    db.session.commit()

    dados = _dados_avista(cartao, categoria_despesa)

    with pytest.raises(cartao_service.FaturaFechadaError):
        cartao_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=familia.id)


def test_criar_movimentacao_sem_fatura_selecionada_e_bloqueada(db, cartao, categoria_despesa, usuario, familia):
    dados = _dados_avista(cartao, categoria_despesa, fatura_mes_ano="")

    with pytest.raises(cartao_service.FaturaNaoSelecionadaError):
        cartao_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=familia.id)


# ---------------------------------------------------------------------------
# Atualizar movimentação
# ---------------------------------------------------------------------------
def test_atualizar_movimentacao_move_para_outra_fatura_recalcula_as_duas(
    db, cartao, categoria_despesa, usuario, familia
):
    dados_criar = _dados_avista(cartao, categoria_despesa, valor="50.00")
    cartao_service.criar_movimentacao(dados_criar, usuario_id=usuario.id, familia_id=familia.id)
    mov = MovimentacaoCartao.query.first()
    fatura_julho = Fatura.query.filter_by(mes=7, ano=2026, familia_id=familia.id).first()
    assert float(fatura_julho.saldo) == 50.00

    dados_editar = cartao_service.EditarMovimentacaoInput(
        descricao="Compra movida", valor=Decimal("50.00"), data_compra=datetime(2026, 8, 5),
        cartao_id=cartao.id, categoria_id=categoria_despesa.id, fatura_mes_ano="8-2026",
    )
    cartao_service.atualizar_movimentacao(mov, dados_editar, familia_id=familia.id)

    fatura_agosto = Fatura.query.filter_by(mes=8, ano=2026, familia_id=familia.id).first()
    assert fatura_agosto is not None
    assert float(fatura_agosto.saldo) == 50.00

    db.session.refresh(fatura_julho)
    assert float(fatura_julho.saldo) == 0.00  # a fatura antiga ficou sem essa compra


# ---------------------------------------------------------------------------
# Excluir movimentação
# ---------------------------------------------------------------------------
def test_excluir_movimentacao_individual_recalcula_fatura(db, cartao, categoria_despesa, usuario, familia):
    dados = _dados_avista(cartao, categoria_despesa, valor="50.00")
    cartao_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=familia.id)
    mov = MovimentacaoCartao.query.first()
    fatura = Fatura.query.filter_by(mes=7, ano=2026, familia_id=familia.id).first()

    cartao_service.excluir_movimentacao(mov, familia_id=familia.id, excluir_todas=False)

    assert MovimentacaoCartao.query.count() == 0
    db.session.refresh(fatura)
    assert float(fatura.saldo) == 0.00


def test_excluir_todas_as_parcelas_do_grupo(db, cartao, categoria_despesa, usuario, familia):
    dados = _dados_parcelado(cartao, categoria_despesa, valor="100.00", numero_parcelas=3)
    cartao_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=familia.id)
    assert MovimentacaoCartao.query.count() == 3

    primeira_parcela = MovimentacaoCartao.query.filter_by(parcela_atual=1).first()
    cartao_service.excluir_movimentacao(primeira_parcela, familia_id=familia.id, excluir_todas=True)

    assert MovimentacaoCartao.query.count() == 0  # as 3 parcelas somem juntas