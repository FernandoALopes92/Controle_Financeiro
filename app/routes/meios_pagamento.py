from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models import db, MeioPagamento
from app.utils.db_utils import get_meios_pagamento
from app.utils.upload_utils import salvar_logo, LogoInvalidoError
from flask_login import login_required, current_user

meios_pagamento_bp = Blueprint("meios_pagamento", __name__, url_prefix="/meios_pagamento")

# Define o caminho correto apontando para a pasta de cartões
UPLOAD_PATH = "app/static/logos/cartoes"

# Rota para listar os meios de pagamento
@meios_pagamento_bp.route("/", methods=["GET", "POST"])
@login_required
def listar():
    if request.method == "POST":
        nome = request.form.get("nome")
        tipo = request.form.get("tipo")
        limite = request.form.get("limite")
        fechamento_dia = request.form.get("fechamento_dia")
        vencimento_dia = request.form.get("vencimento_dia")
        logo_file = request.files.get("logo")

        if not nome or not tipo:
            flash("Nome e tipo do meio de pagamento são obrigatórios.", "danger")
            return redirect(url_for("meios_pagamento.listar"))

        try:
            limite = float(limite or 0)
            fechamento_dia = int(fechamento_dia or 0)
            vencimento_dia = int(vencimento_dia or 0)
        except ValueError:
            flash("Limite, fechamento e vencimento devem ser numéricos.", "danger")
            return redirect(url_for("meios_pagamento.listar"))

        try:
            logo_filename = salvar_logo(logo_file, UPLOAD_PATH)
        except LogoInvalidoError as e:
            flash(str(e), "danger")
            return redirect(url_for("meios_pagamento.listar"))

        novo_meio_pagamento = MeioPagamento(
            nome=nome,
            tipo=tipo,
            limite=limite,
            fechamento_dia=fechamento_dia,
            vencimento_dia=vencimento_dia,
            usuario_id=current_user.id,
            familia_id=current_user.familia_id,
            logo=logo_filename
        )
        db.session.add(novo_meio_pagamento)
        db.session.commit()
        flash("Meio de pagamento criado com sucesso!", "success")
        return redirect(url_for("meios_pagamento.listar"))

    meios_pagamento = get_meios_pagamento()
    return render_template("/navbar/meios_pagamento.html", meios_pagamento=meios_pagamento)

# Rota para editar um meio de pagamento
@meios_pagamento_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_meio_pagamento(id):
    meio_pagamento = MeioPagamento.query.filter_by(
        id=id, familia_id=current_user.familia_id
    ).first_or_404()

    if request.method == "POST":
        nome = request.form.get("nome")
        tipo = request.form.get("tipo")
        limite = request.form.get("limite")
        fechamento_dia = request.form.get("fechamento_dia")
        vencimento_dia = request.form.get("vencimento_dia")

        if not nome or not tipo:
            flash("Nome e tipo do meio de pagamento são obrigatórios.", "danger")
            return redirect(url_for("meios_pagamento.listar"))

        meio_pagamento.nome = nome
        meio_pagamento.tipo = tipo

        try:
            meio_pagamento.limite = float(limite or 0)
            meio_pagamento.fechamento_dia = int(fechamento_dia or 0)
            meio_pagamento.vencimento_dia = int(vencimento_dia or 0)

            logo_file = request.files.get('logo')
            logo_filename = salvar_logo(logo_file, UPLOAD_PATH)
            if logo_filename:
                meio_pagamento.logo = logo_filename

            db.session.commit()
            flash("Meio de pagamento atualizado com sucesso!", "success")
        except ValueError:
            flash("Limite, fechamento e vencimento devem ser numéricos.", "danger")
        except LogoInvalidoError as e:
            flash(str(e), "danger")
        return redirect(url_for("meios_pagamento.listar"))

    return render_template("editar_meio_pagamento.html", meio_pagamento=meio_pagamento)

# Rota para excluir um meio de pagamento
@meios_pagamento_bp.route("/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_meio_pagamento(id):
    meio_pagamento = MeioPagamento.query.filter_by(
        id=id, familia_id=current_user.familia_id
    ).first_or_404()
    db.session.delete(meio_pagamento)
    db.session.commit()
    flash("Meio de pagamento excluído com sucesso!", "success")
    return redirect(url_for("meios_pagamento.listar"))