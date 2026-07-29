from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from sqlalchemy import func, not_, or_
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from app.models import db, Movimentacao, Categoria, MovimentacaoCartao, Fatura, MeioPagamento, Conta, OrcamentoMensal
from app.utils.db_utils import filtrar_por_mes_ano, get_contas, get_categorias, get_meios_pagamento
from app.routes.cartao import gerar_cor_pastel_por_nome

main_bp = Blueprint('main', __name__)


# ---------------------------------------------------------------------------
# Funções auxiliares — cada uma monta uma seção do dashboard.
# São só leitura (nenhuma escreve no banco), por isso ficam aqui e não em
# app/services/: não protegem nenhuma regra de negócio, só organizam a
# montagem dos dados que a view precisa.
# ---------------------------------------------------------------------------

def _resolver_saudacao(hora: int) -> str:
    if hora < 12:
        return "Bom dia"
    elif hora < 18:
        return "Boa tarde"
    return "Boa noite"


def _resolver_filtro_periodo(hoje, anos_validos):
    """Lê mes/ano da URL, caindo no mês/ano atual se vier algo inválido ou ausente."""
    try:
        mes_filtro = int(request.args.get('mes', hoje.month))
        ano_filtro = int(request.args.get('ano', hoje.year))
        if not (1 <= mes_filtro <= 12):
            mes_filtro = hoje.month
        if ano_filtro not in anos_validos:
            ano_filtro = hoje.year
    except (ValueError, TypeError):
        mes_filtro = hoje.month
        ano_filtro = hoje.year
    return mes_filtro, ano_filtro


def _obter_meta_percentual(familia_id: int, mes_filtro: int, ano_filtro: int) -> float:
    orcamento = OrcamentoMensal.query.filter_by(
        familia_id=familia_id, mes=mes_filtro, ano=ano_filtro
    ).first()
    # Se ainda não houver meta salva para esse mês, assume 50%
    return float(orcamento.meta_poupanca_percentual) if orcamento else 50.00


def _calcular_totais_do_mes(familia_id: int, mes_filtro: int, ano_filtro: int, filtro_fantasma):
    """Monta os 4 cards principais: saldo total, receitas, despesas e balanço do mês."""
    saldo_total = db.session.query(func.sum(Conta.saldo_atual)).filter_by(familia_id=familia_id).scalar() or 0

    filtro_receita_limpa = not_(or_(
        Movimentacao.descricao.ilike('%reembolso%'),
        Categoria.nome.ilike('%reembolso%'),
        Movimentacao.descricao.ilike('%rendimento%'),
        Categoria.nome.ilike('%rendimento%'),
        Movimentacao.descricao.ilike('%dividendo%'),
        Categoria.nome.ilike('%dividendo%')
    ))

    receitas_query = db.session.query(func.sum(Movimentacao.valor)).select_from(Movimentacao).outerjoin(
        Categoria, Movimentacao.categoria_id == Categoria.id
    ).filter(
        Movimentacao.familia_id == familia_id,
        Movimentacao.tipo == 'receita',
        filtro_fantasma,
        filtro_receita_limpa
    )
    receitas_mes = float(filtrar_por_mes_ano(receitas_query, Movimentacao.data, mes_filtro, ano_filtro).scalar() or 0)

    despesas_conta_query = db.session.query(func.sum(Movimentacao.valor)).filter(
        Movimentacao.familia_id == familia_id,
        Movimentacao.tipo == 'despesa',
        filtro_fantasma
    )
    despesas_conta_mes = float(filtrar_por_mes_ano(despesas_conta_query, Movimentacao.data, mes_filtro, ano_filtro).scalar() or 0)

    faturas_mes = db.session.query(Fatura).join(MeioPagamento).filter(
        Fatura.familia_id == familia_id,
        Fatura.mes == mes_filtro,
        Fatura.ano == ano_filtro
    ).options(joinedload(Fatura.movimentacoes)).all()

    despesas_cartao_mes = sum(sum(m.valor for m in f.movimentacoes) or 0 for f in faturas_mes)
    despesas_totais = float(despesas_conta_mes) + float(despesas_cartao_mes)
    balanco_mes = receitas_mes - despesas_totais

    return {
        "saldo_total": saldo_total,
        "receitas_mes": receitas_mes,
        "despesas_conta_mes": despesas_conta_mes,
        "despesas_cartao_mes": despesas_cartao_mes,
        "despesas_totais": despesas_totais,
        "balanco_mes": balanco_mes,
        "faturas_mes": faturas_mes,  # reaproveitado por _montar_cards_fatura
    }


