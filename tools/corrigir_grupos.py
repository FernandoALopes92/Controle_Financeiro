"""
corrigir_grupos.py

Preenche o compra_grupo_id das movimentações de cartão que vieram do
importar_excel.py / gerar_parcelas_futuras.py e ficaram sem grupo.

Sem grupo, o "atualizar esta e as próximas" não encontra as parcelas seguintes.

Uso (na raiz do projeto, com o .venv ativo):

    python tools/corrigir_grupos.py                  # só mostra o que faria
    python tools/corrigir_grupos.py --aplicar        # grava os grupos de parcelados
    python tools/corrigir_grupos.py --juntar "349,350,351,352"            # mostra
    python tools/corrigir_grupos.py --juntar "349,350,351,352" --aplicar  # grava

    python tools/corrigir_grupos.py --anexar "297" --ao-grupo-de 316            # mostra
    python tools/corrigir_grupos.py --anexar "297" --ao-grupo-de 316 --aplicar  # grava
    python tools/corrigir_grupos.py --listar                                    # lista os grupos

--anexar coloca lançamentos SEM grupo no grupo que o lançamento de referência já tem.

No PowerShell, deixe os ids entre aspas (a vírgula tem outro significado lá).
O banco é PostgreSQL: faça um backup (pg_dump ou o backup do seu provedor)
ANTES de usar --aplicar. A gravação é uma única transação: ou grava tudo, ou nada.
"""

import argparse
import re
import sys
import unicodedata
import uuid
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


def normalizar(descricao):
    """'Pague menos 01/02' -> 'pague menos' | 'Faculdade - ' -> 'faculdade'."""
    texto = unicodedata.normalize("NFKD", descricao or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"\s*\(?\d{1,2}\s*/\s*\d{1,2}\)?\s*$", "", texto)  # 01/02 ou (1/3) no fim
    texto = re.sub(r"[\s\-–:]+$", "", texto)  # traços e espaços no fim
    return re.sub(r"\s+", " ", texto).strip()


def agrupar_parcelados(movs):
    """
    Junta as parcelas de uma mesma compra: mesma família, cartão, descrição
    (sem o '01/02') e total de parcelas.

    Retorna (grupos, ambiguos, isoladas):
      grupos    -> parcelas distintas, seguro de agrupar
      ambiguos  -> a mesma parcela aparece 2x (compras diferentes com o mesmo nome)
      isoladas  -> só uma parcela encontrada; nada a agrupar
    """
    por_chave = defaultdict(list)
    for m in movs:
        if (m.numero_parcelas or 1) > 1:
            chave = (m.familia_id, m.cartao_id, normalizar(m.descricao), m.numero_parcelas)
            por_chave[chave].append(m)

    grupos, ambiguos, isoladas = [], [], []
    for chave, itens in por_chave.items():
        parcelas = [m.parcela_atual for m in itens]
        if len(itens) == 1:
            isoladas.append((chave, itens))
        elif len(set(parcelas)) != len(parcelas):
            ambiguos.append((chave, sorted(itens, key=lambda m: (m.parcela_atual, m.id))))
        else:
            grupos.append((chave, sorted(itens, key=lambda m: m.parcela_atual)))
    return grupos, ambiguos, isoladas


def candidatas_recorrentes(movs):
    """
    Lançamentos de 1 parcela que PARECEM recorrentes: mesma descrição, mesmo
    valor e cartão, pelo menos 3 vezes, no máximo uma por mês.
    É só uma sugestão: quem confirma é você, com --juntar.
    """
    por_chave = defaultdict(list)
    for m in movs:
        if (m.numero_parcelas or 1) == 1 and Decimal(m.valor) > 0:
            chave = (m.familia_id, m.cartao_id, normalizar(m.descricao), Decimal(m.valor))
            por_chave[chave].append(m)

    candidatas = []
    for chave, itens in por_chave.items():
        meses = [(m.data_compra.year, m.data_compra.month) for m in itens]
        if len(itens) >= 3 and len(set(meses)) == len(meses):
            candidatas.append((chave, sorted(itens, key=lambda m: m.data_compra)))
    return candidatas


def validar_anexo(orfas, ids, referencia):
    """Devolve uma mensagem de erro, ou None se pode anexar."""
    if referencia is None or not referencia.compra_grupo_id:
        return "O lançamento de referência não existe ou não tem grupo."
    if len(orfas) != len(ids):
        return "Algum dos ids informados não existe."
    if any(m.familia_id != referencia.familia_id for m in orfas):
        return "Há ids de outra família."
    com_grupo = [m.id for m in orfas if m.compra_grupo_id]
    if com_grupo:
        return f"Estes ids já têm grupo, nada foi alterado: {com_grupo}"
    return None


