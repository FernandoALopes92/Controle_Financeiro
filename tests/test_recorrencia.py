"""Recorrência de 3, 6 e 12 meses (contas e cartão).

Como rodar só este arquivo:
    pytest tests/test_recorrencia.py -v
"""
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models import Movimentacao, MovimentacaoCartao
from app.services import cartao_service, movimentacao_service as mov_service
from app.utils.recorrencia import meses_da_recorrencia


@pytest.mark.parametrize(
    "valor, esperado",
    [("3_meses", 3), ("6_meses", 6), ("12_meses", 12), ("nao", 0), ("", 0), (None, 0), ("99_meses", 0)],
)
def test_meses_da_recorrencia(valor, esperado):
    assert meses_da_recorrencia(valor) == esperado


@pytest.mark.parametrize("replicar, clones", [("3_meses", 3), ("6_meses", 6), ("12_meses", 12)])
def test_conta_recorrente_clona_meses_seguintes(db, conta, categoria_despesa, usuario, replicar, clones):
    dados = mov_service.NovaMovimentacaoInput(
        data=date(2026, 1, 15), descricao="Internet", categoria_id=categoria_despesa.id,
        valor=Decimal("100.00"), conta_id=conta.id, pago=False, replicar=replicar,
    )

    mov_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=conta.familia_id)

    movs = Movimentacao.query.order_by(Movimentacao.data).all()
    assert len(movs) == 1 + clones
    assert len({m.data for m in movs}) == 1 + clones  # uma data diferente por mês


def test_conta_recorrente_um_ano_termina_um_ano_depois(db, conta, categoria_despesa, usuario):
    dados = mov_service.NovaMovimentacaoInput(
        data=date(2026, 3, 10), descricao="IPTV", categoria_id=categoria_despesa.id,
        valor=Decimal("30.00"), conta_id=conta.id, pago=False, replicar="12_meses",
    )

    mov_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=conta.familia_id)

    ultima = Movimentacao.query.order_by(Movimentacao.data.desc()).first()
    assert ultima.data == date(2027, 3, 10)


@pytest.mark.parametrize("replicar, clones", [("3_meses", 3), ("6_meses", 6), ("12_meses", 12)])
def test_compra_cartao_recorrente_cria_grupo_e_clones(db, cartao, categoria_despesa, usuario, familia, replicar, clones):
    dados = cartao_service.NovaMovimentacaoInput(
        descricao="Claro", valor=Decimal("80.00"), data_compra=datetime(2026, 7, 5),
        cartao_id=cartao.id, categoria_id=categoria_despesa.id, fatura_mes_ano="7-2026",
        tipo_pagamento="avista", tipo_valor=None, numero_parcelas=1, replicar=replicar,
    )

    cartao_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=familia.id)

    movs = MovimentacaoCartao.query.all()
    assert len(movs) == 1 + clones
    # todos no mesmo grupo (é isso que habilita "alterar esta e as próximas")
    assert len({m.compra_grupo_id for m in movs}) == 1
    assert movs[0].compra_grupo_id is not None
