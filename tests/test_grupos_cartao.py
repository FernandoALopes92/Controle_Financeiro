"""Testes dos grupos de lançamentos de cartão (parcelados e recorrentes):
exclusão de "todas as parcelas" e busca do grupo da parcela anterior.

Como rodar só este arquivo:
    pytest tests/test_grupos_cartao.py -v
"""
from datetime import date
from decimal import Decimal

from app.models import MovimentacaoCartao
from app.services import cartao_service


def _mov(db, cartao, categoria, usuario, familia, descricao, parcela, total, grupo=None, cartao_id=None):
    mov = MovimentacaoCartao(
        descricao=descricao, valor=Decimal("10.00"), data_compra=date(2026, 7, 5),
        cartao_id=cartao_id or cartao.id, categoria_id=categoria.id, usuario_id=usuario.id,
        familia_id=familia.id, numero_parcelas=total, parcela_atual=parcela, compra_grupo_id=grupo,
    )
    db.session.add(mov)
    db.session.commit()
    return mov


# ---------------------------------------------------------------------------
# Excluir "todas as parcelas"
# ---------------------------------------------------------------------------
def test_excluir_todas_sem_grupo_apaga_ao_menos_o_proprio_lancamento(db, cartao, categoria_despesa, usuario, familia):
    mov = _mov(db, cartao, categoria_despesa, usuario, familia, "Boné", 3, 3, grupo=None)

    cartao_service.excluir_movimentacao(mov, familia_id=familia.id, excluir_todas=True)

    assert MovimentacaoCartao.query.count() == 0


def test_excluir_todas_com_grupo_apaga_a_serie_inteira_e_so_ela(db, cartao, categoria_despesa, usuario, familia):
    p1 = _mov(db, cartao, categoria_despesa, usuario, familia, "Senac", 1, 3, grupo="g1")
    _mov(db, cartao, categoria_despesa, usuario, familia, "Senac", 2, 3, grupo="g1")
    _mov(db, cartao, categoria_despesa, usuario, familia, "Senac", 3, 3, grupo="g1")
    _mov(db, cartao, categoria_despesa, usuario, familia, "Outra compra", 1, 1, grupo=None)

    cartao_service.excluir_movimentacao(p1, familia_id=familia.id, excluir_todas=True)

    restantes = MovimentacaoCartao.query.all()
    assert [m.descricao for m in restantes] == ["Outra compra"]


# ---------------------------------------------------------------------------
# Grupo da parcela anterior (usado pela importação do Excel)
# ---------------------------------------------------------------------------
def test_acha_o_grupo_da_parcela_anterior(db, cartao, categoria_despesa, usuario, familia):
    _mov(db, cartao, categoria_despesa, usuario, familia, "Senac 02/12", 2, 12, grupo="g-senac")

    grupo = cartao_service.obter_grupo_da_parcela_anterior(familia.id, "Senac", 12, 3)

    assert grupo == "g-senac"


def test_devolve_none_quando_nao_ha_parcela_anterior(db, cartao, categoria_despesa, usuario, familia):
    assert cartao_service.obter_grupo_da_parcela_anterior(familia.id, "Senac", 12, 3) is None


def test_ignora_grupo_que_ja_tem_a_parcela(db, cartao, categoria_despesa, usuario, familia):
    # compra A (grupo gA) já tem a parcela 3; compra B (grupo gB) ainda está na 2
    _mov(db, cartao, categoria_despesa, usuario, familia, "Ultrafarma", 2, 3, grupo="gA")
    _mov(db, cartao, categoria_despesa, usuario, familia, "Ultrafarma", 3, 3, grupo="gA")
    _mov(db, cartao, categoria_despesa, usuario, familia, "Ultrafarma", 2, 3, grupo="gB")

    grupo = cartao_service.obter_grupo_da_parcela_anterior(familia.id, "Ultrafarma", 3, 3)

    assert grupo == "gB"


def test_acha_o_grupo_mesmo_com_troca_de_cartao(db, cartao, categoria_despesa, usuario, familia):
    from app.models import MeioPagamento

    outro = MeioPagamento(nome="Outro cartão", tipo="Crédito", limite=Decimal("500.00"),
                          fechamento_dia=5, vencimento_dia=15, usuario_id=usuario.id, familia_id=familia.id)
    db.session.add(outro)
    db.session.commit()
    _mov(db, cartao, categoria_despesa, usuario, familia, "Espaço Laser", 4, 16, grupo="g-laser")

    # a parcela 5 veio no outro cartão, mas é a mesma série
    grupo = cartao_service.obter_grupo_da_parcela_anterior(familia.id, "Espaço Laser", 16, 5)

    assert grupo == "g-laser"