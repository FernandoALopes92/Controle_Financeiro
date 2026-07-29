import traceback, random, hashlib, uuid
from flask import Blueprint, jsonify, render_template, redirect, url_for, request, flash
from app.models import db, MovimentacaoCartao, MeioPagamento, Categoria, Usuario, Fatura, Conta
from flask_login import login_required, current_user
from sqlalchemy import func, extract
from datetime import datetime, date
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from dateutil.relativedelta import relativedelta  # instale com: pip install python-dateutil
from app.utils.db_utils import get_meios_pagamento, get_categorias, get_contas
from calendar import monthrange
from app.services import cartao_service
from app.services.cartao_service import (
    NovaMovimentacaoInput,
    EditarMovimentacaoInput,
    converter_valor_para_decimal,
    # gerar_cor_pastel_por_nome,  # se mover gerar_cor para utils depois
)

def _resposta_cartao(is_ajax, *, sucesso, msg, tipo="info", status=200):
    """Função auxiliar para padronizar respostas AJAX vs Redirect/Flash."""
    if is_ajax:
        payload = {"sucesso": sucesso, "mensagem": msg} if sucesso else {"sucesso": False, "erro": msg}
        return jsonify(payload), status
    
    flash(msg, tipo)
    return redirect(url_for("cartao.listar_movimentacoes_cartao"))


cartao_bp = Blueprint("cartao", __name__, url_prefix="/cartao")

def gerar_cor_pastel_por_nome(nome):
    if not nome:
        return "hsl(0, 0%, 90%)"
    hash_obj = hashlib.md5(nome.encode('utf-8'))
    hash_int = int(hash_obj.hexdigest()[:8], 16)
    hue = hash_int % 360 
    return f"hsl({hue}, 70%, 80%)"


@cartao_bp.route("/mov_cartao")
@login_required
def listar_movimentacoes_cartao():
    familia_id = current_user.familia_id

    # Obter os anos distintos de faturas (Segurança: Apenas da família logada)
    anos = db.session.query(Fatura.ano).filter_by(familia_id=familia_id).distinct().order_by(Fatura.ano.desc()).all()
    anos = [ano[0] for ano in anos] if anos else [datetime.now().year]

    # Filtros capturados da URL
    ano_filtro = int(request.args.get('ano', default=datetime.now().year))
    mes_filtro = int(request.args.get('mes', default=datetime.now().month))
    cartao_filtro = request.args.get('cartao_id', type=int)
    categoria_filtro = request.args.get('categoria_id', type=int)

    meses = [
        ("Janeiro", 1), ("Fevereiro", 2), ("Março", 3), ("Abril", 4),
        ("Maio", 5), ("Junho", 6), ("Julho", 7), ("Agosto", 8),
        ("Setembro", 9), ("Outubro", 10), ("Novembro", 11), ("Dezembro", 12)
    ]

    # Buscar faturas abertas do mês/ano filtrado DA FAMÍLIA
    faturas = Fatura.query.filter_by(mes=mes_filtro, ano=ano_filtro, familia_id=familia_id).all()
    fatura_ids = [f.id for f in faturas]

    # --- MOTOR DE BUSCA COM FILTROS ATIVADOS E BLINDADOS ---
    query_mov = MovimentacaoCartao.query.filter(
        MovimentacaoCartao.fatura_id.in_(fatura_ids),
        MovimentacaoCartao.familia_id == familia_id
    )

    if cartao_filtro:
        query_mov = query_mov.filter(MovimentacaoCartao.cartao_id == cartao_filtro)
    
    if categoria_filtro:
        query_mov = query_mov.filter(MovimentacaoCartao.categoria_id == categoria_filtro)

    mov_cartao = query_mov.order_by(MovimentacaoCartao.data_compra.desc()).all()

    mov_cartao = query_mov.order_by(MovimentacaoCartao.data_compra.desc()).all()

    # CAPTURA APENAS O QUE FOI USADO NA TABELA ATUAL ---
    cartoes_usados = sorted(list({mov.cartao.nome for mov in mov_cartao if mov.cartao}))
    categorias_usadas = sorted(list({mov.categoria.nome if mov.categoria else 'Rotativo / Ajuste' for mov in mov_cartao}))

    meios = get_meios_pagamento()
    categorias = Categoria.query.filter(
        Categoria.categoria_pai_id.isnot(None), 
        Categoria.tipo == 'despesa',
        Categoria.familia_id == familia_id
    ).order_by(Categoria.nome.asc()).all()
    contas = get_contas()

    # Selecionar a fatura mais recente por cartão
    faturas_unicas = {}
    for f in faturas:
        if f.cartao_id not in faturas_unicas:
            faturas_unicas[f.cartao_id] = f
        else:
            atual = faturas_unicas[f.cartao_id]
            if (f.ano, f.mes) > (atual.ano, atual.mes):
                faturas_unicas[f.cartao_id] = f

    faturas_ordenadas = sorted(faturas_unicas.values(), key=lambda f: f.cartao.nome.lower())

    # Calcular saldo total por cartão (Geral do mês, independente do filtro visual)
    total_saldo = {meio.id: 0.00 for meio in meios}
    for f in faturas_ordenadas:
        total_fatura = sum(mov.valor for mov in f.movimentacoes)
        total_saldo[f.cartao_id] = float(total_fatura)
    
    total_saldo_total = sum(total_saldo.values())

    # Agrupar valores por categoria BASEADO NOS FILTROS ATIVOS para os gráficos
    valores_por_categoria = {}
    total_filtrado = sum(mov.valor for mov in mov_cartao)
    
    for mov in mov_cartao:
        cat = mov.categoria.nome if mov.categoria else "Rotativo / Ajuste"
        valores_por_categoria.setdefault(cat, 0)
        valores_por_categoria[cat] += mov.valor

    categorias_valores = []
    for nome, valor in valores_por_categoria.items():
        percentual = (float(valor) / float(total_filtrado) * 100) if total_filtrado else 0
        categorias_valores.append({
            'nome': nome,
            'valor': round(valor, 2),
            'percentual': round(percentual, 1),
            'cor': gerar_cor_pastel_por_nome(nome)
        })

    categorias_valores.sort(key=lambda x: x['valor'], reverse=True)


    return render_template(
        "cartao/mov_cartao.html",
        ano_filtro=ano_filtro,
        mes_filtro=mes_filtro,
        cartao_filtro=cartao_filtro, # Retornado para o HTML marcar o Select
        categoria_filtro=categoria_filtro, # Retornado para o HTML marcar o Select
        anos=anos,
        meses=meses,
        mov_cartao=mov_cartao,
        meios=meios,
        categorias=categorias,
        contas=contas,
        faturas=faturas_unicas.values(),
        total_saldo=total_saldo,
        total_saldo_total=total_saldo_total,
        categorias_valores=categorias_valores,
        cartoes_usados=cartoes_usados,
        categorias_usadas=categorias_usadas,
        date=date,
        gerar_cor_pastel=gerar_cor_pastel_por_nome
    )


