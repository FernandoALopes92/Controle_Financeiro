from app import create_app
from app.models import db, MovimentacaoCartao, Fatura

app = create_app()

with app.app_context():
    print("🧹 Iniciando limpeza dos dados de cartão...")
    
    # Apaga todas as movimentações de cartão
    apagados_mov = MovimentacaoCartao.query.delete()
    
    # Apaga todas as faturas (para zerar os saldos e elas serem recriadas do zero)
    apagadas_fat = Fatura.query.delete()
    
    db.session.commit()
    
    print(f"✅ Limpeza concluída!")
    print(f"   - {apagados_mov} movimentações excluídas.")
    print(f"   - {apagadas_fat} faturas excluídas.")