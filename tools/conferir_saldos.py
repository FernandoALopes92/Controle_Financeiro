"""
conferir_saldos.py

Confere os saldos das contas. SOMENTE LEITURA: não grava nada no banco.

O app guarda um saldo por conta (saldo_atual) e o atualiza a cada lançamento.
Este script recalcula o saldo do zero, a partir do saldo inicial e de todos os
lançamentos, e compara com o saldo guardado:

    saldo recalculado = saldo inicial
                        + receitas pagas
                        - despesas pagas (inclui pagamentos de fatura)
                        + transferências recebidas
                        - transferências enviadas

Uso (na raiz do projeto, com o .venv ativo):

    python tools/conferir_saldos.py
        confere todas as contas e mostra possíveis causas de diferença

    python tools/conferir_saldos.py --conta "Itaú" --desde 2026-10-01
        mostra, linha a linha, o que o app tem para essa conta desde a data,
        com o saldo acumulado, para você comparar com o extrato do banco
        (--conta aceita o nome ou o id)
"""

import argparse
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ZERO = Decimal("0.00")


def _dia(valor):
    """Date ou datetime -> date."""
    return valor.date() if isinstance(valor, datetime) else valor


def _fmt(valor):
    return f"{Decimal(valor):>12,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def efeitos_da_conta(conta, movimentacoes, transferencias):
    """
    Devolve a lista de efeitos no saldo da conta, como tuplas
    (data, id_ordem, descricao, delta, contado):
      contado = False para lançamentos pendentes (ainda não pagos), que não mexem no saldo.
    """
    efeitos = []
    for m in movimentacoes:
        if m.conta_id != conta.id or m.tipo not in ("receita", "despesa"):
            continue
        delta = Decimal(m.valor) if m.tipo == "receita" else -Decimal(m.valor)
        efeitos.append((_dia(m.data), m.id, m.descricao or "", delta, bool(m.pago)))
    for t in transferencias:
        nota = f" ({t.observacoes})" if t.observacoes else ""
        if t.conta_origem_id == conta.id:
            efeitos.append((_dia(t.data_transferencia), 10**9 + t.id, f"Transferência enviada{nota}", -Decimal(t.valor), True))
        if t.conta_destino_id == conta.id:
            efeitos.append((_dia(t.data_transferencia), 10**9 + t.id, f"Transferência recebida{nota}", Decimal(t.valor), True))
    return efeitos


def saldo_recalculado(conta, efeitos, antes_de=None):
    base = Decimal(conta.saldo_inicial or 0)
    for data, _, _, delta, contado in efeitos:
        if contado and (antes_de is None or data < antes_de):
            base += delta
    return base