def _linha(m):
    return f"    id {m.id:<5} {m.data_compra}  {m.descricao!r}  R$ {m.valor}  parcela {m.parcela_atual}/{m.numero_parcelas}  cartão {m.cartao_id}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="grava no banco (sem isso, só mostra)")
    parser.add_argument("--juntar", nargs="+", help='ids para colocar no mesmo grupo, ex.: "349,350,351"')
    parser.add_argument("--anexar", nargs="+", help='ids SEM grupo para anexar a um grupo existente, ex.: "297"')
    parser.add_argument("--ao-grupo-de", dest="ao_grupo_de", type=int, help="id de um lançamento que já está no grupo desejado")
    parser.add_argument("--listar", action="store_true", help="lista os grupos existentes")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from dotenv import load_dotenv

    load_dotenv()
    from app import create_app
    from app.models import MovimentacaoCartao, db

    app = create_app()
    with app.app_context():
        if args.listar:
            com_grupo = MovimentacaoCartao.query.filter(MovimentacaoCartao.compra_grupo_id.isnot(None)).all()
            por_grupo = defaultdict(list)
            for m in com_grupo:
                por_grupo[m.compra_grupo_id].append(m)
            series = {g: itens for g, itens in por_grupo.items() if len(itens) >= 2}
            avulsos = len(por_grupo) - len(series)
            print(f"Grupos com 2 ou mais lançamentos: {len(series)} (e {avulsos} grupos de 1 lançamento)\n")
            for g, itens in sorted(series.items(), key=lambda kv: (kv[1][0].descricao or "").lower()):
                itens.sort(key=lambda m: (m.data_compra, m.id))
                print(f"  {itens[0].descricao!r}: {len(itens)} lançamentos, ids {[m.id for m in itens]}")
            return

        if args.anexar:
            if not args.ao_grupo_de:
                print("❌ Informe --ao-grupo-de com o id de um lançamento que já tem o grupo.")
                return
            ids = sorted({int(x) for token in args.anexar for x in token.split(",") if x.strip()})
            referencia = db.session.get(MovimentacaoCartao, args.ao_grupo_de)
            orfas = MovimentacaoCartao.query.filter(MovimentacaoCartao.id.in_(ids)).all()
            erro = validar_anexo(orfas, ids, referencia)
            if erro:
                print("❌", erro)
                return
            do_grupo = MovimentacaoCartao.query.filter_by(compra_grupo_id=referencia.compra_grupo_id).all()
            print(f"Grupo de {referencia.descricao!r} (hoje com {len(do_grupo)} lançamentos). Serão anexados:")
            for m in orfas:
                print(_linha(m))
            if args.aplicar:
                for m in orfas:
                    m.compra_grupo_id = referencia.compra_grupo_id
                db.session.commit()
                print(f"✅ {len(orfas)} lançamento(s) anexado(s). O grupo agora tem {len(do_grupo) + len(orfas)}.")
            else:
                print("\n(simulação) Rode de novo com --aplicar para gravar.")
            return

        if args.juntar:
            ids = sorted({int(x) for token in args.juntar for x in token.split(",") if x.strip()})
            movs = MovimentacaoCartao.query.filter(MovimentacaoCartao.id.in_(ids)).all()
            if len(ids) < 2 or len(movs) != len(ids):
                print("❌ Informe pelo menos 2 ids e confira se todos existem.")
                return
            if len({m.familia_id for m in movs}) != 1:
                print("❌ Os ids são de famílias diferentes.")
                return
            com_grupo = [m for m in movs if m.compra_grupo_id]
            if com_grupo:
                print("❌ Estes ids já têm grupo, nada foi alterado:")
                for m in com_grupo:
                    print(_linha(m))
                return
            print("Serão colocados no mesmo grupo:")
            for m in sorted(movs, key=lambda m: m.data_compra):
                print(_linha(m))
            if args.aplicar:
                grupo = str(uuid.uuid4())
                for m in movs:
                    m.compra_grupo_id = grupo
                db.session.commit()
                print(f"✅ Grupo {grupo} gravado em {len(movs)} lançamentos.")
            else:
                print("\n(simulação) Rode de novo com --aplicar para gravar.")
            return

        sem_grupo = MovimentacaoCartao.query.filter(MovimentacaoCartao.compra_grupo_id.is_(None)).all()
        grupos, ambiguos, isoladas = agrupar_parcelados(sem_grupo)
        recorrentes = candidatas_recorrentes(sem_grupo)

        print(f"Lançamentos sem grupo: {len(sem_grupo)}\n")

        print(f"== PARCELADOS que podem ser agrupados: {len(grupos)} compras ==")
        for (_, cartao, base, total), itens in grupos:
            print(f"  {base!r} em {total}x (cartão {cartao}): {len(itens)} parcelas, ids {[m.id for m in itens]}")

        print(f"\n== AMBÍGUOS (mesma parcela repetida, não agrupo sozinho): {len(ambiguos)} ==")
        for (_, cartao, base, total), itens in ambiguos:
            print(f"  {base!r} em {total}x (cartão {cartao}):")
            for m in itens:
                print(_linha(m))

        print(f"\n== ISOLADAS (só uma parcela achada, vale conferir): {len(isoladas)} ==")
        for _, itens in isoladas:
            print(_linha(itens[0]))

        print(f"\n== POSSÍVEIS RECORRENTES (confirme e use --juntar): {len(recorrentes)} ==")
        for (_, cartao, base, valor), itens in recorrentes:
            print(f"  {base!r} R$ {valor} (cartão {cartao}): --juntar \"{','.join(str(m.id) for m in itens)}\"")

        if args.aplicar:
            for _, itens in grupos:
                grupo = str(uuid.uuid4())
                for m in itens:
                    m.compra_grupo_id = grupo
            db.session.commit()
            print(f"\n✅ {len(grupos)} compras parceladas agrupadas.")
        else:
            print("\n(simulação) Nada foi gravado. Use --aplicar para gravar os PARCELADOS.")


if __name__ == "__main__":
    main()