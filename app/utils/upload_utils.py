"""Utilitários para upload de imagens de logo (contas e cartões).

Antes dessa extração, a mesma lógica (validar extensão, gerar nome único,
salvar no disco) estava copiada em 4 lugares: contas.py (criar/editar) e
meios_pagamento.py (criar/editar).

Segurança: além da extensão (que o usuário controla), confere o CONTEÚDO do
arquivo (assinatura PNG/JPEG/WEBP) e recusa SVG com script embutido.
"""
import os
import re
import uuid
from typing import Optional

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

# Extensões aceitas para upload de logos (contas e cartões)
EXTENSOES_LOGO_PERMITIDAS = {"png", "jpg", "jpeg", "svg", "webp"}
TAMANHO_MAXIMO_LOGO = 2 * 1024 * 1024  # 2 MB

# Marcas de SVG que executam código ou carregam coisas de fora
_SVG_PERIGOSO = re.compile(
    r"<\s*script|<\s*foreignobject|<\s*iframe|<\s*embed|<\s*object|<!entity|"
    r"javascript\s*:|data\s*:\s*text/html|\son[a-z]+\s*=",
    re.IGNORECASE,
)


def extensao_logo_permitida(nome_arquivo: str) -> bool:
    """Verifica se o arquivo enviado tem uma extensão de imagem permitida."""
    if "." not in nome_arquivo:
        return False
    extensao = nome_arquivo.rsplit(".", 1)[1].lower()
    return extensao in EXTENSOES_LOGO_PERMITIDAS


class LogoInvalidoError(Exception):
    """Levantada quando o arquivo enviado não é uma imagem de logo válida."""


def _conteudo_confere_com_extensao(conteudo: bytes, extensao: str) -> bool:
    if extensao == "png":
        return conteudo.startswith(b"\x89PNG\r\n\x1a\n")
    if extensao in ("jpg", "jpeg"):
        return conteudo.startswith(b"\xff\xd8\xff")
    if extensao == "webp":
        return conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP"
    if extensao == "svg":
        try:
            texto = conteudo.decode("utf-8-sig")
        except UnicodeDecodeError:
            return False
        return "<svg" in texto.lower() and not _SVG_PERIGOSO.search(texto)
    return False


def salvar_logo(logo_file: Optional[FileStorage], upload_path: str) -> Optional[str]:
    """Valida, gera um nome único e salva um arquivo de logo no disco.

    Retorna o nome do arquivo salvo, ou None se nenhum arquivo foi enviado.
    Levanta LogoInvalidoError se a extensão/conteúdo não forem de uma imagem válida.
    """
    if not logo_file or logo_file.filename == "":
        return None

    if not extensao_logo_permitida(logo_file.filename):
        raise LogoInvalidoError("Arquivo de logo inválido. Use png, jpg, jpeg, svg ou webp.")

    extensao = logo_file.filename.rsplit(".", 1)[1].lower()

    conteudo = logo_file.stream.read(TAMANHO_MAXIMO_LOGO + 1)
    logo_file.stream.seek(0)
    if len(conteudo) > TAMANHO_MAXIMO_LOGO:
        raise LogoInvalidoError("A logo é grande demais. O limite é 2 MB.")
    if not _conteudo_confere_com_extensao(conteudo, extensao):
        raise LogoInvalidoError("O conteúdo do arquivo não é uma imagem válida (ou o SVG contém código não permitido).")

    # secure_filename pode apagar nomes só com acentos/ideogramas ("日本.png" -> "png"),
    # por isso a extensão vem da validação acima e o nome-base tem um padrão.
    nome_base = os.path.splitext(secure_filename(logo_file.filename))[0]
    if not nome_base or nome_base.lower() == extensao:
        nome_base = "logo"
    codigo_unico = uuid.uuid4().hex[:8]
    filename = f"{nome_base}_{codigo_unico}.{extensao}"

    os.makedirs(upload_path, exist_ok=True)
    logo_file.save(os.path.join(upload_path, filename))

    return filename