@cartao_bp.route("/mov_cartao/nova", methods=["GET", "POST"])
@login_required
def nova_movimentacao_cartao():
    if request.method == "POST":
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        valor = converter_valor_para_decimal(request.form.get("valor", "").strip())
        if valor is None:
            msg = f"O valor '{request.form.get('valor', '')}' não é válido. Use 100.00 ou 100,00."
            return _resposta_cartao(is_ajax, sucesso=False, msg=msg, tipo="danger", status=400)
        try:
            dados = NovaMovimentacaoInput(
                descricao=request.form["descricao"],
                valor=valor,
                data_compra=datetime.strptime(request.form["data"], "%Y-%m-%d"),
                cartao_id=int(request.form["meio_pagamento_id"]),
                categoria_id=int(request.form["categoria_id"]),
                fatura_mes_ano=request.form.get("fatura_mes_ano", ""),
                tipo_pagamento=request.form.get("tipo_pagamento", ""),
                tipo_valor=request.form.get("tipo_valor"),
                numero_parcelas=int(request.form.get("numero_parcelas") or 1),
                replicar=request.form.get("replicar", "nao"),
                is_estorno=request.form.get("is_estorno") == "true",
            )
            msg, _ = cartao_service.criar_movimentacao(
                dados,
                usuario_id=current_user.id,
                familia_id=current_user.familia_id,
            )
            return _resposta_cartao(is_ajax, sucesso=True, msg=msg, tipo="success")
        except cartao_service.FaturaFechadaError as e:
            return _resposta_cartao(is_ajax, sucesso=False, msg=str(e), tipo="warning", status=400)
        except cartao_service.CartaoServiceError as e:
            return _resposta_cartao(is_ajax, sucesso=False, msg=str(e), tipo="danger", status=400)
        except Exception as e:
            db.session.rollback()
            return _resposta_cartao(
                is_ajax, sucesso=False,
                msg=f"Ocorreu um erro ao salvar: {e}",
                tipo="danger", status=500,
            )

    meios = get_meios_pagamento()
    categorias = Categoria.query.filter(Categoria.categoria_pai_id.isnot(None), Categoria.tipo == 'despesa').order_by(Categoria.nome.asc()).all()
    return render_template("cartao/formAddDespesaCartao.html", meios=meios, categorias=categorias)


