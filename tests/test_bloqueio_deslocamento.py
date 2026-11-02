"""Fatura fechada ou paga é imutável; "esta e as próximas" desloca as faturas;
data da compra só muda na 1ª parcela dos parcelados.

Como rodar só este arquivo:
    pytest tests/test_bloqueio_e_deslocamento.py -v
"""
import re
from datetime import date
from decimal import Decimal

import pytest

from app.models import Fatura, MeioPagamento, MovimentacaoCartao
from app.services import cartao_service as cs


# ------------------------------- ajudas -------------------------------
def _cadastrar_4x(cartao, categoria, usuario, familia, descricao="Compra 4x"):
    """4 parcelas de 100, faturas out/26, nov/26, dez/26, jan/27."""
    dados = cs.NovaMovimentacaoInput(
        descricao=descricao, valor=Decimal("400.00"), data_compra=date(2026, 10, 10),
        cartao_id=cartao.id, categoria_id=categoria.id, tipo_pagamento="parcelado",
        fatura_mes_ano="10-2026", tipo_valor="total", numero_parcelas=4, replicar="nao",
    )
    cs.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=familia.id)
    return _movs(descricao)


def _movs(descricao="Compra 4x"):
    return MovimentacaoCartao.query.filter_by(descricao=descricao).order_by(MovimentacaoCartao.parcela_atual).all()


def _faturas(db, descricao="Compra 4x"):
    resultado = []
    for m in _movs(descricao):
        f = db.session.get(Fatura, m.fatura_id)
        resultado.append((f.mes, f.ano))
    return resultado


def _status(db, mov, status):
    db.session.get(Fatura, mov.fatura_id).status = status
    db.session.commit()


def _editar(mov, cartao, categoria, base, proximas, valor="100.00", descricao=None, data=None):
    return cs.EditarMovimentacaoInput(
        descricao=descricao or mov.descricao, valor=Decimal(valor), data_compra=data or mov.data_compra,
        cartao_id=cartao.id, categoria_id=categoria.id, fatura_mes_ano=base, alterar_proximas=proximas,
    )


def _atualizar(mov, dados):
    return cs.atualizar_movimentacao(mov, dados, familia_id=mov.familia_id)


