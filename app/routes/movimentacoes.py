from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import extract, func

from app.models import db, Movimentacao, Transferencia
from app.utils.db_utils import get_meios_pagamento, get_categorias, get_contas, filtrar_por_mes_ano
from app.services import movimentacao_service as mov_service


movimentacoes_bp = Blueprint('movimentacoes', __name__, url_prefix='/movimentacoes')


@movimentacoes_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def criar():
    if request.method == 'POST':
        data = request.form.get('data')
        descricao = request.form.get('descricao')
        categoria_id = request.form.get('categoria_id') or None
        valor_raw = request.form.get('valor')
        conta_id = request.form.get('conta_id') or None
        pago = request.form.get('pago') == 'true'
        replicar = request.form.get('replicar')

        if not data or not descricao or not categoria_id or not valor_raw or not conta_id:
            flash('Todos os campos são obrigatórios.', 'danger')
            return redirect(url_for('movimentacoes.lista'))

        try:
            valor = Decimal(valor_raw)
        except (ValueError, TypeError, InvalidOperation):
            flash("Valor inválido. Use números com ponto ou vírgula.", "danger")
            return redirect(url_for('movimentacoes.lista'))

        try:
            data_dt = datetime.strptime(data, '%Y-%m-%d')
        except (ValueError, TypeError):
            flash("Data inválida.", "danger")
            return redirect(url_for('movimentacoes.lista'))

        dados = mov_service.NovaMovimentacaoInput(
            data=data_dt,
            descricao=descricao,
            categoria_id=categoria_id,
            valor=valor,
            conta_id=conta_id,
            pago=pago,
            replicar=replicar,
        )
        try:
            mensagem = mov_service.criar_movimentacao(
                dados, usuario_id=current_user.id, familia_id=current_user.familia_id
            )
            flash(mensagem, "success")
        except mov_service.MovimentacaoServiceError as e:
            flash(str(e), "danger")

        return redirect(url_for('movimentacoes.lista'))

    # GET
    categorias = get_categorias()
    meios_pagamento = get_meios_pagamento()
    contas = get_contas()
    return render_template(
        'form_movimentacao.html',
        categorias=categorias,
        meios_pagamento=meios_pagamento,
        contas=contas
    )


@movimentacoes_bp.route('/')
@login_required
def lista():
    # 1. Captura primeiro a data atual e os parâmetros da URL
    agora = datetime.now()
    mes = request.args.get("mes", default=agora.month, type=int)
    ano = request.args.get("ano", default=agora.year, type=int)

    # 2. Carrega as funções auxiliares de contas e categorias
    contas = get_contas()
    categorias = get_categorias()

    # 3. Executa a busca filtrada de Movimentações (Aba 1)
    query = db.session.query(Movimentacao)
    if mes and ano:
        query = filtrar_por_mes_ano(query, Movimentacao.data, mes, ano)
    movimentacoes = query.order_by(Movimentacao.data.desc()).all()

    # 4. Executa a busca filtrada de Transferências (Aba 2)
    query_transf = db.session.query(Transferencia).filter_by(familia_id=current_user.familia_id)
    if mes and ano:
        query_transf = filtrar_por_mes_ano(query_transf, Transferencia.data_transferencia, mes, ano)
    transferencias = query_transf.order_by(Transferencia.data_transferencia.desc()).all()

    # 5. Gera as opções disponíveis para os seletores de filtros
    anos_query = db.session.query(extract('year', Movimentacao.data).label('ano'))\
        .distinct().order_by('ano')
    anos = [int(row.ano) for row in anos_query]

    if not anos:
        anos = [agora.year]

    meses_query = db.session.query(
        extract('month', Movimentacao.data).label('mes')
    ).distinct().order_by('mes')

    meses_nomes = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    meses = [(meses_nomes[int(row.mes)-1], int(row.mes)) for row in meses_query]

    if not meses:
        meses = [(meses_nomes[agora.month - 1], agora.month)]

    # 6. Cálculos estatísticos do gráfico de barras lateral
    query_receitas = db.session.query(func.sum(Movimentacao.valor)).filter(
        Movimentacao.tipo == 'receita'
    )
    query_receitas = filtrar_por_mes_ano(query_receitas, Movimentacao.data, mes, ano)

    query_despesas = db.session.query(func.sum(Movimentacao.valor)).filter(
        Movimentacao.tipo == 'despesa'
    )
    query_despesas = filtrar_por_mes_ano(query_despesas, Movimentacao.data, mes, ano)

    total_receitas = query_receitas.scalar() or 0
    total_despesas = query_despesas.scalar() or 0

    return render_template('mov_contas/lista_movimentacoes.html',
                           movimentacoes=movimentacoes,
                           transferencias=transferencias,
                           contas=contas,
                           categorias=categorias,
                           total_receitas=total_receitas,
                           total_despesas=total_despesas,
                           meses=meses,
                           anos=anos,
                           mes_filtro=mes,
                           ano_filtro=ano)