def pendentes_vencidos(efeitos, hoje):
    """Lançamentos não pagos com data até hoje: o banco já pode ter movimentado."""
    return [e for e in efeitos if not e[4] and e[0] <= hoje]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conta", help="nome ou id da conta (para o modo extrato)")
    parser.add_argument("--desde", help="data inicial AAAA-MM-DD (para o modo extrato)")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from dotenv import load_dotenv

    load_dotenv()
    from app import create_app
    from app.models import Categoria, Conta, Movimentacao, PagamentoFatura, Transferencia

    app = create_app()
    with app.app_context():
        from sqlalchemy.engine import make_url

        url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
        print(f"🗄️  Banco: {url.host or 'local'} / {url.database}  (somente leitura)\n")

        contas = Conta.query.order_by(Conta.id).all()
        movimentacoes = Movimentacao.query.all()
        transferencias = Transferencia.query.all()
        hoje = date.today()

        # ------------------------------------------------------------------
        # Modo extrato: uma conta, linha a linha
        # ------------------------------------------------------------------
        if args.conta:
            alvo = [c for c in contas if str(c.id) == args.conta or c.nome.lower() == args.conta.lower()]
            if not alvo:
                print(f"❌ Conta '{args.conta}' não encontrada. Contas: {[f'{c.id}={c.nome}' for c in contas]}")
                return
            conta = alvo[0]
            desde = date.fromisoformat(args.desde) if args.desde else None
            efeitos = sorted(efeitos_da_conta(conta, movimentacoes, transferencias), key=lambda e: (e[0], e[1]))
            acumulado = saldo_recalculado(conta, efeitos, antes_de=desde)
            print(f"Conta: {conta.nome} (id {conta.id})")
            print(f"Saldo inicial cadastrado: R$ {_fmt(conta.saldo_inicial or 0)}")
            if desde:
                print(f"Saldo calculado pelo app ANTES de {desde:%d/%m/%Y}: R$ {_fmt(acumulado)}")
            print(f"\n{'data':<11}{'descrição':<44}{'valor':>13}  {'saldo':>13}  situação")
            for data, _, descricao, delta, contado in efeitos:
                if desde and data < desde:
                    continue
                if contado:
                    acumulado += delta
                situacao = "" if contado else "PENDENTE (não conta no saldo)"
                print(f"{data:%d/%m/%Y}  {descricao[:42]:<44}{_fmt(delta)}  {_fmt(acumulado)}  {situacao}")
            print(f"\nSaldo final calculado: R$ {_fmt(acumulado)}   |   saldo guardado: R$ {_fmt(conta.saldo_atual)}")
            return

        # ------------------------------------------------------------------
        # Modo conferência geral
        # ------------------------------------------------------------------
        print(f"{'conta':<26}{'guardado':>13}{'recalculado':>14}{'diferença':>13}")
        total_dif = 0
        resumo_pendentes = []
        for conta in contas:
            efeitos = efeitos_da_conta(conta, movimentacoes, transferencias)
            calc = saldo_recalculado(conta, efeitos)
            guardado = Decimal(conta.saldo_atual or 0)
            dif = guardado - calc
            marca = "" if dif == ZERO else "  <-- DIFERENTE"
            total_dif += dif != ZERO
            print(f"{conta.nome[:25]:<26}{_fmt(guardado)}{_fmt(calc)}{_fmt(dif)}{marca}")
            pend = pendentes_vencidos(efeitos, hoje)
            if pend:
                resumo_pendentes.append((conta, pend))

        print()
        if total_dif == 0:
            print("✅ Os saldos guardados batem com o recálculo. Se o seu banco mostra outro valor,")
            print("   a diferença está em algo que o app não tem (lançamento faltando, valor digitado")
            print("   diferente, rendimento/tarifa). Use o modo extrato para comparar linha a linha.")
        else:
            print(f"⚠️  {total_dif} conta(s) com diferença interna: o saldo guardado não corresponde aos lançamentos.")

        if resumo_pendentes:
            print("\n== Pendentes com data até hoje (não contam no saldo; o banco pode já ter movimentado) ==")
            for conta, pend in resumo_pendentes:
                efeito = sum(e[3] for e in pend)
                print(f"  {conta.nome}: {len(pend)} lançamento(s), efeito total R$ {_fmt(efeito).strip()}")
                for data, _, descricao, delta, _ in sorted(pend)[:8]:
                    print(f"      {data:%d/%m/%Y}  {descricao[:40]:<42}{_fmt(delta)}")

        # ------------------------------------------------------------------
        # Outras verificações de consistência
        # ------------------------------------------------------------------
        print("\n== Outras verificações ==")
        problemas = 0

        if hasattr(Movimentacao, "transferencia_id"):
            espelhos = defaultdict(list)
            for m in movimentacoes:
                if m.tipo == "transferencia":
                    espelhos[m.transferencia_id].append(m)
            ids_transf = {t.id for t in transferencias}
            for t in transferencias:
                linhas = espelhos.get(t.id, [])
                if len(linhas) != 2 or any(Decimal(x.valor) != Decimal(t.valor) for x in linhas):
                    problemas += 1
                    print(f"  ⚠️ Transferência {t.id} ({_dia(t.data_transferencia):%d/%m/%Y}, R$ {t.valor}): "
                          f"{len(linhas)} linha(s) espelho no extrato (esperado 2, mesmo valor)")
            for tid, linhas in espelhos.items():
                if tid not in ids_transf:
                    problemas += 1
                    print(f"  ⚠️ {len(linhas)} linha(s) de transferência apontam para a transferência {tid}, que não existe")
        else:
            print("  (linhas espelho das transferências não verificadas: o modelo não tem transferencia_id)")

        for p in PagamentoFatura.query.all():
            ligadas = [m for m in movimentacoes if m.pagamento_fatura_id == p.id]
            if len(ligadas) != 1 or Decimal(ligadas[0].valor) != Decimal(p.valor_pago) or not ligadas[0].pago:
                problemas += 1
                print(f"  ⚠️ Pagamento de fatura {p.id} (R$ {p.valor_pago}): lançamento ligado ausente, duplicado ou com outro valor")

        categorias = {c.id: c.tipo for c in Categoria.query.all()}
        for m in movimentacoes:
            if m.tipo in ("receita", "despesa") and m.categoria_id in categorias and categorias[m.categoria_id] != m.tipo:
                problemas += 1
                print(f"  ⚠️ Lançamento {m.id} '{m.descricao}': tipo '{m.tipo}' mas a categoria é '{categorias[m.categoria_id]}'")

        if problemas == 0:
            print("  ✅ Transferências, pagamentos de fatura e tipos de categoria consistentes.")


if __name__ == "__main__":
    main()