import os
from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (Conexão com PostgreSQL)
load_dotenv()

from app import create_app
from app.models import db, MovimentacaoCartao, Categoria, MeioPagamento, Usuario
from app.routes.faturas import calcular_fatura_para_compra

app = create_app()

# === LISTA COMPLETA DAS PARCELAS FUTURAS MAPEADAS DO SEU EXCEL ===
compras_para_projetar = [
    {"nome_base": "O Boticário", "valor": 50.70, "cartao": "Nubank", "categoria": "Higiene/Perfumaria", "parcela_inicial": 3, "total_parcelas": 4, "data_proxima_parcela": date(2026, 7, 15)},
    {"nome_base": "Temu", "valor": 17.58, "cartao": "Pic Pay", "categoria": "Roupas/Calçados", "parcela_inicial": 3, "total_parcelas": 6, "data_proxima_parcela": date(2026, 7, 8)},
    {"nome_base": "Pratika", "valor": 63.34, "cartao": "Pic Pay", "categoria": "Remédios", "parcela_inicial": 3, "total_parcelas": 3, "data_proxima_parcela": date(2026, 7, 7)},
    {"nome_base": "Senac", "valor": 37.80, "cartao": "Pic Pay", "categoria": "Educação", "parcela_inicial": 3, "total_parcelas": 12, "data_proxima_parcela": date(2026, 7, 4)},
    {"nome_base": "Ultrafarma", "valor": 21.93, "cartao": "Pic Pay", "categoria": "Remédios", "parcela_inicial": 3, "total_parcelas": 3, "data_proxima_parcela": date(2026, 6, 30)},
    {"nome_base": "Espaço Laser", "valor": 153.75, "cartao": "Pic Pay", "categoria": "Beleza/Estética", "parcela_inicial": 4, "total_parcelas": 16, "data_proxima_parcela": date(2026, 7, 6)},
    {"nome_base": "Óculos", "valor": 70.00, "cartao": "Pic Pay", "categoria": "Saúde", "parcela_inicial": 9, "total_parcelas": 10, "data_proxima_parcela": date(2026, 7, 3)},
]

with app.app_context():
    print("\n🚀 Iniciando a projeção de faturas futuras no PostgreSQL...\n")
    
    usuario = Usuario.query.first()

    for item in compras_para_projetar:
        print(f"🔄 Projetando: {item['nome_base']} (Restam {item['total_parcelas'] - item['parcela_inicial'] + 1} parcelas)")
        
        cartao = MeioPagamento.query.filter(MeioPagamento.nome.ilike(f"%{item['cartao'].replace(' ', '%')}%")).first()
        categoria = Categoria.query.filter_by(nome=item['categoria']).first()

        if not cartao or not categoria:
            print(f"  ❌ Erro: Cartão ou Categoria não encontrados para {item['nome_base']}")
            continue

        data_atual_laco = item["data_proxima_parcela"]
        
        # Converte o valor para Decimal de forma segura antes de entrar no laço
        valor_decimal = Decimal(str(item["valor"]))

        for parcela in range(item["parcela_inicial"], item["total_parcelas"] + 1):
            
            descricao_formatada = f"{item['nome_base']} {parcela:02d}/{item['total_parcelas']:02d}"
            fatura = calcular_fatura_para_compra(cartao.id, data_atual_laco)

            nova_mov = MovimentacaoCartao(
                descricao=descricao_formatada,
                valor=valor_decimal,  # Usa o valor convertido
                data_compra=data_atual_laco,
                cartao_id=cartao.id,
                categoria_id=categoria.id,
                usuario_id=usuario.id,
                numero_parcelas=item["total_parcelas"],
                parcela_atual=parcela,
                fatura_id=fatura.id
            )
            db.session.add(nova_mov)
            fatura.saldo += valor_decimal  # Soma Decimal com Decimal

            print(f"  ✅ Lançada: {descricao_formatada} | Fatura: {fatura.mes}/{fatura.ano}")

            data_atual_laco = data_atual_laco + relativedelta(months=1)

    db.session.commit()
    print("\n🎉 Todas as parcelas futuras foram criadas e as faturas ajustadas!")