@movimentacoes_bp.route('/<int:id>/json')
@login_required
def obter_movimentacao(id):
    movimentacao = Movimentacao.query.get_or_404(id)

    if movimentacao.familia_id != current_user.familia_id:
        return {"erro": "Acesso negado"}, 403

    return {
        "id": movimentacao.id,
        "data": movimentacao.data.strftime('%Y-%m-%d'),
        "descricao": movimentacao.descricao,
        "categoria_id": movimentacao.categoria_id,
        "valor": str(movimentacao.valor),
        "conta_id": movimentacao.conta_id,
        "pago": movimentacao.pago
    }


@movimentacoes_bp.route('/<int:id>/editar', methods=['POST'])
@login_required
def editar(id):
    mov = Movimentacao.query.get_or_404(id)

    if mov.familia_id != current_user.familia_id:
        flash("Você não tem permissão para editar essa movimentação.", "danger")
        return redirect(url_for('movimentacoes.lista'))

    data = request.form.get('data')
    descricao = request.form.get('descricao')
    categoria_id = request.form.get('categoria_id') or None
    valor_raw = request.form.get('valor')
    conta_id = request.form.get('conta_id') or None

    if not data or not descricao or not categoria_id or not valor_raw or not conta_id:
        flash('Todos os campos são obrigatórios.', 'danger')
        return redirect(url_for('movimentacoes.lista'))

    try:
        valor = Decimal(valor_raw)
    except (ValueError, TypeError, InvalidOperation):
        flash("Valor inválido.", "danger")
        return redirect(url_for('movimentacoes.lista'))

    try:
        data_dt = datetime.strptime(data, '%Y-%m-%d')
    except (ValueError, TypeError):
        flash("Data inválida.", "danger")
        return redirect(url_for('movimentacoes.lista'))

    pago = mov_service.decidir_pago(request.form.get('pago'), data_dt)

    dados = mov_service.EditarMovimentacaoInput(
        data=data_dt,
        descricao=descricao,
        categoria_id=categoria_id,
        valor=valor,
        conta_id=conta_id,
        pago=pago,
    )

    try:
        mensagem = mov_service.atualizar_movimentacao(mov, dados, familia_id=current_user.familia_id)
        flash(mensagem, "success")
    except mov_service.MovimentacaoBloqueadaError as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"erro": str(e)}), 403
        flash(str(e), "warning")
    except mov_service.MovimentacaoServiceError as e:
        flash(str(e), "danger")

    return redirect(url_for('movimentacoes.lista'))


@movimentacoes_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    mov = Movimentacao.query.get_or_404(id)

    if mov.familia_id != current_user.familia_id:
        return {"erro": "Acesso negado"}, 403

    try:
        mov_service.excluir_movimentacao(mov, familia_id=current_user.familia_id)
    except mov_service.MovimentacaoBloqueadaError as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"erro": str(e)}), 403
        flash(str(e), "warning")
        return redirect(url_for('movimentacoes.lista'))
    except mov_service.ContaInativaError as e:
        flash(str(e), "danger")
        return redirect(url_for('movimentacoes.lista'))

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"mensagem": "Movimentação excluída com sucesso"})

    flash("Movimentação excluída com sucesso!", "success")
    return redirect(url_for('movimentacoes.lista'))