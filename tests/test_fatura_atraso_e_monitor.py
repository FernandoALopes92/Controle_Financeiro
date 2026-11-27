"""Tag "Com atraso" nas faturas pagas, monitor de faturas (atuais e próximas)
e filtro de pesquisa da tela de categorias.

Como rodar só este arquivo:
    pytest tests/test_fatura_atraso_e_monitor.py -v
"""
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models import Fatura, MovimentacaoCartao, PagamentoFatura


@pytest.fixture
def client(app, usuario):
    cliente = app.test_client()
    with cliente.session_transaction() as sessao:
        sessao["_user_id"] = str(usuario.id)
        sessao["_fresh"] = True
    return cliente


def _fatura(db, cartao, familia, mes, ano, status="aberta", valor="150.00", usuario=None, categoria=None):
    fatura = Fatura(
        cartao_id=cartao.id, mes=mes, ano=ano,
        data_fechamento=date(ano, mes, 10), data_vencimento=date(ano, mes, 20),
        status=status, saldo=Decimal(valor), familia_id=familia.id,
    )
    db.session.add(fatura)
    db.session.commit()
    if usuario and categoria:
        db.session.add(MovimentacaoCartao(
            descricao="Compra", valor=Decimal(valor), data_compra=date(ano, mes, 3),
            cartao_id=cartao.id, categoria_id=categoria.id, usuario_id=usuario.id,
            familia_id=familia.id, numero_parcelas=1, parcela_atual=1, fatura_id=fatura.id,
        ))
        db.session.commit()
    return fatura


def _pagar(db, fatura, conta, usuario, familia, dia, valor="150.00"):
    db.session.add(PagamentoFatura(
        usuario_id=usuario.id, conta_id=conta.id, fatura_id=fatura.id,
        valor_pago=Decimal(valor), data_pagamento=date(fatura.ano, fatura.mes, dia),
        familia_id=familia.id,
    ))
    db.session.commit()


# ---------------------------------------------------------------------------
# Regra do atraso (propriedades do modelo)
# ---------------------------------------------------------------------------
def test_fatura_paga_depois_do_vencimento_conta_dias_de_atraso(db, cartao, familia, conta, usuario):
    fatura = _fatura(db, cartao, familia, 7, 2026, status="pago")   # vence dia 20
    _pagar(db, fatura, conta, usuario, familia, dia=23)

    assert fatura.dias_atraso_pagamento == 3
    assert fatura.data_quitacao == date(2026, 7, 23)


def test_fatura_paga_no_vencimento_ou_antes_nao_tem_atraso(db, cartao, familia, conta, usuario):
    no_dia = _fatura(db, cartao, familia, 7, 2026, status="pago")
    _pagar(db, no_dia, conta, usuario, familia, dia=20)
    antes = _fatura(db, cartao, familia, 8, 2026, status="pago")
    _pagar(db, antes, conta, usuario, familia, dia=5)

    assert no_dia.dias_atraso_pagamento == 0
    assert antes.dias_atraso_pagamento == 0


def test_atraso_usa_a_data_do_pagamento_que_quitou(db, cartao, familia, conta, usuario):
    """Pago em duas vezes: vale a data do último pagamento (o que quitou)."""
    fatura = _fatura(db, cartao, familia, 7, 2026, status="pago")
    _pagar(db, fatura, conta, usuario, familia, dia=15, valor="50.00")
    _pagar(db, fatura, conta, usuario, familia, dia=25, valor="100.00")

    assert fatura.dias_atraso_pagamento == 5


@pytest.mark.parametrize("status", ["aberta", "fechada", "pago_parcial"])
def test_fatura_nao_quitada_nunca_tem_tag_de_atraso(db, cartao, familia, conta, usuario, status):
    fatura = _fatura(db, cartao, familia, 7, 2026, status=status)
    _pagar(db, fatura, conta, usuario, familia, dia=28, valor="10.00")

    assert fatura.dias_atraso_pagamento == 0


def test_fatura_paga_sem_registro_de_pagamento_nao_quebra(db, cartao, familia):
    """Faturas antigas marcadas como pagas sem PagamentoFatura: sem tag, sem erro."""
    fatura = _fatura(db, cartao, familia, 7, 2026, status="pago")

    assert fatura.data_quitacao is None
    assert fatura.dias_atraso_pagamento == 0


# ---------------------------------------------------------------------------
# Telas
# ---------------------------------------------------------------------------
def test_resumo_de_faturas_mostra_tag_com_atraso(db, client, cartao, familia, conta, usuario, categoria_despesa):
    fatura = _fatura(db, cartao, familia, 10, 2026, status="pago", usuario=usuario, categoria=categoria_despesa)
    _pagar(db, fatura, conta, usuario, familia, dia=24)

    html = client.get("/cartao/mov_cartao?mes=10&ano=2026").get_data(as_text=True)

    assert "Com atraso" in html
    assert "4 dia(s) após o vencimento" in html


def test_resumo_de_faturas_paga_em_dia_nao_mostra_tag(db, client, cartao, familia, conta, usuario, categoria_despesa):
    fatura = _fatura(db, cartao, familia, 10, 2026, status="pago", usuario=usuario, categoria=categoria_despesa)
    _pagar(db, fatura, conta, usuario, familia, dia=20)

    html = client.get("/cartao/mov_cartao?mes=10&ano=2026").get_data(as_text=True)

    assert "Com atraso" not in html


def test_monitor_do_dashboard_lista_faturas_atuais_e_proximas(db, client, cartao, familia, usuario, categoria_despesa):
    _fatura(db, cartao, familia, 10, 2026, valor="111.00", usuario=usuario, categoria=categoria_despesa)
    _fatura(db, cartao, familia, 11, 2026, valor="222.00", usuario=usuario, categoria=categoria_despesa)

    html = client.get("/dashboard?mes=10&ano=2026").get_data(as_text=True)

    assert "111,00" in html           # fatura do mês atual
    assert "222,00" in html           # fatura do próximo ciclo (antes só aparecia um contador)
    assert "Próximo ciclo" in html


def test_monitor_do_dashboard_sem_fatura_proxima_mostra_aviso(db, client):
    html = client.get("/dashboard?mes=10&ano=2026").get_data(as_text=True)

    assert "Nenhuma fatura lançada em" in html


def test_tela_de_categorias_tem_campo_de_pesquisa_e_atributos_do_filtro(db, client, categoria_despesa):
    html = client.get("/categorias/").get_data(as_text=True)

    assert 'id="filtroCategorias"' in html
    assert 'data-cat-nivel="principal"' in html
    assert "js/categorias.js" in html
