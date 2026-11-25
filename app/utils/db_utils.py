from app.models import MeioPagamento, Categoria, Conta
from sqlalchemy import extract
from flask_login import current_user # Precisamos disso para saber qual família está logada

def get_meios_pagamento():
    """Retorna os meios de pagamento que pertencem à FAMÍLIA do usuário logado."""
    return MeioPagamento.query.filter_by(
        familia_id=current_user.familia_id
    ).order_by(MeioPagamento.nome.asc()).all()

def get_categorias(tipo=None):
    """Retorna categorias filhas da FAMÍLIA do usuário logado, podendo filtrar por tipo (receita/despesa)."""
    query = Categoria.query.filter(
        Categoria.categoria_pai_id.isnot(None),
        Categoria.familia_id == current_user.familia_id,
        Categoria.status.is_(True),
    )

    # Se quem chamou a função pediu um tipo específico, aplica o filtro
    if tipo:
        query = query.filter(Categoria.tipo == tipo)

    return query.order_by(Categoria.nome.asc()).all()

def get_contas(incluir_inativas=False):
    """Retorna as contas da FAMÍLIA do usuário logado (por padrão só as ATIVAS).

    Com incluir_inativas=True (tela de Contas) as inativas vêm no fim da lista,
    para poderem ser reativadas."""
    query = Conta.query.filter_by(familia_id=current_user.familia_id)
    if not incluir_inativas:
        return query.filter_by(status=True).order_by(Conta.saldo_atual.desc()).all()
    return query.order_by(Conta.status.desc(), Conta.saldo_atual.desc()).all()

def filtrar_por_mes_ano(query, campo_data, mes, ano):
    """Filtra uma query pelo campo de data, mês e ano."""
    return query.filter(
        extract('month', campo_data) == mes,
        extract('year', campo_data) == ano
    )