from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user
from app.models import Usuario
from app.utils import login_throttle

auth = Blueprint('auth', __name__, url_prefix='/auth')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        senha = request.form.get('senha') or ''
        ip = request.remote_addr or 'desconhecido'
        limitar = current_app.config.get('LOGIN_THROTTLE_ENABLED', True)

        # Muitas tentativas erradas seguidas: bloqueia por alguns minutos,
        # mesmo que a próxima tentativa fosse a senha certa.
        espera = login_throttle.segundos_restantes(email, ip) if limitar else 0
        if espera:
            minutos = max(1, (espera + 59) // 60)
            flash(f'Muitas tentativas de login. Tente novamente em {minutos} minuto(s).', 'danger')
            return render_template('login.html'), 429

        usuario = Usuario.query.filter_by(email=email).first() if email and senha else None

        if usuario and usuario.verificar_senha(senha):
            login_throttle.limpar(email, ip)
            login_user(usuario)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('main.dashboard'))  # redireciona para o dashboard

        if limitar:
            login_throttle.registrar_falha(email, ip)
        flash('Email ou senha incorretos.', 'danger')

    return render_template('login.html')


# POST (e não GET): um link/imagem em outro site não consegue deslogar o usuário.
@auth.route('/logout', methods=['POST'])
def logout():
    logout_user()
    flash('Você saiu da conta.', 'info')
    return redirect(url_for('auth.login'))
