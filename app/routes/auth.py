from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, LoginManager
from app.models import Usuario
from app import db

login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

auth = Blueprint('auth', __name__, url_prefix='/auth')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('main.dashboard'))  # redireciona para o dashboard
        else:
            flash('Email ou senha incorretos.', 'danger')

    return render_template('login.html')

@auth.route('/logout')
def logout():
    logout_user()
    flash('Você saiu da conta.', 'info')
    return redirect(url_for('auth.login'))
