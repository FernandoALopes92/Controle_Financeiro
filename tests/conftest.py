"""Configuração compartilhada dos testes automatizados.

O pytest carrega este arquivo sozinho (por causa do nome "conftest.py") e
disponibiliza cada função abaixo como uma "fixture" — um pedacinho de
cenário pronto que qualquer teste pode pedir só citando o nome dela como
argumento (veja tests/test_conta_service.py para ver isso em uso).
"""
from datetime import date
from decimal import Decimal

import pytest

from app import create_app
from app.models import db as _db, Familia, Usuario, Conta, Categoria, MeioPagamento


@pytest.fixture
def app():
    """Cria uma instância do Flask App configurada para testes: banco
    SQLite em memória (existe só enquanto o teste roda, depois some),
    criado do zero a cada teste — nunca toca no Postgres real."""
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,  # não precisamos validar token CSRF nos testes
    })

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    """Atalho para a sessão do banco (já dentro do contexto do app de teste)."""
    return _db


@pytest.fixture
def familia(db):
    """Cria uma família de teste, pronta para uso."""
    familia = Familia(nome="Família Teste")
    db.session.add(familia)
    db.session.commit()
    return familia


@pytest.fixture
def usuario(db, familia):
    """Cria um usuário de teste, pertencente à família de teste."""
    usuario = Usuario(nome="Usuário Teste", email="teste@teste.com", familia_id=familia.id)
    usuario.set_senha("senha123")
    db.session.add(usuario)
    db.session.commit()
    return usuario


@pytest.fixture
def conta(db, familia, usuario):
    """Cria uma conta de teste com saldo inicial de R$ 100."""
    conta = Conta(
        nome="Conta Teste",
        data=date(2026, 1, 1),
        saldo_inicial=Decimal("100.00"),
        saldo_atual=Decimal("100.00"),
        tipo="Conta Corrente",
        usuario_id=usuario.id,
        familia_id=familia.id,
    )
    db.session.add(conta)
    db.session.commit()
    return conta


@pytest.fixture
def cartao(db, familia, usuario):
    """Cria um cartão de crédito de teste (fecha dia 10, vence dia 20)."""
    cartao = MeioPagamento(
        nome="Cartão Teste",
        tipo="Crédito",
        limite=Decimal("1000.00"),
        fechamento_dia=10,
        vencimento_dia=20,
        usuario_id=usuario.id,
        familia_id=familia.id,
    )
    db.session.add(cartao)
    db.session.commit()
    return cartao


@pytest.fixture
def conta_destino(db, familia, usuario):
    """Segunda conta de teste, usada como destino em transferências."""
    conta = Conta(
        nome="Conta Destino",
        data=date(2026, 1, 1),
        saldo_inicial=Decimal("200.00"),
        saldo_atual=Decimal("200.00"),
        tipo="Conta Corrente",
        usuario_id=usuario.id,
        familia_id=familia.id,
    )
    db.session.add(conta)
    db.session.commit()
    return conta


@pytest.fixture
def categoria_despesa(db, familia):
    """Cria uma categoria de despesa de teste."""
    categoria = Categoria(nome="Mercado", tipo="despesa", familia_id=familia.id)
    db.session.add(categoria)
    db.session.commit()
    return categoria


@pytest.fixture
def categoria_receita(db, familia):
    """Cria uma categoria de receita de teste."""
    categoria = Categoria(nome="Salário", tipo="receita", familia_id=familia.id)
    db.session.add(categoria)
    db.session.commit()
    return categoria