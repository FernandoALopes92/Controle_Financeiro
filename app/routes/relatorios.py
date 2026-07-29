from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, extract, not_, or_
from datetime import datetime
from app.models import db, Movimentacao, Categoria, MovimentacaoCartao, Fatura, OrcamentoMensal, MeioPagamento

relatorios_bp = Blueprint('relatorios', __name__)

@relatorios_bp.route('/relatorios', methods=['GET', 'POST'])
@login_required
def relatorios():
    ano_atual = datetime.today().year
    
    # Captura o ano (via GET ou POST)
    ano_raw = request.form.get('ano') or request.args.get('ano')
    try:
        ano_filtro = int(ano_raw) if ano_raw else ano_atual
        if ano_filtro < 2026: 
            ano_filtro = 2026
    except ValueError:
        ano_filtro = max(ano_atual, 2026)

    # =======================================================
    # 1. SALVAR METAS NO BANCO (Se clicou em Atualizar Painel)
    # =======================================================
    if request.method == "POST":
        for m in range(1, 13):
            meta_input = request.form.get(f"meta_{m}")
            if meta_input:
                orcamento = OrcamentoMensal.query.filter_by(
                    familia_id=current_user.familia_id, mes=m, ano=ano_filtro
                ).first()
                
                if not orcamento:
                    orcamento = OrcamentoMensal(familia_id=current_user.familia_id, mes=m, ano=ano_filtro)
                    db.session.add(orcamento)
                
                orcamento.meta_poupanca_percentual = float(meta_input)
        
        db.session.commit()
        flash("Painel e metas atualizados com sucesso!", "success")
        return redirect(url_for('relatorios.relatorios', ano=ano_filtro))

    # =======================================================
    # 2. LER METAS DO BANCO PARA O RELATÓRIO
    # =======================================================
    orcamentos_do_ano = OrcamentoMensal.query.filter_by(
        familia_id=current_user.familia_id, ano=ano_filtro
    ).all()

    # Cria dicionário padrão com 50% para todos os meses
    meta_meses = {m: 50.0 for m in range(1, 13)}
    
    # Substitui os 50% pelos valores reais que vieram do banco
    for o in orcamentos_do_ano:
        meta_meses[o.mes] = float(o.meta_poupanca_percentual)

    anos = list(range(2026, max(ano_atual + 2, 2028)))
    meses_nomes = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

