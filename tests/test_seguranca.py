"""Testes de segurança: limite de tentativas de login, logout por POST, cookies,
cabeçalhos, upload de logos, SECRET_KEY obrigatória, parâmetros de URL e valores
monetários (NaN/Infinity).

Como rodar só este arquivo:
    pytest tests/test_seguranca.py -v
"""
import io
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.datastructures import FileStorage

from app import create_app
from app.models import Conta, Movimentacao
from app.services import movimentacao_service as mov_service
from app.utils import login_throttle
from app.utils.upload_utils import LogoInvalidoError, salvar_logo
from app.utils.valores import converter_valor_para_decimal

PNG_MINIMO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
SVG_OK = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'


@pytest.fixture(autouse=True)
def zerar_limite_de_login():
    login_throttle.resetar_tudo()
    yield
    login_throttle.resetar_tudo()


@pytest.fixture
def client(app, usuario):
    """Cliente já logado."""
    cliente = app.test_client()
    with cliente.session_transaction() as sessao:
        sessao["_user_id"] = str(usuario.id)
        sessao["_fresh"] = True
    return cliente


def _tentar_login(cliente, email, senha):
    return cliente.post("/auth/login", data={"email": email, "senha": senha})


# ---------------------------------------------------------------------------
# Login: limite de tentativas
# ---------------------------------------------------------------------------
def test_login_correto_funciona(app, usuario):
    resposta = _tentar_login(app.test_client(), "teste@teste.com", "senha123")

    assert resposta.status_code == 302
    assert "/dashboard" in resposta.headers["Location"]


def test_apos_5_erros_bloqueia_ate_com_senha_certa(app, usuario):
    cliente = app.test_client()
    for _ in range(5):
        assert _tentar_login(cliente, "teste@teste.com", "errada").status_code == 200

    resposta = _tentar_login(cliente, "teste@teste.com", "senha123")

    assert resposta.status_code == 429
    assert "Muitas tentativas" in resposta.get_data(as_text=True)


def test_login_correto_zera_o_contador_de_erros(app, usuario):
    cliente = app.test_client()
    for _ in range(4):
        _tentar_login(cliente, "teste@teste.com", "errada")
    assert _tentar_login(cliente, "teste@teste.com", "senha123").status_code == 302

    # contador zerado: mais 4 erros não bloqueiam
    for _ in range(4):
        assert _tentar_login(cliente, "teste@teste.com", "errada").status_code == 200


def test_bloqueio_de_um_email_nao_bloqueia_outro_email(app, usuario):
    cliente = app.test_client()
    for _ in range(5):
        _tentar_login(cliente, "alguem@teste.com", "errada")

    assert _tentar_login(cliente, "teste@teste.com", "senha123").status_code == 302


def test_bloqueio_libera_depois_da_janela():
    agora = 1_000_000.0
    for _ in range(5):
        login_throttle.registrar_falha("a@a.com", "1.2.3.4", agora=agora)

    assert login_throttle.segundos_restantes("a@a.com", "1.2.3.4", agora=agora + 10) > 0
    assert login_throttle.segundos_restantes("a@a.com", "1.2.3.4", agora=agora + login_throttle.JANELA_SEGUNDOS + 1) == 0


def test_limite_por_ip_vale_mesmo_trocando_de_email():
    for i in range(login_throttle.MAX_FALHAS_POR_IP):
        login_throttle.registrar_falha(f"email{i}@x.com", "9.9.9.9")

    assert login_throttle.segundos_restantes("novo@x.com", "9.9.9.9") > 0


def test_login_sem_campos_nao_quebra(app):
    resposta = app.test_client().post("/auth/login", data={})

    assert resposta.status_code == 200
    assert "incorretos" in resposta.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Logout por POST
# ---------------------------------------------------------------------------
def test_logout_por_get_nao_e_permitido(client):
    assert client.get("/auth/logout").status_code == 405


def test_logout_por_post_desloga(client):
    resposta = client.post("/auth/logout")

    assert resposta.status_code == 302
    assert "/auth/login" in resposta.headers["Location"]
    # depois de sair, uma página protegida manda para o login
    assert client.get("/dashboard").status_code == 302


def test_paginas_tem_formulario_de_logout_e_link_sair(client):
    html = client.get("/contas/").get_data(as_text=True)

    assert 'id="logoutForm"' in html
    assert "data-logout" in html
    assert 'href="/auth/logout"' not in html


# ---------------------------------------------------------------------------
# Cookies e cabeçalhos
# ---------------------------------------------------------------------------
def test_cookie_de_sessao_e_httponly_e_samesite_lax(app, usuario):
    resposta = _tentar_login(app.test_client(), "teste@teste.com", "senha123")

    cookie = resposta.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_cookie_secure_so_liga_pela_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "1")
    app_seguro = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    assert app_seguro.config["SESSION_COOKIE_SECURE"] is True

    monkeypatch.delenv("SESSION_COOKIE_SECURE")
    app_local = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    assert app_local.config["SESSION_COOKIE_SECURE"] is False


def test_cabecalhos_de_seguranca_nas_respostas(app):
    resposta = app.test_client().get("/auth/login")

    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "Referrer-Policy" in resposta.headers


def test_svg_estatico_sai_com_csp_sandbox(app):
    resposta = app.test_client().get("/static/logos/contas/Itau.svg")

    assert resposta.status_code == 200
    assert "sandbox" in resposta.headers["Content-Security-Policy"]


def test_sem_secret_key_o_app_nao_inicia_fora_dos_testes(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})


