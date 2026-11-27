"""Leitura segura de parâmetros da URL."""
from flask import request


def int_arg(nome: str, padrao: int, minimo: int = None, maximo: int = None) -> int:
    """Lê um inteiro de request.args sem nunca estourar erro 500.

    Valor ausente, não numérico ("?ano=abc") ou fora do intervalo
    [minimo, maximo] devolve o padrão.
    """
    bruto = request.args.get(nome)
    try:
        valor = int(bruto)
    except (TypeError, ValueError):
        return padrao
    if minimo is not None and valor < minimo:
        return padrao
    if maximo is not None and valor > maximo:
        return padrao
    return valor