@cartao_bp.route("/mov_cartao/<int:id>/edit", methods=["GET", "POST"])
@login_required
def editar_movimentacao_cartao(id):
    # BLINDADO PARA IDOR: Filtra sempre pela família do usuário logado
    mov_cartao = MovimentacaoCartao.query.filter_by(id=id, familia_id=current_user.familia_id).first_or_404()
    meios = get_meios_pagamento()
    categorias = Categoria.query.filter(Categoria.categoria_pai_id.isnot(None), Categoria.tipo == 'despesa', Categoria.familia_id == current_user.familia_id).order_by(Categoria.nome.asc()).all()

    if request.method == "POST":
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        try:
            valor_novo = converter_valor_para_decimal(request.form.get("valor", "").strip())
            if valor_novo is None:
                raise cartao_service.ValorInvalidoError(request.form.get("valor", ""))

            dados = EditarMovimentacaoInput(
                descricao=request.form["descricao"],
                valor=valor_novo,
                data_compra=datetime.strptime(request.form["data"], "%Y-%m-%d"),
                cartao_id=int(request.form["meio_pagamento_id"]),
                categoria_id=int(request.form["categoria_id"]),
                fatura_mes_ano=request.form.get("fatura_mes_ano", ""),
                is_estorno=request.form.get("is_estorno") == "true",
                alterar_proximas=request.form.get("alterar_proximas") == "true",
            )

            msg = cartao_service.atualizar_movimentacao(
                mov_cartao, dados, familia_id=current_user.familia_id
            )
            return _resposta_cartao(is_ajax, sucesso=True, msg=msg, tipo="success")

        except cartao_service.FaturaFechadaError as e:
            db.session.rollback()
            return _resposta_cartao(is_ajax, sucesso=False, msg=str(e), tipo="warning", status=400)
            
        except cartao_service.ValorInvalidoError as e:
            return _resposta_cartao(is_ajax, sucesso=False, msg=str(e), tipo="danger", status=400)
            
        except cartao_service.CartaoServiceError as e:
            db.session.rollback()
            return _resposta_cartao(is_ajax, sucesso=False, msg=str(e), tipo="danger", status=400)
            
        except Exception as e:
            db.session.rollback()
            return _resposta_cartao(
                is_ajax, sucesso=False,
                msg=f"Ocorreu um erro ao atualizar: {e}",
                tipo="danger", status=500,
            )

    return render_template("cartao/formAddDespesaCartao.html", meios=meios, categorias=categorias, mov=mov_cartao)

@cartao_bp.route("/mov_cartao/<int:id>/excluir", methods=["POST"])
@login_required
def deletar_movimentacao_cartao(id):
    # BLINDADO PARA IDOR
    mov_cartao = MovimentacaoCartao.query.filter_by(id=id, familia_id=current_user.familia_id).first_or_404()
    
    excluir_todas = request.form.get("excluir_todas") == "true"
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    ano_filtro = request.args.get('ano')
    mes_filtro = request.args.get('mes')

    try:
        # Chama a função que já existe no seu cartao_service!
        cartao_service.excluir_movimentacao(
            mov_cartao,
            familia_id=current_user.familia_id,
            excluir_todas=excluir_todas
        )

        msg = "Exclusão realizada com sucesso."
        if is_ajax:
            return jsonify({"sucesso": True, "mensagem": msg})
        
        flash(msg, "success")
        return redirect(url_for("cartao.listar_movimentacoes_cartao", ano=ano_filtro, mes=mes_filtro))

    except Exception as e:
        db.session.rollback()
        erro_msg = f"Falha ao excluir a movimentação: {str(e)}"
        
        if is_ajax:
            return jsonify({"sucesso": False, "erro": erro_msg}), 400
            
        flash(erro_msg, "danger")
        return redirect(url_for("cartao.listar_movimentacoes_cartao", ano=ano_filtro, mes=mes_filtro))

@cartao_bp.route('/mov_cartao/editar/<int:id>', methods=['GET'])
@login_required
def obter_movimentacao_cartao(id):
    # BLINDADO PARA IDOR
    mov = MovimentacaoCartao.query.filter_by(id=id, familia_id=current_user.familia_id).first_or_404()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'id': mov.id,
            'descricao': mov.descricao,
            'valor': Decimal(mov.valor),
            'data_compra': mov.data_compra.strftime('%Y-%m-%d'),
            'categoria_id': mov.categoria_id,
            'meio_pagamento_id': mov.cartao_id,
            'numero_parcelas': mov.numero_parcelas,
            'parcela_atual': mov.parcela_atual,
            'fatura_id_mes': mov.fatura.mes,
            'fatura_id_ano': mov.fatura.ano,
            "compra_grupo_id": mov.compra_grupo_id
        })

    return redirect(url_for('cartao.listar_movimentacoes_cartao'))

@cartao_bp.route("/fatura_original/<int:id>", methods=["GET"])
@login_required
def buscar_fatura_original(id):
    from app.models import Fatura 
    
    # BLINDADO PARA IDOR
    mov_cartao = MovimentacaoCartao.query.filter_by(id=id, familia_id=current_user.familia_id).first_or_404()
    fatura = Fatura.query.filter_by(id=mov_cartao.fatura_id, familia_id=current_user.familia_id).first()
    
    if fatura:
        meses = {
            1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 
            7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
        }
        texto_fatura = f"{meses.get(fatura.mes, str(fatura.mes))}/{fatura.ano} (Fatura Original)"
        return jsonify({
            "mes": fatura.mes,
            "ano": fatura.ano,
            "texto_fatura": texto_fatura
        })
    else:
        return jsonify({"erro": "Fatura não encontrada"}), 404