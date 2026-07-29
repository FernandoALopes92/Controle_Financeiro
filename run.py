from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    # CORREÇÃO: debug nunca fixo em True no código — controlado por variável de
    # ambiente, para nunca ficar ligado por engano se o app for exposto além do
    # localhost (o debugger interativo do Werkzeug permite rodar código arbitrário)
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode)