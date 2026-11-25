"""Testes de rota: isolamento entre famílias, reativação de contas/categorias
e filtros de status.

Como rodar só este arquivo:
    pytest tests/test_rotas_categorias_contas.py -v
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models import Categoria, Conta, Familia, Usuario


@pytest.fixture
def client(app, usuario):
    """Cliente de teste já logado como o usuário de teste."""
    cliente = app.test_client()
    with cliente.session_transaction() as sessao:
        sessao["_user_id"] = str(usuario.id)
        sessao["_fresh"] = True
    return cliente


@pytest.fixture
def categoria_despesa_filha(db, familia, categoria_despesa):
    filha = Categoria(nome="Feira", tipo="despesa", familia_id=familia.id, categoria_pai_id=categoria_despesa.id)
    db.session.add(filha)
    db.session.commit()
    return filha


@pytest.fixture
def categoria_de_outra_familia(db):
    outra = Familia(nome="Outra família")
    db.session.add(outra)
    db.session.commit()
    pai = Categoria(nome="Pai alheio", tipo="despesa", familia_id=outra.id)
    db.session.add(pai)
    db.session.commit()
    filha = Categoria(nome="CATEGORIA_ALHEIA", tipo="despesa", familia_id=outra.id, categoria_pai_id=pai.id)
    db.session.add(filha)
    db.session.commit()
    return filha


def test_nova_compra_cartao_nao_lista_categorias_de_outra_familia(client, categoria_despesa_filha, categoria_de_outra_familia):
    resposta = client.get("/cartao/mov_cartao/nova")

    html = resposta.get_data(as_text=True)
    assert resposta.status_code == 200
    assert "Feira" in html
    assert "CATEGORIA_ALHEIA" not in html


def test_nova_compra_cartao_nao_lista_categoria_desativada(db, client, categoria_despesa_filha):
    categoria_despesa_filha.status = False
    db.session.commit()

    html = client.get("/cartao/mov_cartao/nova").get_data(as_text=True)

    assert "Feira" not in html


def test_desativar_categoria_mostra_mensagem_de_desativada(client, categoria_despesa):
    resposta = client.post(f"/categorias/excluir/{categoria_despesa.id}", follow_redirects=True)

    html = resposta.get_data(as_text=True)
    assert "desativada com sucesso" in html
    assert "Categorias desativadas" in html  # aparece na lista para reativar


def test_reativar_categoria_volta_a_ficar_ativa(db, client, categoria_despesa):
    categoria_despesa.status = False
    db.session.commit()

    client.post(f"/categorias/reativar/{categoria_despesa.id}")

    db.session.refresh(categoria_despesa)
    assert categoria_despesa.status is True


def test_reativar_subcategoria_reativa_tambem_a_principal(db, client, categoria_despesa, categoria_despesa_filha):
    categoria_despesa.status = False
    categoria_despesa_filha.status = False
    db.session.commit()

    client.post(f"/categorias/reativar/{categoria_despesa_filha.id}")

    db.session.refresh(categoria_despesa)
    db.session.refresh(categoria_despesa_filha)
    assert categoria_despesa_filha.status is True
    assert categoria_despesa.status is True


def test_nao_reativa_categoria_de_outra_familia(client, categoria_de_outra_familia):
    categoria_de_outra_familia.status = False

    resposta = client.post(f"/categorias/reativar/{categoria_de_outra_familia.id}")

    assert resposta.status_code == 404


def test_lista_de_contas_mostra_inativa_com_botao_reativar(db, client, conta):
    conta.status = False
    db.session.commit()

    html = client.get("/contas/").get_data(as_text=True)

    assert "Conta Teste" in html
    assert "Inativo" in html
    assert f"/contas/reativar/{conta.id}" in html


def test_reativar_conta_pela_rota(db, client, conta):
    conta.status = False
    db.session.commit()

    client.post(f"/contas/reativar/{conta.id}")

    db.session.refresh(conta)
    assert conta.status is True


def test_nao_reativa_conta_de_outra_familia(db, client):
    outra = Familia(nome="Outra")
    db.session.add(outra)
    db.session.commit()
    dono = Usuario(nome="Dono", email="dono@x.com", familia_id=outra.id)
    dono.set_senha("x")
    db.session.add(dono)
    db.session.commit()
    alheia = Conta(nome="Alheia", data=date(2026, 1, 1), saldo_inicial=Decimal("0"), saldo_atual=Decimal("0"),
                   tipo="Conta Corrente", usuario_id=dono.id, familia_id=outra.id, status=False)
    db.session.add(alheia)
    db.session.commit()

    resposta = client.post(f"/contas/reativar/{alheia.id}")

    assert resposta.status_code == 404
