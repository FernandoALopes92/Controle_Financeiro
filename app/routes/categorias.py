
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Categoria

categorias_bp = Blueprint("categorias", __name__, url_prefix="/categorias")

@categorias_bp.route("/", methods=["GET", "POST"])
@login_required
def listar():
    if request.method == "POST":
        nome = request.form.get("nome")
        tipo = request.form.get("tipo") # 'receita' ou 'despesa'
        categoria_pai_id = request.form.get("categoria_pai_id")

        if not nome or not tipo:
            flash("Nome e tipo são obrigatórios.", "danger")
        else:
            # Se vier vazio, salva como None (Categoria Principal)
            pai_id = int(categoria_pai_id) if categoria_pai_id else None
            
            nova_categoria = Categoria(nome=nome, tipo=tipo, categoria_pai_id=pai_id, familia_id=current_user.familia_id)
            db.session.add(nova_categoria)
            db.session.commit()
            flash("Categoria adicionada com sucesso!", "success")
        return redirect(url_for("categorias.listar"))

    # Busca apenas as categorias principais (que não têm pai) para estruturar a tabela
    categorias_principais = Categoria.query.filter_by(familia_id=current_user.familia_id, categoria_pai_id=None, status=True).order_by(Categoria.nome).all()
    
    # Busca todas as categorias para preencher o <select> do modal
    todas_categorias = Categoria.query.filter_by(familia_id=current_user.familia_id, status=True).order_by(Categoria.nome).all()
    
    return render_template("/navbar/categorias.html", categorias=categorias_principais, todas_categorias=todas_categorias)

@categorias_bp.route("/editar/<int:id>", methods=["POST"])
@login_required
def editar_categoria(id):
    categoria = Categoria.query.filter_by(id=id, familia_id=current_user.familia_id).first_or_404()    
    nome = request.form.get("nome")
    tipo = request.form.get("tipo")
    categoria_pai_id = request.form.get("categoria_pai_id")

    if not nome or not tipo:
        flash("Nome e tipo são obrigatórios.", "danger")
        return redirect(url_for("categorias.listar"))
        
    categoria.nome = nome
    categoria.tipo = tipo
    categoria.categoria_pai_id = int(categoria_pai_id) if categoria_pai_id else None
    
    db.session.commit()
    flash("Categoria atualizada com sucesso!", "success")
    return redirect(url_for("categorias.listar"))

@categorias_bp.route("/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_categoria(id):
    categoria = Categoria.query.filter_by(id=id, familia_id=current_user.familia_id).first_or_404()

    # SOFT DELETE: Apenas desativa a categoria para não quebrar o histórico de gastos
    categoria.status = False
    
    # Se você apagar uma categoria principal, desativa as filhas junto
    for sub in categoria.subcategorias:
        sub.status = False

    db.session.commit()
    flash("Categoria excluída com sucesso!", "success")
    return redirect(url_for("categorias.listar"))