def _montar_cards_fatura(familia_id: int, mes_filtro: int, ano_filtro: int, faturas_mes, meses_por_numero):
    """Monta as listas de fatura do 'Monitor de Faturas' (mês atual e o próximo)."""
    prox_mes = 1 if mes_filtro == 12 else mes_filtro + 1
    prox_ano = ano_filtro + 1 if mes_filtro == 12 else ano_filtro

    faturas_proximo_mes = db.session.query(Fatura).join(MeioPagamento).filter(
        Fatura.familia_id == familia_id,
        Fatura.mes == prox_mes,
        Fatura.ano == prox_ano
    ).options(joinedload(Fatura.movimentacoes)).all()

    def _montar_lista(faturas):
        lista = []
        for f in faturas:
            saldo = sum(m.valor for m in f.movimentacoes) or 0
            if saldo > 0 or f.status == 'aberta':
                lista.append({'cartao': f.cartao, 'saldo': saldo, 'status': f.status})
        lista.sort(key=lambda x: x['cartao'].nome)
        return lista

    lista_faturas_atuais = _montar_lista(faturas_mes)
    lista_faturas_proximas = _montar_lista(faturas_proximo_mes)

    nome_mes_atual = f"{meses_por_numero.get(mes_filtro)}/{ano_filtro}"
    nome_mes_prox = f"{meses_por_numero.get(prox_mes)}/{prox_ano}"

    return lista_faturas_atuais, lista_faturas_proximas, nome_mes_atual, nome_mes_prox


def _top_5_categorias(familia_id: int, mes_filtro: int, ano_filtro: int, filtro_fantasma, despesas_totais: float):
    """Unifica gastos de conta + cartão por categoria e devolve o top 5 (+ a lista completa ordenada,
    usada depois para montar os gráficos)."""
    cat_conta_query = db.session.query(
        Categoria.nome,
        func.sum(Movimentacao.valor)
    ).select_from(Movimentacao).outerjoin(Categoria, Movimentacao.categoria_id == Categoria.id).filter(
        Movimentacao.familia_id == familia_id,
        Movimentacao.tipo == 'despesa',
        filtro_fantasma
    )
    cat_conta = filtrar_por_mes_ano(cat_conta_query, Movimentacao.data, mes_filtro, ano_filtro).group_by(Categoria.nome).all()

    cat_cartao_query = db.session.query(
        Categoria.nome,
        func.sum(MovimentacaoCartao.valor)
    ).select_from(MovimentacaoCartao).outerjoin(Categoria, MovimentacaoCartao.categoria_id == Categoria.id).join(
        Fatura, MovimentacaoCartao.fatura_id == Fatura.id
    ).filter(
        Fatura.familia_id == familia_id,
        Fatura.mes == mes_filtro,
        Fatura.ano == ano_filtro
    )
    cat_cartao = cat_cartao_query.group_by(Categoria.nome).all()

    soma_categorias = {}
    for nome, valor in cat_conta + cat_cartao:
        nome_cat = nome if nome else "Sem Categoria"
        soma_categorias[nome_cat] = soma_categorias.get(nome_cat, 0) + float(valor or 0)

    cat_ordenadas = sorted(soma_categorias.items(), key=lambda x: x[1], reverse=True)
    top_5_categorias = []

    if despesas_totais > 0:
        for nome, valor in cat_ordenadas[:5]:
            pct = (valor / despesas_totais * 100)
            top_5_categorias.append({
                'nome': nome, 'valor': valor, 'percentual': round(pct, 1), 'cor': gerar_cor_pastel_por_nome(nome)
            })

    return top_5_categorias, cat_ordenadas


def _top_5_despesas(familia_id: int, mes_filtro: int, ano_filtro: int, filtro_fantasma):
    """Unifica as maiores despesas de conta + cartão do mês e devolve as 5 maiores."""
    movs_conta_query = Movimentacao.query.filter(
        Movimentacao.familia_id == familia_id,
        Movimentacao.tipo == 'despesa',
        filtro_fantasma
    )
    movs_conta = filtrar_por_mes_ano(movs_conta_query, Movimentacao.data, mes_filtro, ano_filtro).all()

    movs_cartao = MovimentacaoCartao.query.join(Fatura).filter(
        Fatura.familia_id == familia_id,
        Fatura.mes == mes_filtro,
        Fatura.ano == ano_filtro
    ).all()

    lista_despesas = []
    for m in movs_conta:
        lista_despesas.append({'descricao': m.descricao, 'valor': float(m.valor), 'data': m.data, 'origem': 'Conta/Pix', 'icone': 'bi-bank'})
    for m in movs_cartao:
        lista_despesas.append({'descricao': m.descricao, 'valor': float(m.valor), 'data': m.data_compra, 'origem': m.cartao.nome, 'icone': 'bi-credit-card'})

    return sorted(lista_despesas, key=lambda x: x['valor'], reverse=True)[:5]


