from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models import db, Conta
from flask_login import login_required, current_user
from app.utils.db_utils import get_contas
from app.utils.upload_utils import salvar_logo, LogoInvalidoError
from app.services import conta_service
from datetime import datetime

contas_bp = Blueprint("contas", __name__, url_prefix="/contas")

UPLOAD_PATH = "app/static/logos/contas"

@contas_bp.route("/", methods=["GET", "POST"])
@login_required
def listar():
    if request.method == "POST":
        nome = request.form.get("nome")
        data = request.form.get("data")
        saldo_inicial = request.form.get("saldo_inicial")
        tipo = request.form.get("tipo")
        logo_file = request.files.get("logo")

        # Converte a string do HTML para uma Data do Python
        data_formatada = None
        if data:
            data_formatada = datetime.strptime(data, '%Y-%m-%d').date()

        # Validação robusta
        if not nome or not tipo:
            flash("Nome e tipo da conta são obrigatórios.", "danger")
            return redirect(url_for("contas.listar"))

        try:
            saldo = float(saldo_inicial or 0)
        except ValueError:
            flash("Saldo inicial inválido.", "danger")
            return redirect(url_for("contas.listar"))

        try:
            logo_filename = salvar_logo(logo_file, UPLOAD_PATH)
        except LogoInvalidoError as e:
            flash(str(e), "danger")
            return redirect(url_for("contas.listar"))

        nova_conta = Conta(
            nome=nome, data=data_formatada, saldo_inicial=saldo, saldo_atual=saldo,
            tipo=tipo, usuario_id=current_user.id, familia_id=current_user.familia_id,
            logo=logo_filename
        )
        db.session.add(nova_conta)
        db.session.commit()
        flash("Conta adicionada com sucesso!", "success")
        return redirect(url_for("contas.listar"))

    contas = get_contas()
    return render_template("navbar/contas.html", contas=contas)


@contas_bp.route("/editar/<int:id>", methods=["POST"])
@login_required
def editar_conta(id):
    conta = Conta.query.filter_by(
        id=id, familia_id=current_user.familia_id
    ).first_or_404()

    nome = request.form.get("nome")
    data_str = request.form.get("data")
    saldo_inicial_str = request.form.get("saldo_inicial")
    tipo = request.form.get("tipo")

    try:
        novo_saldo_inicial = float(saldo_inicial_str or 0)
    except ValueError:
        flash("Saldo inválido.", "danger")
        return redirect(url_for("contas.listar"))

    data_formatada = None
    if data_str:
        data_formatada = datetime.strptime(data_str, '%Y-%m-%d').date()

    try:
        logo_filename = salvar_logo(request.files.get('logo'), UPLOAD_PATH)
    except LogoInvalidoError as e:
        flash(str(e), "danger")
        return redirect(url_for("contas.listar"))

    dados = conta_service.EditarContaInput(
        nome=nome,
        data=data_formatada,
        saldo_inicial=novo_saldo_inicial,
        tipo=tipo,
        logo_filename=logo_filename,
    )
    mensagem = conta_service.atualizar_conta(conta, dados)
    flash(mensagem, "success")
    return redirect(url_for("contas.listar"))


@contas_bp.route("/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_conta(id):
    # TRAVA DE SEGURANÇA: Garante que a conta pertence à família
    conta = Conta.query.filter_by(id=id, familia_id=current_user.familia_id).first_or_404()

    try:
        mensagem = conta_service.excluir_conta(conta, familia_id=current_user.familia_id)
        flash(mensagem, "success")
    except conta_service.ContaComSaldoError as e:
        flash(str(e), "warning")
    except conta_service.ContaComPendenciaError as e:
        flash(str(e), "danger")

    return redirect(url_for("contas.listar"))