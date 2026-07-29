"""Testes do app/services/fatura_service.py — a parte mais delicada do
sistema (fechar, reabrir, pagar com rotativo e estornar fatura).

Como rodar só este arquivo:
    pytest tests/test_fatura_service.py -v
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models import Fatura, Movimentacao, MovimentacaoCartao, PagamentoFatura
from app.services import fatura_service


def _criar_fatura(db, cartao, familia, mes=7, ano=2026, status="aberta"):
    fatura = Fatura(
        cartao_id=cartao.id, mes=mes, ano=ano,
        data_fechamento=date(ano, mes, 10), data_vencimento=date(ano, mes, 20),
        status=status, saldo=Decimal("0.00"), familia_id=familia.id,
    )
    db.session.add(fatura)
    db.session.commit()
    return fatura


def _criar_compra(db, fatura, cartao, categoria_despesa, usuario, familia, valor="200.00"):
    mov = MovimentacaoCartao(
        descricao="Compra teste", valor=Decimal(valor), data_compra=date(2026, 7, 5),
        cartao_id=cartao.id, categoria_id=categoria_despesa.id, usuario_id=usuario.id,
        familia_id=familia.id, numero_parcelas=1, parcela_atual=1, fatura_id=fatura.id,
    )
    db.session.add(mov)
    db.session.commit()
    return mov


# ---------------------------------------------------------------------------
# Fechar fatura
# ---------------------------------------------------------------------------
def test_fechar_fatura_com_saldo_cria_movimentacao_pendente(db, cartao, familia, usuario, categoria_despesa):
    fatura = _criar_fatura(db, cartao, familia)
    _criar_compra(db, fatura, cartao, categoria_despesa, usuario, familia, valor="200.00")

    fatura_service.fechar_fatura(fatura, usuario_id=usuario.id, familia_id=familia.id)

    assert fatura.status == "fechada"
    assert float(fatura.saldo) == 200.00

    mov_pendente = Movimentacao.query.filter_by(familia_id=familia.id, pago=False).first()
    assert mov_pendente is not None
    assert float(mov_pendente.valor) == 200.00


def test_fechar_fatura_zerada_e_excluida(db, cartao, familia, usuario):
    fatura = _criar_fatura(db, cartao, familia)  # sem nenhuma compra -> saldo fica 0

    mensagem = fatura_service.fechar_fatura(fatura, usuario_id=usuario.id, familia_id=familia.id)

    assert "excluída" in mensagem
    assert Fatura.query.count() == 0


def test_fechar_fatura_ja_fechada_e_bloqueada(db, cartao, familia, usuario):
    fatura = _criar_fatura(db, cartao, familia, status="fechada")

    with pytest.raises(fatura_service.FaturaJaFechadaError):
        fatura_service.fechar_fatura(fatura, usuario_id=usuario.id, familia_id=familia.id)


# ---------------------------------------------------------------------------
# Reabrir fatura
# ---------------------------------------------------------------------------
def test_reabrir_fatura_remove_movimentacao_pendente(db, cartao, familia, usuario):
    fatura = _criar_fatura(db, cartao, familia, status="fechada")
    fatura.saldo = Decimal("150.00")
    db.session.add(Movimentacao(
        usuario_id=usuario.id, familia_id=familia.id, data=fatura.data_vencimento,
        descricao=f"Fatura {cartao.nome} 07/26", categoria_id=None, tipo="despesa",
        valor=fatura.saldo, conta_id=None, pago=False,
    ))
    db.session.commit()

    fatura_service.reabrir_fatura(fatura, familia_id=familia.id)

    assert fatura.status == "aberta"
    assert Movimentacao.query.count() == 0


def test_reabrir_fatura_ja_aberta_e_bloqueada(db, cartao, familia):
    fatura = _criar_fatura(db, cartao, familia, status="aberta")

    with pytest.raises(fatura_service.FaturaJaAbertaError):
        fatura_service.reabrir_fatura(fatura, familia_id=familia.id)


# ---------------------------------------------------------------------------
# Pagar fatura
# ---------------------------------------------------------------------------
def test_pagar_fatura_total_debita_conta_e_marca_paga(db, cartao, familia, usuario, conta):
    fatura = _criar_fatura(db, cartao, familia, status="fechada")
    fatura.saldo = Decimal("100.00")
    db.session.commit()

    dados = fatura_service.PagamentoFaturaInput(
        conta_id=conta.id, valor=Decimal("100.00"), data_pagamento=date(2026, 7, 20)
    )
    mensagem = fatura_service.pagar_fatura(fatura, dados, usuario_id=usuario.id, familia_id=familia.id)

    assert fatura.status == "pago"
    assert float(conta.saldo_atual) == 0.00  # 100 - 100
    assert "sucesso" in mensagem
    assert PagamentoFatura.query.count() == 1


def test_pagar_fatura_com_saldo_insuficiente_e_bloqueada(db, cartao, familia, usuario, conta):
    fatura = _criar_fatura(db, cartao, familia, status="fechada")
    fatura.saldo = Decimal("500.00")  # a conta só tem 100
    db.session.commit()

    dados = fatura_service.PagamentoFaturaInput(
        conta_id=conta.id, valor=Decimal("500.00"), data_pagamento=date(2026, 7, 20)
    )

    with pytest.raises(fatura_service.SaldoInsuficienteError):
        fatura_service.pagar_fatura(fatura, dados, usuario_id=usuario.id, familia_id=familia.id)


def test_pagar_fatura_parcialmente_rola_saldo_restante_para_proxima_fatura(db, cartao, familia, usuario, conta):
    """Este é o caso que motivou a correção do bug do familia_id faltando
    ao criar a fatura seguinte — vale testar com atenção."""
    fatura = _criar_fatura(db, cartao, familia, mes=7, ano=2026, status="fechada")
    fatura.saldo = Decimal("100.00")
    db.session.commit()

    dados = fatura_service.PagamentoFaturaInput(
        conta_id=conta.id, valor=Decimal("40.00"), data_pagamento=date(2026, 7, 20)
    )
    mensagem = fatura_service.pagar_fatura(fatura, dados, usuario_id=usuario.id, familia_id=familia.id)

    assert fatura.status == "pago_parcial"
    assert "parcial" in mensagem
    assert float(conta.saldo_atual) == 60.00  # 100 - 40

    fatura_seguinte = Fatura.query.filter_by(cartao_id=cartao.id, mes=8, ano=2026, familia_id=familia.id).first()
    assert fatura_seguinte is not None
    assert fatura_seguinte.familia_id == familia.id  # a correção do bug: isso não pode ser None


# ---------------------------------------------------------------------------
# Estornar pagamento
# ---------------------------------------------------------------------------
def test_estornar_pagamento_devolve_saldo_e_reabre_fatura(db, cartao, familia, usuario, conta):
    fatura = _criar_fatura(db, cartao, familia, status="fechada")
    fatura.saldo = Decimal("100.00")
    db.session.commit()

    dados = fatura_service.PagamentoFaturaInput(
        conta_id=conta.id, valor=Decimal("100.00"), data_pagamento=date(2026, 7, 20)
    )
    fatura_service.pagar_fatura(fatura, dados, usuario_id=usuario.id, familia_id=familia.id)
    assert float(conta.saldo_atual) == 0.00

    fatura_service.estornar_pagamento(fatura, familia_id=familia.id, usuario_id=usuario.id)

    assert fatura.status == "fechada"
    assert float(conta.saldo_atual) == 100.00  # o dinheiro voltou
    assert PagamentoFatura.query.count() == 0


def test_estornar_sem_pagamento_e_bloqueado(db, cartao, familia, usuario):
    fatura = _criar_fatura(db, cartao, familia, status="fechada")

    with pytest.raises(fatura_service.SemPagamentoParaEstornarError):
        fatura_service.estornar_pagamento(fatura, familia_id=familia.id, usuario_id=usuario.id)