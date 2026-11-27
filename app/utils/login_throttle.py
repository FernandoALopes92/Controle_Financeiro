"""Limite de tentativas de login (proteção contra força bruta).

Guarda as falhas recentes em memória, por (IP + e-mail) e por IP. Sem
dependências extras. Observações:
- a contagem é por processo: com vários workers (gunicorn -w 4) o limite
  efetivo é multiplicado pelo número de workers. Para um app familiar é
  suficiente; se um dia precisar de rigor, trocar por Flask-Limiter + Redis;
- atrás de um proxy/reverse proxy, configure ProxyFix para request.remote_addr
  ser o IP real do visitante (senão todo mundo parece vir do mesmo IP).
"""
import time
from collections import defaultdict, deque
from threading import Lock

MAX_FALHAS_POR_EMAIL = 5      # (IP + e-mail) dentro da janela
MAX_FALHAS_POR_IP = 20        # qualquer e-mail, mesmo IP, dentro da janela
JANELA_SEGUNDOS = 15 * 60

_falhas = defaultdict(deque)
_lock = Lock()


def _chaves(email, ip):
    return (f"ip:{ip}", f"ip-email:{ip}|{(email or '').strip().lower()}")


def _limpar_expiradas(fila, agora):
    while fila and agora - fila[0] > JANELA_SEGUNDOS:
        fila.popleft()


def segundos_restantes(email, ip, agora=None) -> int:
    """0 se pode tentar; senão, quantos segundos faltam para liberar."""
    agora = time.time() if agora is None else agora
    chave_ip, chave_email = _chaves(email, ip)
    espera = 0
    with _lock:
        for chave, limite in ((chave_ip, MAX_FALHAS_POR_IP), (chave_email, MAX_FALHAS_POR_EMAIL)):
            fila = _falhas.get(chave)
            if not fila:
                continue
            _limpar_expiradas(fila, agora)
            if len(fila) >= limite:
                espera = max(espera, int(fila[0] + JANELA_SEGUNDOS - agora) + 1)
        if len(_falhas) > 10000:  # evita crescer sem limite
            for chave in [c for c, f in _falhas.items() if not f or agora - f[-1] > JANELA_SEGUNDOS]:
                del _falhas[chave]
    return espera


def registrar_falha(email, ip, agora=None) -> None:
    agora = time.time() if agora is None else agora
    with _lock:
        for chave in _chaves(email, ip):
            _falhas[chave].append(agora)


def limpar(email, ip) -> None:
    """Login bem-sucedido: zera o contador do par IP+e-mail."""
    with _lock:
        _falhas.pop(_chaves(email, ip)[1], None)


def resetar_tudo() -> None:
    with _lock:
        _falhas.clear()
