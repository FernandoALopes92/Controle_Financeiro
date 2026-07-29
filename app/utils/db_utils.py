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
        Categoria.familia_id == current_user.familia_id
    )

    # Se quem chamou a função pediu um tipo específico, aplica o filtro
    if tipo:
        query = query.filter(Categoria.tipo == tipo)

    return query.order_by(Categoria.nome.asc()).all()

def get_contas():
    """Retorna todas as contas ATIVAS e que pertencem à FAMÍLIA do usuário logado."""
    return Conta.query.filter_by(
        familia_id=current_user.familia_id, 
        status=True
    ).order_by(Conta.nome.asc()).all()

def filtrar_por_mes_ano(query, campo_data, mes, ano):
    """Filtra uma query pelo campo de data, mês e ano."""
    return query.filter(
        extract('month', campo_data) == mes,
        extract('year', campo_data) == ano
    )