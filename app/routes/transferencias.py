from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import extract

from app.models import db, Conta, Transferencia
from app.utils.db_utils import filtrar_por_mes_ano
from app.services import transferencia_service as transf_service

transferencias_bp = Blueprint("transferencias", __name__, url_prefix="/transferencias")


@transferencias_bp.route('/')
@login_required
def listar_transferencias():
    hoje = date.today()
    ano_atual = hoje.year
    mes_atual = hoje.month

    # CORREÇÃO: filtrar por familia_id para não listar contas de outras famílias no filtro
    contas = Conta.query.filter_by(status=True, familia_id=current_user.familia_id).all()

    ano = request.args.get('ano', type=int) or ano_atual
    mes = request.args.get('mes', type=int) or mes_atual

    transferencias = Transferencia.query \
        .filter_by(familia_id=current_user.familia_id)
    transferencias = filtrar_por_mes_ano(transferencias, Transferencia.data_transferencia, mes, ano)
    transferencias = transferencias.order_by(Transferencia.data_transferencia.desc()).all()

    anos_distintos = db.session.query(extract('year', Transferencia.data_transferencia)) \
        .filter_by(familia_id=current_user.familia_id) \
        .distinct() \
        .order_by(extract('year', Transferencia.data_transferencia).desc()) \
        .all()
    anos = [a[0] for a in anos_distintos]

    meses = [
        ("Janeiro", 1), ("Fevereiro", 2), ("Março", 3), ("Abril", 4),
        ("Maio", 5), ("Junho", 6), ("Julho", 7), ("Agosto", 8),
        ("Setembro", 9), ("Outubro", 10), ("Novembro", 11), ("Dezembro", 12)
    ]

    return render_template(
        'transferencias/lista_transferencias.html',
        transferencias=transferencias,
        anos=anos,
        ano_filtro=ano,
        meses=meses,
        mes_filtro=mes,
        contas=contas
    )


@transferencias_bp.route("/nova", methods=["GET", "POST"])
@login_required
def nova_transferencia():
    contas = Conta.query.filter_by(familia_id=current_user.familia_id, status=True).all()

    if request.method == "POST":
        origem_id_raw = request.form.get("conta_origem")
        destino_id_raw = request.form.get("conta_destino")
        valor_raw = request.form.get("valor")
        data = request.form.get("data")
        descricao = request.form.get("descricao")

        if not origem_id_raw or not destino_id_raw or not valor_raw or not data:
            flash("Todos os campos são obrigatórios.", "danger")
            return redirect(request.referrer)

        try:
            dados = transf_service.NovaTransferenciaInput(
                origem_id=int(origem_id_raw),
                destino_id=int(destino_id_raw),
                valor=Decimal(valor_raw),
                data=data,
                descricao=descricao,
            )
        except (ValueError, InvalidOperation):
            flash("Dados inválidos.", "danger")
            return redirect(request.referrer)

        try:
            mensagem = transf_service.criar_transferencia(
                dados, usuario_id=current_user.id, familia_id=current_user.familia_id
            )
            flash(mensagem, "success")
        except transf_service.TransferenciaServiceError as e:
            flash(str(e), "danger")
        except Exception:
            flash("Erro ao realizar transferência.", "danger")

        return redirect(request.referrer)

    return render_template("form_transferencia.html", contas=contas)


@transferencias_bp.route('/transferencias/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_transferencia(id):
    # CORREÇÃO: filtrar por familia_id para impedir excluir/estornar transferência de outra família
    transferencia = Transferencia.query.filter_by(id=id, familia_id=current_user.familia_id).first_or_404()

    try:
        transf_service.excluir_transferencia(transferencia)
        flash("Transferência excluída e saldos estornados com sucesso.", "success")
    except transf_service.ContaInativaError as e:
        flash(str(e), "danger")
        return redirect(url_for("transferencias.listar_transferencias"))

    return redirect(request.referrer)


@transferencias_bp.route('/editar/<int:id>', methods=["POST"])
@login_required
def editar_transferencia(id):
    # CORREÇÃO: filtrar por familia_id para impedir editar transferência de outra família
    transferencia = Transferencia.query.filter_by(id=id, familia_id=current_user.familia_id).first_or_404()

    origem_id_raw = request.form.get("conta_origem")
    destino_id_raw = request.form.get("conta_destino")
    valor_raw = request.form.get("valor")
    data = request.form.get("data")
    descricao = request.form.get("descricao")

    if not origem_id_raw or not destino_id_raw or not valor_raw or not data:
        flash("Todos os campos são obrigatórios.", "danger")
        return redirect(request.referrer)

    if origem_id_raw == destino_id_raw:
        flash("A conta de origem e destino devem ser diferentes.", "danger")
        return redirect(request.referrer)

    try:
        valor = Decimal(valor_raw)
        if valor <= 0:
            flash("O valor da transferência deve ser maior que zero.", "danger")
            return redirect(request.referrer)
        dados = transf_service.EditarTransferenciaInput(
            origem_id=int(origem_id_raw),
            destino_id=int(destino_id_raw),
            valor=valor,
            data=data,
            descricao=descricao,
        )
    except (ValueError, InvalidOperation):
        flash("Dados inválidos. Verifique os campos e tente novamente.", "danger")
        return redirect(request.referrer)

    try:
        mensagem = transf_service.atualizar_transferencia(
            transferencia, dados, usuario_id=current_user.id, familia_id=current_user.familia_id
        )
        flash(mensagem, "success")
    except transf_service.ContaInativaError as e:
        flash(str(e), "danger")
        return redirect(url_for("transferencias.listar_transferencias"))
    except transf_service.TransferenciaServiceError as e:
        flash(str(e), "danger")
    except Exception:
        flash("Erro ao atualizar transferência. Tente novamente.", "danger")

    return redirect(request.referrer)