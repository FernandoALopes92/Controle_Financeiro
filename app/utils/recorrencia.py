"""Opções de recorrência (conta/compra fixa clonada para os meses seguintes).

Antes só existia "3_meses", comparado direto nos services. Agora o valor do
formulário é "<N>_meses" e este módulo é a única fonte da verdade: para
oferecer outra duração basta incluí-la em OPCOES_RECORRENCIA e nos templates.
"""

# valor enviado pelo formulário -> quantidade de meses clonados à frente
OPCOES_RECORRENCIA = {
    "3_meses": 3,
    "6_meses": 6,
    "12_meses": 12,
}


def meses_da_recorrencia(replicar) -> int:
    """Quantos meses futuros devem ser clonados (0 = não recorrente ou valor desconhecido)."""
    return OPCOES_RECORRENCIA.get(str(replicar or "").strip(), 0)
