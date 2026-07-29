from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, CheckConstraint, Numeric
from flask_login import UserMixin
from datetime import date, datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal



db = SQLAlchemy()

class Familia(db.Model):
    __tablename__ = 'familias'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    criado_em = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))  # CORREÇÃO: datetime.utcnow() está sendo descontinuado pelo Python

    # Relacionamentos (Opcional, mas ajuda no SQLAlchemy)
    usuarios = db.relationship('Usuario', backref='familia_rel', lazy=True)

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False, index=True)  # CORREÇÃO: índice para acelerar filtros por família
    email = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.Text, nullable=False)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Conta(db.Model):
    __tablename__ = 'contas'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    data = db.Column(db.Date, nullable=False)
    saldo_inicial = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))
    saldo_atual = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    status = db.Column(db.Boolean, default=True)
    tipo = db.Column(db.String(50))
    logo = db.Column(db.String(200))  # nome do arquivo
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False, index=True)  # CORREÇÃO: índice para acelerar filtros por família

class MeioPagamento(db.Model):
    __tablename__ = 'meios_pagamento'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    logo = db.Column(db.String(200))  # nome do arquivo
    tipo = db.Column(db.String(50), nullable=False)
    limite = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))
    fechamento_dia = db.Column(db.Integer)
    vencimento_dia = db.Column(db.Integer)
    status = db.Column(db.Boolean, default=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False, index=True)  # CORREÇÃO: índice para acelerar filtros por família



class Categoria(db.Model):
    __tablename__ = 'categorias'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    status = db.Column(db.Boolean, default=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False, index=True)  # CORREÇÃO: índice para acelerar filtros por família


    # A MAGIA ESTÁ AQUI: Aponta para o ID da própria tabela de categorias
    categoria_pai_id = db.Column(db.Integer, db.ForeignKey('categorias.id', ondelete='CASCADE'), nullable=True)

    # Relacionamento para o Flask conseguir buscar as subcategorias facilmente
    subcategorias = db.relationship(
        'Categoria', 
        backref=db.backref('pai', remote_side=[id]), 
        lazy='joined'
    )


class Movimentacao(db.Model):
    __tablename__ = 'movimentacoes'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    data = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), index=True)  # CORREÇÃO: índice, coluna muito filtrada em relatórios
    tipo = db.Column(db.String, nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    conta_id = db.Column(db.Integer, db.ForeignKey('contas.id'), index=True)  # CORREÇÃO: índice, coluna muito filtrada nas telas de movimentação
    pago = db.Column(db.Boolean, nullable=True, default=None)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False, index=True)  # CORREÇÃO: índice, toda consulta do sistema filtra por família



    pagamento_fatura_id = db.Column(
        db.Integer, db.ForeignKey('pagamentos_fatura.id'), nullable=True
    )

    @property
    def cor_valor(self):
        if self.descricao.startswith("Saída - Transferência"):
            return "text-danger"
        elif self.descricao.startswith("Entrada - Transferência"):
            return "text-success"
        elif self.tipo == "receita":
            return "text-success"
        elif self.tipo == "despesa":
            return "text-danger"
        return ""

    usuario = db.relationship("Usuario", backref="movimentacoes")
    categoria = db.relationship("Categoria", backref="movimentacoes")
    conta = db.relationship("Conta", backref="movimentacoes")
    pagamento_fatura = db.relationship("PagamentoFatura", backref="movimentacao", uselist=False)


    __table_args__ = (
        CheckConstraint(
            tipo.in_(['despesa', 'receita', 'transferencia']),
            name='movimentacoes_tipo_check'
        ),
    )
    