# --- PROCESSAMENTO DAS RECEITAS (AGRUPADO POR CATEGORIA) ---
    receitas_query = db.session.query(
        Categoria.nome, Movimentacao.descricao, extract('month', Movimentacao.data).label('mes'), func.sum(Movimentacao.valor)
    ).select_from(Movimentacao).outerjoin(Categoria, Movimentacao.categoria_id == Categoria.id).filter(
        Movimentacao.familia_id == current_user.familia_id, 
        Movimentacao.tipo == 'receita', 
        extract('year', Movimentacao.data) == ano_filtro,
        # Filtro Anti-Reembolso: Ignora se a palavra "reembolso" estiver na descrição ou no nome da categoria
        not_(or_(
            Movimentacao.descricao.ilike('%reembolso%'), 
            Categoria.nome.ilike('%reembolso%'),
            Movimentacao.descricao.ilike('%rendimento%'),
            Categoria.nome.ilike('%rendimento%'),
            Movimentacao.descricao.ilike('%dividendo%'),
            Categoria.nome.ilike('%dividendo%')
        ))
    ).group_by(Categoria.nome, Movimentacao.descricao, extract('month', Movimentacao.data)).all()

    receitas_por_categoria = {}
    total_receitas_mes = {m: 0.0 for m in range(1, 13)}
    total_receitas_ano = 0.0

    for cat_nome, desc, mes, valor in receitas_query:
        mes = int(mes)
        val = float(valor or 0)
        
        # Formatação
        cat_formatada = cat_nome.title() if cat_nome else "Sem Categoria"
        desc_formatada = desc.title() if desc else "Outros"
        
        # Cria a Categoria (Pai) se não existir
        if cat_formatada not in receitas_por_categoria:
            receitas_por_categoria[cat_formatada] = {
                'total': 0.0,
                'meses': {m: 0.0 for m in range(1, 13)},
                'descricoes': {}
            }
            
        # Cria a Descrição (Filha) dentro da Categoria se não existir
        if desc_formatada not in receitas_por_categoria[cat_formatada]['descricoes']:
            receitas_por_categoria[cat_formatada]['descricoes'][desc_formatada] = {
                'total': 0.0,
                'meses': {m: 0.0 for m in range(1, 13)}
            }
            
        # Soma os valores na Categoria (Linha Pai)
        receitas_por_categoria[cat_formatada]['meses'][mes] += val
        receitas_por_categoria[cat_formatada]['total'] += val
        
        # Soma os valores na Descrição Específica (Linha Filha)
        receitas_por_categoria[cat_formatada]['descricoes'][desc_formatada]['meses'][mes] += val
        receitas_por_categoria[cat_formatada]['descricoes'][desc_formatada]['total'] += val
        
        # Soma no Total Arrecadado Geral (Rodapé verde escuro)
        total_receitas_mes[mes] += val
        total_receitas_ano += val

    # --- PROCESSAMENTO DAS DESPESAS ---
    despesas_conta = db.session.query(
        Categoria.nome, extract('month', Movimentacao.data).label('mes'), func.sum(Movimentacao.valor)
    ).join(Categoria).filter(
        Movimentacao.familia_id == current_user.familia_id, Movimentacao.tipo == 'despesa', extract('year', Movimentacao.data) == ano_filtro
    ).group_by(Categoria.nome, extract('month', Movimentacao.data)).all()

    despesas_cartao = db.session.query(
        Categoria.nome, Fatura.mes, func.sum(MovimentacaoCartao.valor)
    ).join(Categoria).join(Fatura).filter(
        MovimentacaoCartao.familia_id == current_user.familia_id, Fatura.ano == ano_filtro
    ).group_by(Categoria.nome, Fatura.mes).all()

    despesas_por_categoria = {}
    total_despesas_mes = {m: 0.0 for m in range(1, 13)}
    total_despesas_ano = 0.0

    for nome, mes, valor in despesas_conta + despesas_cartao:
        mes = int(mes)
        val = float(valor or 0)
        nome_cat = nome if nome else "Sem Categoria"
        
        if nome_cat not in despesas_por_categoria:
            despesas_por_categoria[nome_cat] = {m: 0.0 for m in range(1, 13)}
            despesas_por_categoria[nome_cat]['total'] = 0.0
            
        despesas_por_categoria[nome_cat][mes] += val
        despesas_por_categoria[nome_cat]['total'] += val
        total_despesas_mes[mes] += val
        total_despesas_ano += val

    # --- CÁLCULO DE METAS E SOBRAS MÊS A MÊS ---
    meta_valor_mes = {m: 0.0 for m in range(1, 13)}
    sobra_mes = {m: 0.0 for m in range(1, 13)}
    cumpriu_meta = {m: None for m in range(1, 13)}
    sobra_ano = 0.0
    meta_ano = 0.0

    for m in range(1, 13):
        # A conta usa a porcentagem específica que veio do banco para aquele mês
        meta_valor_mes[m] = total_receitas_mes[m] * (meta_meses[m] / 100.0)
        meta_ano += meta_valor_mes[m]
        
        sobra_mes[m] = total_receitas_mes[m] - total_despesas_mes[m]
        sobra_ano += sobra_mes[m]
        
        if total_receitas_mes[m] > 0:
            cumpriu_meta[m] = sobra_mes[m] >= meta_valor_mes[m]

    # =======================================================
    # DETALHAMENTO DE GASTOS (AGRUPADO CONTAS / INDIVIDUAL CARTÕES)
    # =======================================================
    # 1. Agrupado único de todas as movimentações de conta (Pix/Débito) mês a mês
    total_gastos_contas_mes = {m: 0.0 for m in range(1, 13)}
    total_gastos_contas_ano = 0.0
    for nome, mes, valor in despesas_conta:
        mes = int(mes)
        val = float(valor or 0)
        total_gastos_contas_mes[mes] += val
        total_gastos_contas_ano += val

    # 2. Detalhado por cada Cartão de Crédito físico
    gastos_cartao_query = db.session.query(
        MeioPagamento.nome, Fatura.mes, func.sum(MovimentacaoCartao.valor)
    ).join(Fatura, MovimentacaoCartao.fatura_id == Fatura.id).join(MeioPagamento, Fatura.cartao_id == MeioPagamento.id).filter(
        MovimentacaoCartao.familia_id == current_user.familia_id, 
        Fatura.ano == ano_filtro
    ).group_by(MeioPagamento.nome, Fatura.mes).all()

    gastos_por_cartao = {}
    for nome, mes, valor in gastos_cartao_query:
        mes = int(mes)
        val = float(valor or 0)
        nome_formatado = f"Cartão: {nome}"
        if nome_formatado not in gastos_por_cartao:
            gastos_por_cartao[nome_formatado] = {m: 0.0 for m in range(1, 13)}
            gastos_por_cartao[nome_formatado]['total'] = 0.0
        gastos_por_cartao[nome_formatado][mes] += val
        gastos_por_cartao[nome_formatado]['total'] += val
    # =======================================================
 

    # --- IDENTIFICAR O TOP 7 DE CADA MÊS ---
    top_7_por_mes = {m: [] for m in range(1, 13)}
    for m in range(1, 13):
        gastos_do_mes = [(cat, despesas_por_categoria[cat][m]) for cat in despesas_por_categoria if despesas_por_categoria[cat][m] > 0]
        gastos_do_mes.sort(key=lambda x: x[1], reverse=True)
        top_7_por_mes[m] = [item[0] for item in gastos_do_mes[:7]]

    return render_template('navbar/relatorios.html',
        ano_filtro=ano_filtro, meta_meses=meta_meses, anos=anos, meses_nomes=meses_nomes,
        receitas_por_categoria=receitas_por_categoria, total_receitas_mes=total_receitas_mes, total_receitas_ano=total_receitas_ano,
        despesas_por_categoria=despesas_por_categoria, total_despesas_mes=total_despesas_mes, total_despesas_ano=total_despesas_ano,
        meta_valor_mes=meta_valor_mes, meta_ano=meta_ano, sobra_mes=sobra_mes, sobra_ano=sobra_ano, cumpriu_meta=cumpriu_meta,
        total_gastos_contas_mes=total_gastos_contas_mes, total_gastos_contas_ano=total_gastos_contas_ano, gastos_por_cartao=gastos_por_cartao,
        top_7_por_mes=top_7_por_mes
    )