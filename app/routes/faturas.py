from decimal import Decimal, InvalidOperation
from datetime import datetime

from flask import Blueprint, flash, redirect, request, jsonify, url_for
from flask_login import current_user, login_required

from app.models import MeioPagamento, Fatura
from app.services import cartao_service, fatura_service
import locale

fatura_bp = Blueprint('faturas', __name__, url_prefix='/faturas')

# Configurar o locale para português
locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')


@fatura_bp.route('/prever_fatura', methods=['POST'])
@login_required
def prever_fatura():
    data = request.json
    data_compra_str = data.get('data_compra')
    meio_pagamento_id = data.get('meio_pagamento_id')

    if not data_compra_str or not meio_pagamento_id:
        return jsonify({'erro': 'Data da compra e cartão são obrigatórios.'}), 400

    try:
        data_compra = datetime.strptime(data_compra_str, '%Y-%m-%d').date()
        meio_pagamento_id = int(meio_pagamento_id)
    except Exception:
        return jsonify({'erro': 'Dados inválidos.'}), 400

    cartao = MeioPagamento.query.filter_by(id=meio_pagamento_id, familia_id=current_user.familia_id).first()
    if not cartao:
        return jsonify({'erro': 'Cartão não encontrado.'}), 404

    opcoes = cartao_service.prever_opcoes_fatura(cartao, data_compra)
    return jsonify({'opcoes': opcoes})


def _buscar_fatura_ou_404(fatura_id):
    return Fatura.query.filter_by(id=fatura_id, familia_id=current_user.familia_id).first_or_404()


@fatura_bp.route("/fatura/<int:fatura_id>/fechar", methods=["POST"])
@login_required
def fechar_fatura(fatura_id):
    fatura = _buscar_fatura_ou_404(fatura_id)
    try:
        mensagem = fatura_service.fechar_fatura(
            fatura, usuario_id=current_user.id, familia_id=current_user.familia_id
        )
        flash(mensagem, "success")
    except fatura_service.FaturaJaFechadaError as e:
        flash(str(e), "info")
    return redirect(request.referrer or url_for("cartao.listar_movimentacoes_cartao"))


@fatura_bp.route('/fatura/<int:fatura_id>/reabrir', methods=['POST'])
@login_required
def reabrir_fatura(fatura_id):
    fatura = _buscar_fatura_ou_404(fatura_id)
    try:
        mensagem = fatura_service.reabrir_fatura(fatura, familia_id=current_user.familia_id)
        flash(mensagem, "success")
    except fatura_service.FaturaJaAbertaError as e:
        flash(str(e), "info")
    return redirect(request.referrer or url_for('cartao.listar_movimentacoes_cartao'))


@fatura_bp.route('/fatura/<int:fatura_id>/pagar', methods=['POST'])
@login_required
def pagar_fatura(fatura_id):
    fatura = _buscar_fatura_ou_404(fatura_id)

    conta_id = request.form.get('conta_id')
    valor_str = request.form.get('valor', '0').replace(',', '.')
    data_pagamento_str = request.form.get('data_pagamento')

    if not conta_id or not valor_str or not data_pagamento_str:
        flash("Todos os campos são obrigatórios.", "danger")
        return redirect(request.referrer or url_for("cartao.listar_movimentacoes_cartao"))

    try:
        dados = fatura_service.PagamentoFaturaInput(
            conta_id=int(conta_id),
            valor=Decimal(valor_str),
            data_pagamento=datetime.strptime(data_pagamento_str, "%Y-%m-%d").date(),
        )
    except (ValueError, InvalidOperation):
        flash("Dados inválidos. Verifique os campos e tente novamente.", "danger")
        return redirect(request.referrer or url_for("cartao.listar_movimentacoes_cartao"))

    try:
        mensagem = fatura_service.pagar_fatura(
            fatura, dados, usuario_id=current_user.id, familia_id=current_user.familia_id
        )
        flash(mensagem, "warning" if "parcial" in mensagem else "success")
    except fatura_service.FaturaPrecisaEstarFechadaError as e:
        flash(str(e), "warning")
    except fatura_service.FaturaSemSaldoError as e:
        flash(str(e), "info")
    except fatura_service.FaturaServiceError as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"Erro ao pagar fatura: {str(e)}", "danger")

    return redirect(request.referrer or url_for("cartao.listar_movimentacoes_cartao"))


@fatura_bp.route('/fatura/<int:fatura_id>/estornar', methods=['POST'])
@login_required
def estornar_pagamento(fatura_id):
    fatura = _buscar_fatura_ou_404(fatura_id)
    try:
        mensagem = fatura_service.estornar_pagamento(
            fatura, familia_id=current_user.familia_id, usuario_id=current_user.id
        )
        flash(mensagem, "success")
    except fatura_service.SemPagamentoParaEstornarError as e:
        flash(str(e), "warning")
    except Exception as e:
        flash(f"Erro ao estornar pagamento: {str(e)}", "danger")

    return redirect(request.referrer or url_for("cartao.listar_movimentacoes_cartao"))


@fatura_bp.route('/fatura_nome/<int:mes>/<int:ano>', methods=['GET'])
@login_required
def obter_nome_fatura(mes, ano):
    meses = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
        7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    nome = meses.get(mes, "Desconhecido")
    return jsonify({"texto": f"{nome}/{ano} (Fatura Original)"})