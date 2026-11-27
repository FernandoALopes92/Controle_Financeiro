"""Conversão de valores monetários digitados nos formulários."""
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

# As colunas de valor são Numeric(10, 2): acima disso o banco recusa (erro 500).
VALOR_MAXIMO = Decimal("99999999.99")


def converter_valor_para_decimal(valor_str: str) -> Optional[Decimal]:
    """Converte o texto de um valor ("21.28", "21,28", "1.234,56", "R$ 10") em Decimal.

    Retorna None se o valor for inválido: vazio, texto qualquer, NaN/Infinity
    com mais de 2 casas decimais ou acima de R$ 99.999.999,99. É a ÚNICA porta de entrada de valores em
    dinheiro (cartão, contas e transferências) — antes algumas rotas usavam
    Decimal(...) direto, que aceita "NaN" e "Infinity" (um NaN gravado em um
    lançamento contaminaria o saldo da conta inteira).
    """
    if not valor_str:
        return None
    texto = valor_str.replace("R$", "").replace(" ", "").strip()
    if "," in texto:
        # a vírgula é o decimal; os pontos são separador de milhar
        texto = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", texto):
        # só pontos, todos seguidos de 3 dígitos: milhar ("1.234" -> 1234)
        texto = texto.replace(".", "")
    try:
        valor = Decimal(texto)
    except (InvalidOperation, ValueError):
        return None
    if not valor.is_finite() or valor.as_tuple().exponent < -2:
        return None
    if abs(valor) > VALOR_MAXIMO:  # ex.: "1e999" é finito, mas estoura a coluna
        return None
    return valor