# ---------------------------------------------------------------------------
# Fatura fechada ou paga é imutável
# ---------------------------------------------------------------------------
def test_excluir_parcela_em_fatura_fechada_e_recusado(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    _status(db, movs[0], "fechada")

    with pytest.raises(cs.FaturaBloqueadaError, match="10/2026"):
        cs.excluir_movimentacao(movs[0], familia_id=familia.id, excluir_todas=False)

    assert len(_movs()) == 4


def test_excluir_esta_e_proximas_preserva_as_anteriores_mesmo_em_fatura_paga(
    db, cartao, categoria_despesa, usuario, familia
):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    _status(db, movs[0], "pago")

    cs.excluir_movimentacao(movs[2], familia_id=familia.id, excluir_todas=True)

    assert [m.parcela_atual for m in _movs()] == [1, 2]


def test_excluir_esta_e_proximas_recusa_tudo_se_alguma_seguinte_esta_bloqueada(
    db, cartao, categoria_despesa, usuario, familia
):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    _status(db, movs[3], "fechada")  # fatura da parcela 4 fechada

    with pytest.raises(cs.FaturaBloqueadaError, match="parcela 4/4"):
        cs.excluir_movimentacao(movs[1], familia_id=familia.id, excluir_todas=True)

    assert len(_movs()) == 4  # nada foi apagado


def test_editar_parcela_em_fatura_paga_e_recusado(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    _status(db, movs[0], "pago")

    with pytest.raises(cs.FaturaBloqueadaError, match="paga"):
        _atualizar(movs[0], _editar(movs[0], cartao, categoria_despesa, "10-2026", False, valor="777.00"))

    assert str(_movs()[0].valor) == "100.00"


def test_alterar_proximas_recusa_tudo_se_alguma_seguinte_esta_em_fatura_fechada(
    db, cartao, categoria_despesa, usuario, familia
):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    _status(db, movs[2], "fechada")

    with pytest.raises(cs.FaturaBloqueadaError, match="parcela 3/4"):
        _atualizar(movs[1], _editar(movs[1], cartao, categoria_despesa, "11-2026", True, valor="999.00"))

    assert [str(m.valor) for m in _movs()] == ["100.00"] * 4  # nem a parcela 2 mudou


# ---------------------------------------------------------------------------
# Deslocamento das faturas
# ---------------------------------------------------------------------------
def test_trocar_a_fatura_com_proximas_desloca_as_seguintes(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)

    # parcela 2: de nov/26 para dez/26 (+1 mês), com "esta e as próximas"
    _atualizar(movs[1], _editar(movs[1], cartao, categoria_despesa, "12-2026", True))

    assert _faturas(db) == [(10, 2026), (12, 2026), (1, 2027), (2, 2027)]


def test_trocar_a_fatura_sem_marcar_proximas_move_so_a_editada(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)

    _atualizar(movs[1], _editar(movs[1], cartao, categoria_despesa, "12-2026", False))

    assert _faturas(db) == [(10, 2026), (12, 2026), (12, 2026), (1, 2027)]


def test_deslocamento_para_tras(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)

    _atualizar(movs[1], _editar(movs[1], cartao, categoria_despesa, "10-2026", True))  # nov -> out

    assert _faturas(db) == [(10, 2026), (10, 2026), (11, 2026), (12, 2026)]


def test_sem_mudar_a_fatura_nada_se_desloca(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)

    _atualizar(movs[1], _editar(movs[1], cartao, categoria_despesa, "11-2026", True, valor="120.00"))

    assert _faturas(db) == [(10, 2026), (11, 2026), (12, 2026), (1, 2027)]
    assert [str(m.valor) for m in _movs()] == ["100.00", "120.00", "120.00", "120.00"]


def test_destino_fechado_da_propria_parcela_recusa(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    _status(db, movs[2], "fechada")  # dez/26 fechada (e é a fatura da parcela 3)

    with pytest.raises(cs.FaturaFechadaError):
        _atualizar(movs[1], _editar(movs[1], cartao, categoria_despesa, "12-2026", False))

    assert _faturas(db) == [(10, 2026), (11, 2026), (12, 2026), (1, 2027)]


def test_destino_fechado_de_uma_seguinte_recusa_tudo(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    fev = cs.obter_ou_criar_fatura_aberta(cartao, 2, 2027, familia.id)  # destino da parcela 4 (+1)
    fev.status = "fechada"
    db.session.commit()

    with pytest.raises(cs.FaturaBloqueadaError, match="mover a parcela 4/4 de 'Compra 4x' para a fatura 02/2027"):
        _atualizar(movs[1], _editar(movs[1], cartao, categoria_despesa, "12-2026", True, valor="555.00"))

    assert _faturas(db) == [(10, 2026), (11, 2026), (12, 2026), (1, 2027)]
    assert [str(m.valor) for m in _movs()] == ["100.00"] * 4


def test_cada_parcela_usa_as_faturas_do_proprio_cartao(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    outro = MeioPagamento(nome="Outro cartão", tipo="Crédito", limite=Decimal("500.00"), fechamento_dia=5,
                          vencimento_dia=15, usuario_id=usuario.id, familia_id=familia.id)
    db.session.add(outro)
    db.session.commit()
    # a parcela 3 foi paga em outro cartão (como o Espaço Laser)
    movs[2].cartao_id = outro.id
    movs[2].fatura_id = cs.obter_ou_criar_fatura_aberta(outro, 12, 2026, familia.id).id
    db.session.commit()

    _atualizar(movs[1], _editar(movs[1], cartao, categoria_despesa, "12-2026", True))

    f3 = db.session.get(Fatura, _movs()[2].fatura_id)
    assert (f3.cartao_id, f3.mes, f3.ano) == (outro.id, 1, 2027)


def test_saldos_das_faturas_sao_recalculados_apos_o_deslocamento(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)

    _atualizar(movs[1], _editar(movs[1], cartao, categoria_despesa, "12-2026", True, valor="130.00"))

    for fatura in Fatura.query.all():
        esperado = sum((m.valor for m in fatura.movimentacoes), Decimal("0"))
        assert fatura.saldo == esperado


def _recorrentes(db, cartao, categoria, usuario, familia, meses=(7, 8, 9)):
    lista = []
    for mes in meses:
        fatura = cs.obter_ou_criar_fatura_aberta(cartao, mes, 2026, familia.id)
        m = MovimentacaoCartao(
            descricao="Claro", valor=Decimal("19.99"), data_compra=date(2026, mes, 20), cartao_id=cartao.id,
            categoria_id=categoria.id, usuario_id=usuario.id, familia_id=familia.id,
            numero_parcelas=1, parcela_atual=1, compra_grupo_id="g-claro", fatura_id=fatura.id,
        )
        db.session.add(m)
        lista.append(m)
    db.session.commit()
    return lista


def test_recorrente_desloca_a_fatura_mas_nao_mexe_nas_datas(db, cartao, categoria_despesa, usuario, familia):
    recorrentes = _recorrentes(db, cartao, categoria_despesa, usuario, familia)

    # a Claro de julho caiu na fatura de agosto: com "próximas", as seguintes andam junto
    _atualizar(recorrentes[0], _editar(recorrentes[0], cartao, categoria_despesa, "8-2026", True, valor="21.99"))

    movs = _movs("Claro")
    assert _faturas(db, "Claro") == [(8, 2026), (9, 2026), (10, 2026)]
    assert [m.data_compra for m in movs] == [date(2026, 7, 20), date(2026, 8, 20), date(2026, 9, 20)]
    assert {str(m.valor) for m in movs} == {"21.99"}


# ---------------------------------------------------------------------------
# Data da compra
# ---------------------------------------------------------------------------
def test_data_da_parcela_2_em_diante_e_bloqueada(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)

    with pytest.raises(cs.DataCompraBloqueadaError, match="1ª parcela"):
        _atualizar(movs[1], _editar(movs[1], cartao, categoria_despesa, "11-2026", False, data=date(2026, 10, 25)))

    assert {m.data_compra for m in _movs()} == {date(2026, 10, 10)}


def test_data_da_parcela_1_vale_para_todas_as_parcelas(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)

    _atualizar(movs[0], _editar(movs[0], cartao, categoria_despesa, "10-2026", False, data=date(2026, 10, 3)))

    assert {m.data_compra for m in _movs()} == {date(2026, 10, 3)}
    assert _faturas(db) == [(10, 2026), (11, 2026), (12, 2026), (1, 2027)]  # faturas intactas


def test_data_da_parcela_1_recusa_se_alguma_parcela_esta_em_fatura_paga(
    db, cartao, categoria_despesa, usuario, familia
):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    _status(db, movs[2], "pago")

    with pytest.raises(cs.FaturaBloqueadaError, match="alterar a data"):
        _atualizar(movs[0], _editar(movs[0], cartao, categoria_despesa, "10-2026", False, data=date(2026, 10, 3)))

    assert {m.data_compra for m in _movs()} == {date(2026, 10, 10)}


def test_data_da_parcela_1_em_compra_antiga_muda_so_a_propria(db, cartao, categoria_despesa, usuario, familia):
    """Compras antigas guardam datas deslocadas por parcela; não dá para unificar sem perder isso."""
    antigas = []
    for k in range(3):
        fatura = cs.obter_ou_criar_fatura_aberta(cartao, 10 + k, 2026, familia.id)
        m = MovimentacaoCartao(
            descricao="Antiga", valor=Decimal("50.00"), data_compra=date(2026, 10 + k, 5), cartao_id=cartao.id,
            categoria_id=categoria_despesa.id, usuario_id=usuario.id, familia_id=familia.id,
            numero_parcelas=3, parcela_atual=k + 1, compra_grupo_id="g-antiga", fatura_id=fatura.id,
        )
        db.session.add(m)
        antigas.append(m)
    db.session.commit()

    _atualizar(antigas[0], _editar(antigas[0], cartao, categoria_despesa, "10-2026", False, valor="50.00",
                                   data=date(2026, 10, 1)))

    assert [m.data_compra for m in _movs("Antiga")] == [date(2026, 10, 1), date(2026, 11, 5), date(2026, 12, 5)]


def test_data_do_recorrente_e_editavel_so_nele(db, cartao, categoria_despesa, usuario, familia):
    recorrentes = _recorrentes(db, cartao, categoria_despesa, usuario, familia, meses=(7, 8))

    _atualizar(recorrentes[0], _editar(recorrentes[0], cartao, categoria_despesa, "7-2026", True, valor="19.99",
                                       data=date(2026, 7, 22)))

    assert [m.data_compra for m in _movs("Claro")] == [date(2026, 7, 22), date(2026, 8, 20)]


# ---------------------------------------------------------------------------
# Quem tem "próximas" (para a tela)
# ---------------------------------------------------------------------------
def test_ids_com_proximas(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    avulso = MovimentacaoCartao(
        descricao="Avulso", valor=Decimal("10.00"), data_compra=date(2026, 10, 1), cartao_id=cartao.id,
        categoria_id=categoria_despesa.id, usuario_id=usuario.id, familia_id=familia.id,
        numero_parcelas=1, parcela_atual=1, compra_grupo_id=None,
        fatura_id=movs[0].fatura_id,
    )
    db.session.add(avulso)
    db.session.commit()

    ids = cs.ids_com_proximas([*movs, avulso], familia.id)

    assert ids == {movs[0].id, movs[1].id, movs[2].id}  # a última parcela e o avulso ficam de fora


# ---------------------------------------------------------------------------
# Pelas rotas (tela): listagem, edição e exclusão
# ---------------------------------------------------------------------------
AJAX = {"X-Requested-With": "XMLHttpRequest"}


def _cliente_logado(app, usuario):
    app.config["SECRET_KEY"] = "teste"
    client = app.test_client()
    with client.session_transaction() as sessao:
        sessao["_user_id"] = str(usuario.id)
        sessao["_fresh"] = True
    return client


def test_rota_listagem_marca_quem_tem_proximas(app, db, cartao, categoria_despesa, usuario, familia):
    _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    client = _cliente_logado(app, usuario)

    outubro = client.get("/cartao/mov_cartao?ano=2026&mes=10").get_data(as_text=True)
    janeiro = client.get("/cartao/mov_cartao?ano=2027&mes=1").get_data(as_text=True)

    assert set(re.findall(r'data-tem-proximas="(\d)"', outubro)) == {"1"}  # parcela 1 tem seguintes
    assert set(re.findall(r'data-tem-proximas="(\d)"', janeiro)) == {"0"}  # a última não tem


def test_rota_editar_informa_parcela_e_tem_proximas(app, db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    client = _cliente_logado(app, usuario)

    primeira = client.get(f"/cartao/mov_cartao/editar/{movs[0].id}", headers=AJAX).get_json()
    ultima = client.get(f"/cartao/mov_cartao/editar/{movs[3].id}", headers=AJAX).get_json()

    assert (primeira["parcela_atual"], primeira["tem_proximas"]) == (1, True)
    assert (ultima["parcela_atual"], ultima["tem_proximas"]) == (4, False)


def _form_edicao(mov, cartao, categoria, base, proximas, valor="100,00", data="2026-10-10"):
    return {
        "descricao": mov.descricao, "valor": valor, "data": data, "meio_pagamento_id": cartao.id,
        "categoria_id": categoria.id, "fatura_mes_ano": base, "alterar_proximas": "true" if proximas else "false",
    }


def test_rota_editar_data_da_parcela_2_devolve_mensagem_clara(app, db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    client = _cliente_logado(app, usuario)

    r = client.post(f"/cartao/mov_cartao/{movs[1].id}/edit", headers=AJAX,
                    data=_form_edicao(movs[1], cartao, categoria_despesa, "11-2026", False, data="2026-10-25"))

    assert r.status_code == 400
    assert "1ª parcela" in r.get_json()["erro"]
    assert {m.data_compra for m in _movs()} == {date(2026, 10, 10)}


def test_rota_editar_com_proximas_desloca_as_faturas(app, db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    client = _cliente_logado(app, usuario)

    r = client.post(f"/cartao/mov_cartao/{movs[1].id}/edit", headers=AJAX,
                    data=_form_edicao(movs[1], cartao, categoria_despesa, "12-2026", True))

    assert r.status_code == 200
    assert _faturas(db) == [(10, 2026), (12, 2026), (1, 2027), (2, 2027)]


def test_rota_excluir_recusa_fatura_fechada_e_exclui_esta_e_as_proximas(
    app, db, cartao, categoria_despesa, usuario, familia
):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)
    client = _cliente_logado(app, usuario)
    _status(db, movs[0], "fechada")

    bloqueada = client.post(f"/cartao/mov_cartao/{movs[0].id}/excluir", headers=AJAX, data={"excluir_todas": "false"})
    assert bloqueada.status_code == 400
    assert "10/2026" in bloqueada.get_json()["erro"]
    assert len(_movs()) == 4

    ok = client.post(f"/cartao/mov_cartao/{movs[1].id}/excluir", headers=AJAX, data={"excluir_todas": "true"})
    assert ok.status_code == 200
    assert [m.parcela_atual for m in _movs()] == [1]