# ---------------------------------------------------------------------------
# Upload de logos
# ---------------------------------------------------------------------------
def _arquivo(nome, conteudo):
    return FileStorage(stream=io.BytesIO(conteudo), filename=nome)


def test_png_valido_e_salvo(tmp_path):
    nome = salvar_logo(_arquivo("banco.png", PNG_MINIMO), str(tmp_path))

    assert nome.endswith(".png")
    assert (tmp_path / nome).exists()


def test_svg_sem_script_e_aceito(tmp_path):
    assert salvar_logo(_arquivo("banco.svg", SVG_OK), str(tmp_path)).endswith(".svg")


@pytest.mark.parametrize(
    "svg",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><a href="javascript:alert(1)"><rect/></a></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><div/></foreignObject></svg>',
    ],
)
def test_svg_com_codigo_e_recusado(tmp_path, svg):
    with pytest.raises(LogoInvalidoError):
        salvar_logo(_arquivo("mal.svg", svg), str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_arquivo_que_nao_e_imagem_com_extensao_png_e_recusado(tmp_path):
    with pytest.raises(LogoInvalidoError):
        salvar_logo(_arquivo("falso.png", b"<html><script>alert(1)</script></html>"), str(tmp_path))


def test_logo_maior_que_2mb_e_recusada(tmp_path):
    grande = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024 + 10)

    with pytest.raises(LogoInvalidoError, match="2 MB"):
        salvar_logo(_arquivo("grande.png", grande), str(tmp_path))


def test_nome_so_com_ideogramas_continua_com_extensao(tmp_path):
    """secure_filename("日本.png") vira "png": antes o arquivo era salvo sem extensão."""
    nome = salvar_logo(_arquivo("日本.png", PNG_MINIMO), str(tmp_path))

    assert nome.startswith("logo_") and nome.endswith(".png")


def test_requisicao_gigante_e_barrada_pelo_limite_global(client):
    corpo = {"nome": "X", "logo": (io.BytesIO(b"\x00" * (5 * 1024 * 1024)), "grande.png")}

    resposta = client.post("/contas/", data=corpo, content_type="multipart/form-data")

    assert resposta.status_code == 302  # volta ao dashboard com aviso, sem estourar erro


# ---------------------------------------------------------------------------
# Parâmetros da URL
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("query", ["ano=abc&mes=xyz", "ano=99999999999999999999", "mes=99", "mes=-3", "ano=&mes="])
def test_cartao_com_parametros_invalidos_nao_da_erro_500(client, query):
    assert client.get(f"/cartao/mov_cartao?{query}").status_code == 200


# ---------------------------------------------------------------------------
# Valores monetários: NaN/Infinity nunca entram
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("texto", ["NaN", "nan", "Infinity", "-Infinity", "sNaN", "1e999", "100000000", "10,123", "abc", "", None])
def test_conversor_recusa_valores_perigosos_ou_invalidos(texto):
    assert converter_valor_para_decimal(texto) is None


@pytest.mark.parametrize("texto, esperado", [("21.28", "21.28"), ("21,28", "21.28"), ("1.234,56", "1234.56"), ("R$ 10", "10"), ("99999999.99", "99999999.99")])
def test_conversor_aceita_formatos_brasileiros(texto, esperado):
    assert converter_valor_para_decimal(texto) == Decimal(esperado)


def _post_movimentacao(client, conta, categoria, valor):
    return client.post("/movimentacoes/nova", data={
        "data": "2026-07-01", "descricao": "Teste", "categoria_id": categoria.id,
        "valor": valor, "conta_id": conta.id, "pago": "true", "replicar": "nao",
    })


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "0", "-5", "abc"])
def test_rota_de_movimentacao_recusa_valor_invalido_e_saldo_fica_intacto(db, client, conta, categoria_despesa, valor):
    _post_movimentacao(client, conta, categoria_despesa, valor)

    db.session.refresh(conta)
    assert Movimentacao.query.count() == 0
    assert conta.saldo_atual == Decimal("100.00")


def test_rota_de_movimentacao_aceita_virgula(db, client, conta, categoria_despesa):
    _post_movimentacao(client, conta, categoria_despesa, "21,28")

    mov = Movimentacao.query.one()
    assert mov.valor == Decimal("21.28")


def test_service_recusa_nan_mesmo_que_a_rota_deixasse_passar(db, conta, categoria_despesa, usuario):
    dados = mov_service.NovaMovimentacaoInput(
        data=date(2026, 7, 1), descricao="X", categoria_id=categoria_despesa.id,
        valor=Decimal("NaN"), conta_id=conta.id, pago=True, replicar="nao",
    )

    with pytest.raises(mov_service.ValorInvalidoError):
        mov_service.criar_movimentacao(dados, usuario_id=usuario.id, familia_id=conta.familia_id)

    db.session.refresh(conta)
    assert conta.saldo_atual == Decimal("100.00")


def test_transferencia_com_nan_e_recusada_pela_rota(db, client, conta, familia, usuario):
    destino = Conta(nome="Destino", data=date(2026, 1, 1), saldo_inicial=Decimal("0"), saldo_atual=Decimal("0"),
                    tipo="Conta Corrente", usuario_id=usuario.id, familia_id=familia.id)
    db.session.add(destino)
    db.session.commit()

    client.post("/transferencias/nova", data={
        "origem_id": conta.id, "destino_id": destino.id, "valor": "NaN", "data": "2026-07-01",
    })

    db.session.refresh(conta)
    db.session.refresh(destino)
    assert conta.saldo_atual == Decimal("100.00")
    assert destino.saldo_atual == Decimal("0")
