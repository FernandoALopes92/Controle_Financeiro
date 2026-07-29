import os
from flask import Flask, app, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from app.models import db, Usuario
from dotenv import load_dotenv
from . import models
from flask_migrate import Migrate

# Carrega variáveis de ambiente do .env
load_dotenv()

# Instâncias globais
login_manager = LoginManager()
csrf = CSRFProtect()

#formatar para Moeda BRL
def formata_moeda_br(valor):
    if valor is None:
        valor = 0.0
    valor_americano = f"{valor:,.2f}"
    return valor_americano.replace(",", "X").replace(".", ",").replace("X", ".")


def create_app(config_overrides=None):
    app = Flask(__name__)

    # Configurações do app
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Boa prática para evitar warning

    # Usado pelos testes automatizados para trocar o banco por um de teste
    # (em memória), sem nunca tocar no banco Postgres de verdade.
    if config_overrides:
        app.config.update(config_overrides)
    

    # 2. REGISTRE O FILTRO AQUI (Dentro do create_app)
    app.jinja_env.filters['brl'] = formata_moeda_br

    # Inicializa extensões
    db.init_app(app)
    migrate = Migrate(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # Nome da rota de login
    csrf.init_app(app)  # Proteção contra CSRF em todos os formulários POST/PUT/DELETE

    # Registra a função que carrega o usuário logado
    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # Registra blueprints
    from app.routes.auth import auth
    from app.routes.dashboard import main_bp
    from app.routes.contas import contas_bp
    from app.routes.categorias import categorias_bp
    from app.routes.meios_pagamento import meios_pagamento_bp
    from app.routes.movimentacoes import movimentacoes_bp
    from app.routes.cartao import cartao_bp
    from app.routes.transferencias import transferencias_bp
    from app.routes.faturas import fatura_bp
    from app.routes.relatorios import relatorios_bp

    app.register_blueprint(auth) # Registra o blueprint do Login
    app.register_blueprint(main_bp)  # Registra o blueprint do dashboard
    app.register_blueprint(contas_bp) # Registra o blueprint das Contas
    app.register_blueprint(categorias_bp) # Registra o blueprint das Categorias
    app.register_blueprint(meios_pagamento_bp) # Registra o blueprint dos Meios de Pagamento
    app.register_blueprint(movimentacoes_bp) # Registra o blueprint das Movimentações
    app.register_blueprint(cartao_bp) # Registra o blueprint dos Cartões de Crédito
    app.register_blueprint(transferencias_bp) # Registra o blueprint das Transferências
    app.register_blueprint(fatura_bp) # Registra o blueprint das Faturas
    app.register_blueprint(relatorios_bp) # Registra o blueprint dOS Relatórios


    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))  

    return app