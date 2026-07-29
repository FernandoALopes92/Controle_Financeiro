"""Adiciona índices de performance nas colunas de família e chaves estrangeiras

Revision ID: 844b67b1c0b7
Revises: f862d0888b38
Create Date: 2026-07-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '844b67b1c0b7'
down_revision = 'f862d0888b38'
branch_labels = None
depends_on = None

# Lista de (tabela, coluna) que ganharam índice — corresponde aos
# campos que o app filtra o tempo todo (familia_id em toda consulta,
# mais as chaves estrangeiras mais usadas em cada tabela de movimentação)
INDICES = [
    ('usuarios', 'familia_id'),
    ('contas', 'familia_id'),
    ('meios_pagamento', 'familia_id'),
    ('categorias', 'familia_id'),
    ('movimentacoes', 'categoria_id'),
    ('movimentacoes', 'conta_id'),
    ('movimentacoes', 'familia_id'),
    ('movimentacoes_cartao', 'cartao_id'),
    ('movimentacoes_cartao', 'categoria_id'),
    ('movimentacoes_cartao', 'fatura_id'),
    ('movimentacoes_cartao', 'familia_id'),
    ('faturas', 'cartao_id'),
    ('faturas', 'familia_id'),
    ('pagamentos_fatura', 'conta_id'),
    ('pagamentos_fatura', 'fatura_id'),
    ('pagamentos_fatura', 'familia_id'),
    ('transferencias', 'conta_origem_id'),
    ('transferencias', 'conta_destino_id'),
    ('transferencias', 'familia_id'),
    ('orcamentos_mensais', 'familia_id'),
]


def upgrade():
    # ### índices adicionados manualmente (correção de performance) ###
    for tabela, coluna in INDICES:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.create_index(f'ix_{tabela}_{coluna}', [coluna], unique=False)
    # ### end ###


def downgrade():
    # ### remove os índices na ordem inversa ###
    for tabela, coluna in reversed(INDICES):
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.drop_index(f'ix_{tabela}_{coluna}')
    # ### end ###