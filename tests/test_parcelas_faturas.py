"""Parcelas e faturas: cada parcela cai num mês seguido, a data original é
guardada em todas, e "alterar esta e as próximas" não depende da data.

Como rodar só este arquivo:
    pytest tests/test_parcelas_faturas.py -v
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models import Fatura, MovimentacaoCartao
from app.services import cartao_service as cs


def _cartao(fechamento, vencimento):
    return SimpleNamespace(fechamento_dia=fechamento, vencimento_dia=vencimento)


# ---------------------------------------------------------------------------
# Cálculo da fatura pela data (funções puras)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fechamento, vencimento, data, esperado",
    [
        (1, 8, date(2026, 10, 10), (11, 2026)),    # depois do fechamento, vence no mês do fechamento
        (10, 17, date(2026, 10, 10), (10, 2026)),  # no dia do fechamento ainda entra
        (10, 17, date(2026, 10, 11), (11, 2026)),  # um dia depois, vai para a próxima
        (30, 7, date(2026, 1, 30), (2, 2026)),     # vence antes de fechar: fatura do mês seguinte
        (30, 7, date(2026, 1, 31), (3, 2026)),
        (31, 7, date(2026, 2, 28), (3, 2026)),     # fevereiro com fechamento 31
        (5, 15, date(2026, 12, 20), (1, 2027)),    # virada de ano
        (28, 5, date(2026, 12, 29), (2, 2027)),    # virada de ano com vencimento antes do fechamento
    ],
)
def test_mes_ano_da_fatura(fechamento, vencimento, data, esperado):
    assert cs.mes_ano_da_fatura(_cartao(fechamento, vencimento), data) == esperado


@pytest.mark.parametrize(
    "fechamento, vencimento, data, parcelas, esperado",
    [
        # o exemplo do usuário
        (1, 8, date(2026, 10, 10), 3, [(11, 2026), (12, 2026), (1, 2027)]),
        # compra no dia 31, fecha dia 30: o cálculo por data repetia março e maio
        (30, 7, date(2026, 1, 31), 4, [(3, 2026), (4, 2026), (5, 2026), (6, 2026)]),
        # compra no dia 29, fecha dia 28: repetia março
        (28, 7, date(2026, 1, 29), 4, [(3, 2026), (4, 2026), (5, 2026), (6, 2026)]),
        # parcelamento longo atravessa mais de um ano
        (10, 17, date(2026, 11, 3), 14, [(11, 2026), (12, 2026)] + [(m, 2027) for m in range(1, 13)]),
    ],
)
def test_faturas_das_parcelas_sao_meses_seguidos(fechamento, vencimento, data, parcelas, esperado):
    resultado = cs.faturas_das_parcelas(_cartao(fechamento, vencimento), data, parcelas)
    assert resultado == esperado


def test_previsao_para_a_parcela_n_soma_os_meses():
    cartao = _cartao(1, 8)
    parcela_1 = cs.prever_opcoes_fatura(cartao, date(2026, 10, 10))
    parcela_3 = cs.prever_opcoes_fatura(cartao, date(2026, 10, 10), parcela_atual=3)
    assert [o["valor"] for o in parcela_1] == ["11-2026", "12-2026"]
    assert [o["valor"] for o in parcela_3] == ["1-2027", "2-2027"]
    assert "Prevista" in parcela_3[0]["texto"]


# ---------------------------------------------------------------------------
# Cadastro e edição pelo serviço
# ---------------------------------------------------------------------------
def _cadastrar_3x(cartao, categoria, usuario, familia, descricao="Compra 3x", base="10-2026"):
    dados = cs.NovaMovimentacaoInput(
        descricao=descricao, valor=Decimal("300.00"), data_compra=date(2026, 10, 10),
        cartao_id=cartao.id, categoria_id=categoria.id, tipo_pagamento="parcelado",
        fatura_mes_ano=base, tipo_valor="total", numero_parcelas=3, replicar="nao",
    )
    cs.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=familia.id)
    return (
        MovimentacaoCartao.query.filter_by(descricao=descricao)
        .order_by(MovimentacaoCartao.parcela_atual)
        .all()
    )


def _fatura(mov, db):
    f = db.session.get(Fatura, mov.fatura_id)
    return (f.mes, f.ano)


def test_cadastro_parcelado_guarda_a_data_original_e_faturas_seguidas(
    db, cartao, categoria_despesa, usuario, familia
):
    movs = _cadastrar_3x(cartao, categoria_despesa, usuario, familia)

    assert [m.data_compra for m in movs] == [date(2026, 10, 10)] * 3
    assert [_fatura(m, db) for m in movs] == [(10, 2026), (11, 2026), (12, 2026)]
    assert len({m.compra_grupo_id for m in movs}) == 1


def _editar(mov, cartao, categoria, valor, base, proximas):
    return cs.EditarMovimentacaoInput(
        descricao=mov.descricao, valor=Decimal(valor), data_compra=mov.data_compra,
        cartao_id=cartao.id, categoria_id=categoria.id, fatura_mes_ano=base, alterar_proximas=proximas,
    )


def test_alterar_proximas_funciona_com_datas_iguais(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_3x(cartao, categoria_despesa, usuario, familia)
    outra = _cadastrar_3x(cartao, categoria_despesa, usuario, familia, descricao="Outra compra")

    # edita a parcela 2 (fatura 11/2026) com "alterar esta e as próximas"
    cs.atualizar_movimentacao(
        movs[1], _editar(movs[1], cartao, categoria_despesa, "111.00", "11-2026", True), familia_id=familia.id
    )

    valores = [str(m.valor) for m in MovimentacaoCartao.query.filter_by(descricao="Compra 3x")
               .order_by(MovimentacaoCartao.parcela_atual)]
    assert valores == ["100.00", "111.00", "111.00"]  # a 1ª não muda
    assert {str(m.valor) for m in outra} == {"100.00"}  # outra compra intacta


def test_parcelas_seguintes_funciona_com_datas_antigas_deslocadas(
    db, cartao, categoria_despesa, usuario, familia
):
    """Compras antigas guardam a data deslocada por parcela; a ordem das faturas serve às duas."""
    movs = []
    for k in range(3):
        fatura = cs.obter_ou_criar_fatura_aberta(cartao, 10 + k, 2026, familia.id)
        m = MovimentacaoCartao(
            descricao="Antiga", valor=Decimal("50.00"), data_compra=date(2026, 10 + k, 5),
            cartao_id=cartao.id, categoria_id=categoria_despesa.id, usuario_id=usuario.id,
            familia_id=familia.id, numero_parcelas=3, parcela_atual=k + 1,
            compra_grupo_id="g-antiga", fatura_id=fatura.id,
        )
        db.session.add(m)
        movs.append(m)
    db.session.commit()

    assert [m.parcela_atual for m in cs.parcelas_seguintes(movs[0], familia.id)] == [2, 3]
    assert [m.parcela_atual for m in cs.parcelas_seguintes(movs[1], familia.id)] == [3]
    assert cs.parcelas_seguintes(movs[2], familia.id) == []


def test_sem_grupo_nao_ha_parcelas_seguintes(db, cartao, categoria_despesa, usuario, familia):
    avulso = MovimentacaoCartao(
        descricao="Avulso", valor=Decimal("10.00"), data_compra=date(2026, 10, 1), cartao_id=cartao.id,
        categoria_id=categoria_despesa.id, usuario_id=usuario.id, familia_id=familia.id,
        numero_parcelas=1, parcela_atual=1, compra_grupo_id=None,
    )
    db.session.add(avulso)
    db.session.commit()
    assert cs.parcelas_seguintes(avulso, familia.id) == []


def test_calcular_fatura_da_parcela(db, cartao, familia):
    primeira = cs.calcular_fatura_da_parcela(cartao.id, date(2026, 10, 10), 1, familia.id)
    terceira = cs.calcular_fatura_da_parcela(cartao.id, date(2026, 10, 10), 3, familia.id)
    assert (terceira.ano * 12 + terceira.mes) - (primeira.ano * 12 + primeira.mes) == 2


# ---------------------------------------------------------------------------
# Nome e categoria seguem "esta e as próximas", como o valor
# ---------------------------------------------------------------------------
def _cadastrar_4x(cartao, categoria, usuario, familia, descricao="Compra 4x"):
    dados = cs.NovaMovimentacaoInput(
        descricao=descricao, valor=Decimal("400.00"), data_compra=date(2026, 10, 10),
        cartao_id=cartao.id, categoria_id=categoria.id, tipo_pagamento="parcelado",
        fatura_mes_ano="10-2026", tipo_valor="total", numero_parcelas=4, replicar="nao",
    )
    cs.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=familia.id)
    return MovimentacaoCartao.query.filter_by(descricao=descricao).order_by(MovimentacaoCartao.parcela_atual).all()


def _nomes(descricao_base="Compra 4x"):
    return [m.descricao for m in MovimentacaoCartao.query.order_by(MovimentacaoCartao.parcela_atual).all()]


def _editar_parcela_2(movs, cartao, categoria, descricao, proximas):
    mov = movs[1]
    dados = cs.EditarMovimentacaoInput(
        descricao=descricao, valor=Decimal("100.00"), data_compra=mov.data_compra,
        cartao_id=cartao.id, categoria_id=categoria.id, fatura_mes_ano="11-2026", alterar_proximas=proximas,
    )
    cs.atualizar_movimentacao(mov, dados, familia_id=mov.familia_id)


def test_editar_nome_sem_marcar_proximas_altera_so_esta_parcela(db, cartao, categoria_despesa, usuario, familia):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)

    _editar_parcela_2(movs, cartao, categoria_despesa, "Nome novo", proximas=False)

    assert _nomes() == ["Compra 4x", "Nome novo", "Compra 4x", "Compra 4x"]


def test_editar_nome_marcando_proximas_altera_esta_e_as_seguintes_nunca_as_anteriores(
    db, cartao, categoria_despesa, usuario, familia
):
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)

    _editar_parcela_2(movs, cartao, categoria_despesa, "Nome novo", proximas=True)

    assert _nomes() == ["Compra 4x", "Nome novo", "Nome novo", "Nome novo"]


def test_editar_categoria_segue_a_mesma_regra(db, cartao, categoria_despesa, usuario, familia):
    from app.models import Categoria

    outra = Categoria(nome="Outra categoria", tipo="despesa", familia_id=familia.id)
    db.session.add(outra)
    db.session.commit()
    movs = _cadastrar_4x(cartao, categoria_despesa, usuario, familia)

    _editar_parcela_2(movs, cartao, outra, "Compra 4x", proximas=True)

    categorias = [m.categoria_id for m in MovimentacaoCartao.query.order_by(MovimentacaoCartao.parcela_atual)]
    assert categorias == [categoria_despesa.id, outra.id, outra.id, outra.id]