def _montar_agenda(familia_id: int, hoje, filtro_fantasma):
    """Monta o 'Radar da Semana': faturas e movimentações pendentes até 7 dias no futuro."""
    limite_futuro = hoje + timedelta(days=7)

    # 1. Faturas que precisam ser pagas (qualquer status != 'pago', até 7 dias no futuro)
    fats_pendentes = Fatura.query.join(MeioPagamento).filter(
        Fatura.familia_id == familia_id,
        Fatura.status != 'pago',
        Fatura.data_vencimento <= limite_futuro
    ).all()

    # 2. Receitas e despesas pendentes (não pagas, do passado + até 7 dias pra frente)
    movs_pendentes = Movimentacao.query.filter(
        Movimentacao.familia_id == familia_id,
        Movimentacao.pago == False,
        Movimentacao.data <= limite_futuro,
        filtro_fantasma
    ).all()

    agenda = []

    for f in fats_pendentes:
        saldo = sum(m.valor for m in f.movimentacoes) or 0
        if saldo > 0:
            atrasado = f.data_vencimento < hoje
            agenda.append({
                'descricao': f'Fatura {f.cartao.nome}',
                'valor': saldo,
                'data': f.data_vencimento,
                'cor': 'text-danger' if atrasado else 'text-warning',
                'bg': 'bg-danger' if atrasado else 'bg-warning',
                'icone': 'bi-credit-card',
                'atrasado': atrasado,
                'tipo': 'despesa'
            })

    for m in movs_pendentes:
        atrasado = m.data < hoje

        if m.tipo == 'receita':
            cor = 'text-success'
            bg = 'bg-success'
            icone = 'bi-arrow-down-circle'
        else:
            cor = 'text-danger' if atrasado else 'text-danger'
            bg = 'bg-danger' if atrasado else 'bg-danger'
            icone = 'bi-lightning-charge'

        agenda.append({
            'descricao': m.descricao,
            'valor': float(m.valor),
            'data': m.data,
            'cor': cor,
            'bg': bg,
            'icone': icone,
            'atrasado': atrasado,
            'tipo': m.tipo
        })

    return sorted(agenda, key=lambda x: x['data'])


@main_bp.route('/dashboard')
@login_required
def dashboard():
    saudacao = _resolver_saudacao(datetime.now().hour)

    hoje = datetime.today().date()
    meses = [
        ('Janeiro', 1), ('Fevereiro', 2), ('Março', 3), ('Abril', 4),
        ('Maio', 5), ('Junho', 6), ('Julho', 7), ('Agosto', 8),
        ('Setembro', 9), ('Outubro', 10), ('Novembro', 11), ('Dezembro', 12)
    ]
    anos = list(range(hoje.year - 5, hoje.year + 2))
    mes_filtro, ano_filtro = _resolver_filtro_periodo(hoje, anos)

    familia_id = current_user.familia_id

    # Filtro Anti-Fantasmas: some as movimentações que na verdade são
    # faturas/transferências (essas já aparecem em outros lugares do dashboard)
    filtro_fantasma = not_(Movimentacao.descricao.ilike('Fatura %')) & not_(Movimentacao.descricao.ilike('%Transferência%'))

    meta_percentual = _obter_meta_percentual(familia_id, mes_filtro, ano_filtro)

    totais = _calcular_totais_do_mes(familia_id, mes_filtro, ano_filtro, filtro_fantasma)

    meses_por_numero = {numero: nome for nome, numero in meses}
    lista_faturas_atuais, lista_faturas_proximas, nome_mes_atual, nome_mes_prox = _montar_cards_fatura(
        familia_id, mes_filtro, ano_filtro, totais["faturas_mes"], meses_por_numero
    )

    top_5_categorias, cat_ordenadas = _top_5_categorias(
        familia_id, mes_filtro, ano_filtro, filtro_fantasma, totais["despesas_totais"]
    )
    top_5_despesas = _top_5_despesas(familia_id, mes_filtro, ano_filtro, filtro_fantasma)
    agenda = _montar_agenda(familia_id, hoje, filtro_fantasma)

    # Dados para os gráficos do dashboard
    nomes_cats_chart = [item[0] for item in cat_ordenadas if item[0]]
    valores_cats_chart = [item[1] for item in cat_ordenadas if item[0]]
    cores_cats_chart = [gerar_cor_pastel_por_nome(item[0]) for item in cat_ordenadas if item[0]]

    contas = get_contas()
    categorias = get_categorias()
    meios = get_meios_pagamento()

    return render_template('dashboard.html',
        saudacao=saudacao, mes_filtro=mes_filtro, ano_filtro=ano_filtro, meses=meses, anos=anos,
        saldo_total=totais["saldo_total"], receitas_mes=totais["receitas_mes"],
        despesas_totais=totais["despesas_totais"], balanco_mes=totais["balanco_mes"],
        top_5_despesas=top_5_despesas, top_5_categorias=top_5_categorias, agenda=agenda,
        despesas_conta_mes=totais["despesas_conta_mes"], despesas_cartao_mes=totais["despesas_cartao_mes"],
        nomes_cats_chart=nomes_cats_chart, valores_cats_chart=valores_cats_chart, cores_cats_chart=cores_cats_chart,
        contas=contas, categorias=categorias, meios=meios, meta_percentual=meta_percentual,
        lista_faturas_atuais=lista_faturas_atuais, lista_faturas_proximas=lista_faturas_proximas,
        nome_mes_atual=nome_mes_atual, nome_mes_prox=nome_mes_prox
    )