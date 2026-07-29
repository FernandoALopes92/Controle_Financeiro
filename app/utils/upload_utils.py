"""Utilitários para upload de imagens de logo (contas e cartões).

Antes dessa extração, a mesma lógica (validar extensão, gerar nome único,
salvar no disco) estava copiada em 4 lugares: contas.py (criar/editar) e
meios_pagamento.py (criar/editar).
"""
import os
import uuid
from typing import Optional

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

# Extensões aceitas para upload de logos (contas e cartões)
EXTENSOES_LOGO_PERMITIDAS = {"png", "jpg", "jpeg", "svg", "webp"}


def extensao_logo_permitida(nome_arquivo: str) -> bool:
    """Verifica se o arquivo enviado tem uma extensão de imagem permitida."""
    if "." not in nome_arquivo:
        return False
    extensao = nome_arquivo.rsplit(".", 1)[1].lower()
    return extensao in EXTENSOES_LOGO_PERMITIDAS


class LogoInvalidoError(Exception):
    """Levantada quando o arquivo enviado não é uma extensão de imagem permitida."""


def salvar_logo(logo_file: Optional[FileStorage], upload_path: str) -> Optional[str]:
    """Valida, gera um nome único e salva um arquivo de logo no disco.

    Retorna o nome do arquivo salvo, ou None se nenhum arquivo foi enviado.
    Levanta LogoInvalidoError se a extensão não for permitida.
    """
    if not logo_file or logo_file.filename == "":
        return None

    if not extensao_logo_permitida(logo_file.filename):
        raise LogoInvalidoError("Arquivo de logo inválido. Use png, jpg, jpeg, svg ou webp.")

    nome_original = secure_filename(logo_file.filename)
    nome_base, extensao = os.path.splitext(nome_original)
    codigo_unico = uuid.uuid4().hex[:8]
    filename = f"{nome_base}_{codigo_unico}{extensao}"

    os.makedirs(upload_path, exist_ok=True)
    logo_file.save(os.path.join(upload_path, filename))

    return filename