class MovimentacaoCartao(db.Model):
    __tablename__ = 'movimentacoes_cartao'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    cartao_id = db.Column(db.Integer, db.ForeignKey('meios_pagamento.id'), nullable=False, index=True)  # CORREÇÃO: índice, muito filtrado em faturas/relatórios
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), index=True)  # CORREÇÃO: índice, coluna muito filtrada em relatórios
    descricao = db.Column(db.Text, nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    data_compra = db.Column(db.Date, nullable=False)
    numero_parcelas = db.Column(db.Integer, default=1)
    compra_grupo_id = db.Column(db.String(36), nullable=True)
    parcela_atual = db.Column(db.Integer, default=1)
    fatura_id = db.Column(db.Integer, db.ForeignKey('faturas.id'), index=True)  # CORREÇÃO: índice, usado para recalcular saldo de fatura
    criado_em = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False, index=True)  # CORREÇÃO: índice, toda consulta do sistema filtra por família


    usuario = db.relationship("Usuario", backref="movimentacoes_cartao")
    cartao = db.relationship("MeioPagamento", backref="movimentacoes_cartao")
    categoria = db.relationship("Categoria", backref="movimentacoes_cartao")

    __table_args__ = (
        # UniqueConstraint('cartao_id', 'data_compra', 'descricao', 'parcela_atual', name='uq_cartao_data_desc_parcela'),
        CheckConstraint('parcela_atual <= numero_parcelas', name='check_parcela_atual_menor_igual_total'),
    )


class Fatura(db.Model):
    __tablename__ = 'faturas'

    id = db.Column(db.Integer, primary_key=True)
    cartao_id = db.Column(db.Integer, db.ForeignKey('meios_pagamento.id'), nullable=False, index=True)  # CORREÇÃO: índice, muito filtrado ao localizar fatura de um cartão
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    data_fechamento = db.Column(db.Date)
    data_vencimento = db.Column(db.Date)
    saldo = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    status = db.Column(db.String(20), default='aberta', nullable=False)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False, index=True)  # CORREÇÃO: índice, toda consulta do sistema filtra por família


    def atualizar_saldo(self):
        self.saldo = sum(m.valor for m in self.movimentacoes_cartao)

    movimentacoes = db.relationship("MovimentacaoCartao", backref="fatura", lazy=True)
    cartao = db.relationship('MeioPagamento', backref='faturas')

    __table_args__ = (
    db.UniqueConstraint('cartao_id', 'mes', 'ano', name='uq_fatura_cartao_mes_ano'),
)


class PagamentoFatura(db.Model):
    __tablename__ = 'pagamentos_fatura'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    conta_id = db.Column(db.Integer, db.ForeignKey('contas.id'), nullable=False, index=True)  # CORREÇÃO: índice
    fatura_id = db.Column(db.Integer, db.ForeignKey('faturas.id'), nullable=False, index=True)  # CORREÇÃO: índice
    valor_pago = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    data_pagamento = db.Column(db.Date, nullable=False)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False, index=True)  # CORREÇÃO: índice, toda consulta do sistema filtra por família


    usuario = db.relationship("Usuario", backref="pagamentos_fatura")
    conta = db.relationship("Conta", backref="pagamentos_fatura")
    fatura = db.relationship("Fatura", backref="pagamentos")


class Transferencia(db.Model):
    __tablename__ = 'transferencias'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    conta_origem_id = db.Column(db.Integer, db.ForeignKey('contas.id'), nullable=False, index=True)  # CORREÇÃO: índice
    conta_destino_id = db.Column(db.Integer, db.ForeignKey('contas.id'), nullable=False, index=True)  # CORREÇÃO: índice
    valor = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    data_transferencia = db.Column(db.Date, nullable=False)
    observacoes = db.Column(db.Text)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False, index=True)  # CORREÇÃO: índice, toda consulta do sistema filtra por família


    usuario = db.relationship("Usuario", backref="transferencias")
    conta_origem = db.relationship("Conta", foreign_keys=[conta_origem_id], backref="transferencias_origem")
    conta_destino = db.relationship("Conta", foreign_keys=[conta_destino_id], backref="transferencias_destino")

class OrcamentoMensal(db.Model):
    __tablename__ = 'orcamentos_mensais'

    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False, index=True)  # CORREÇÃO: índice, toda consulta do sistema filtra por família
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    
    # A meta global de poupança daquele mês específico (padrão 50%)
    meta_poupanca_percentual = db.Column(db.Numeric(5, 2), default=Decimal('50.00'))