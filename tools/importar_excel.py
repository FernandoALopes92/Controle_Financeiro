# importar_excel.py
import re
from datetime import date
from decimal import Decimal
from app import create_app
from app.models import db, MovimentacaoCartao, Categoria, MeioPagamento, Usuario
from app.services.cartao_service import calcular_fatura_para_compra
from dateutil.relativedelta import relativedelta

app = create_app()

# Dicionário para converter o mês em texto para número
meses_map = {
    'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12
}

# Colei os seus dados exatamente como você mandou
dados_brutos = """
20/ago	Mercado Livre	Outros	Pic Pay	 R$ 38,00 
26/ago	Uber/99	Uber/99	Nubank 	 R$ 6,38 
26/ago	Uber/99	Uber/99	Nubank 	 R$ 5,21 
26/ago	Jrea Cafeteria	Lanches/Besteiras	Nubank 	 R$ 3,00 
26/ago	Marcelo Santana	Lanches/Besteiras	Nubank 	 R$ 3,50 
25/ago	Mrt Distribuidora	Lanches/Besteiras	Nubank 	 R$ 6,50 
25/ago	Uber/99	Uber/99	Nubank 	 R$ 5,26 
25/ago	Mercado União	Lanches/Besteiras	Nubank 	 R$ 6,98 
25/ago	Uber/99	Uber/99	Nubank 	 R$ 4,93 
25/ago	Marcelo Santana	Lanches/Besteiras	Nubank 	 R$ 3,50 
25/ago	Bolo	Lanches/Besteiras	Nubank 	 R$ 12,00 
25/ago	Uber/99	Uber/99	Nubank 	 R$ 5,96 
25/ago	Uber/99	Uber/99	Nubank 	 R$ 5,68 
25/ago	Keetah Sushi	Lanches/Besteiras	Nubank 	 R$ 39,87 
24/ago	Açaí	Lanches/Besteiras	Nubank 	 R$ 9,00 
24/ago	Gás	Contas de Casa	Nubank 	 R$ 110,00 
24/ago	Pequena Artesã	Presentes	Nubank 	 R$ 80,00 
23/ago	Jogo PSN 	Lazer	Nubank 	 R$ 15,95 
22/ago	Marcelo Santana	Lanches/Besteiras	Nubank 	 R$ 2,00 
22/ago	Uber/99	Uber/99	Nubank 	 R$ 6,96 
22/ago	Salgado	Lanches/Besteiras	Nubank 	 R$ 13,00 
22/ago	Salgados Nene	Lanches/Besteiras	Nubank 	 R$ 7,00 
22/ago	Takahashi	Mercado	Nubank 	 R$ 8,98 
22/ago	Uber/99	Uber/99	Nubank 	 R$ 6,95 
21/ago	Supermercado x	Lanches/Besteiras	Nubank 	 R$ 7,98 
21/ago	Marcelo Santana	Lanches/Besteiras	Nubank 	 R$ 2,00 
21/ago	Uber/99	Uber/99	Nubank 	 R$ 6,96 
13/ago	Mercado Livre	Roupas/Calçados	Pic Pay	 R$ 46,39 
12/ago	Via naturale	Lanches/Besteiras	Pic Pay	 R$ 14,00 
11/ago	Sampa Tatoo	Piercings/Bijuterias	Pic Pay	 R$ 50,00 
11/ago	RPG Comercio de alimentos	Lanches/Besteiras	Pic Pay	 R$ 33,00 
11/ago	Itaquera Lanches	Lanches/Besteiras	Pic Pay	 R$ 6,00 
11/ago	Uber/99	Uber/99	Pic Pay	 R$ 6,14 
10/ago	Uber/99	Uber/99	Pic Pay	 R$ 11,07 
10/ago	Uber/99	Uber/99	Pic Pay	 R$ 5,24 
09/ago	Uber/99	Uber/99	Pic Pay	 R$ 16,30 
08/ago	Sushi	Lanches/Besteiras	Pic Pay	 R$ 38,75 
08/ago	Adega	Lanches/Besteiras	Pic Pay	 R$ 12,00 
07/ago	Salgados	Lanches/Besteiras	Pic Pay	 R$ 6,00 
07/ago	Uber/99	Uber/99	Pic Pay	 R$ 6,37 
07/ago	Hikari	Lanches/Besteiras	Pic Pay	 R$ 9,50 
20/ago	Bolo	Lanches/Besteiras	Nubank 	 R$ 12,00 
20/ago	Uber/99	Uber/99	Nubank 	 R$ 9,77 
20/ago	Uber/99	Uber/99	Nubank 	 R$ 6,93 
20/ago	Uber/99	Uber/99	Nubank 	 R$ 6,96 
20/ago	Sorvete	Lanches/Besteiras	Nubank 	 R$ 4,50 
19/ago	Drogaria SP	Remédios	Nubank 	 R$ 9,59 
19/ago	Supermix	Lanches/Besteiras	Nubank 	 R$ 6,75 
19/ago	Uber/99	Uber/99	Nubank 	 R$ 5,96 
19/ago	May bustani	Lanches/Besteiras	Nubank 	 R$ 20,00 
18/ago	Uber/99	Uber/99	Nubank 	 R$ 6,94 
18/ago	Tokai variedades	Lanches/Besteiras	Nubank 	 R$ 10,00 
18/ago	Salgados	Lanches/Besteiras	Nubank 	 R$ 13,00 
18/ago	Thatas confeitaria	Lanches/Besteiras	Nubank 	 R$ 8,50 
18/ago	Uber/99	Uber/99	Nubank 	 R$ 6,96 
17/ago	Uber/99	Uber/99	Nubank 	 R$ 6,10 
17/ago	Rosangela dos santos	Feira	Nubank 	 R$ 5,00 
17/ago	Aracadão	Mercado	Nubank 	 R$ 536,05 
17/ago	Frutas/legumes	Feira	Nubank 	 R$ 10,00 
17/ago	Caldo de Cana	Lanches/Besteiras	Nubank 	 R$ 10,00 
17/ago	Café	Lanches/Besteiras	Nubank 	 R$ 2,00 
17/ago	Uber/99	Uber/99	Nubank 	 R$ 7,62 
17/ago	Shopee	Papelaria	Nubank 	 R$ 31,90 
17/ago	Uber/99	Uber/99	Nubank 	 R$ 6,02 
17/ago	Padaria Wagmar	Padaria	Nubank 	 R$ 33,10 
16/ago	Lenilza	Lanches/Besteiras	Nubank 	 R$ 2,00 
16/ago	Kiko Alimentos	Lanches/Besteiras	Nubank 	 R$ 45,43 
15/ago	Uber/99	Uber/99	Nubank 	 R$ 5,97 
15/ago	Marcelo Santana	Lanches/Besteiras	Nubank 	 R$ 2,00 
15/ago	Rei do comercio	Lanches/Besteiras	Nubank 	 R$ 10,00 
15/ago	Salgados	Lanches/Besteiras	Nubank 	 R$ 6,00 
15/ago	Rei do comercio	Lanches/Besteiras	Nubank 	 R$ 3,00 
14/ago	Bolo	Lanches/Besteiras	Nubank 	 R$ 12,00 
14/ago	Uber/99	Uber/99	Nubank 	 R$ 5,20 
13/ago	Uber/99	Uber/99	Nubank 	 R$ 4,72 
12/ago	Uber/99	Uber/99	Nubank 	 R$ 5,20 
12/ago	Uber/99	Uber/99	Nubank 	 R$ 13,82 
12/ago	Uber/99	Uber/99	Nubank 	 R$ 5,22 
12/ago	Bolo	Lanches/Besteiras	Nubank 	 R$ 12,00 
06/ago	Uber/99	Uber/99	Pic Pay	 R$ 4,72 
06/ago	Uber/99	Uber/99	Pic Pay	 R$ 5,95 
05/ago	Veneno Formiga 	Consertos/Manutenção	Pic Pay	 R$ 6,00 
05/ago	Uber/99	Uber/99	Pic Pay	 R$ 4,72 
04/ago	Uber/99	Uber/99	Pic Pay	 R$ 5,20 
03/ago	Bolo	Lanches/Besteiras	Pic Pay	 R$ 12,00 
02/ago	Milk Moo	Lanches/Besteiras	Pic Pay	 R$ 26,00 
02/ago	Pipoca	Lanches/Besteiras	Pic Pay	 R$ 41,00 
02/ago	Nagumo	Lanches/Besteiras	Pic Pay	 R$ 27,85 
01/ago	Salao Glamour	Beleza/Estética	Pic Pay	 R$ 213,00 
31/jul	Refrigerante	Lanches/Besteiras	Pic Pay	 R$ 8,00 
31/jul	Padaria	Padaria	Pic Pay	 R$ 31,20 
31/jul	Caldo de Cana	Lanches/Besteiras	Pic Pay	 R$ 7,00 
31/jul	Frutas/legumes	Feira	Pic Pay	 R$ 5,00 
31/jul	Frutas/legumes	Feira	Pic Pay	 R$ 5,00 
31/jul	Frutas/legumes	Feira	Pic Pay	 R$ 20,00 
31/jul	Frutas/legumes	Feira	Pic Pay	 R$ 12,00 
31/jul	Takahashi	Lanches/Besteiras	Pic Pay	 R$ 13,97 
31/jul	Açaí	Lanches/Besteiras	Pic Pay	 R$ 15,00 
31/jul	Roupas	Roupas/Calçados	Pic Pay	 R$ 39,98 
22/ago	Estorno Temu	Piercings/Bijuterias	Nubank 	-R$38,95 
22/ago	Estorno Temu	Piercings/Bijuterias	Nubank 	-R$10,00 
22/ago	Estorno Temu	Piercings/Bijuterias	Nubank 	-R$48,85 
18/ago	Estorno calcinha	Roupas/Calçados	Nubank 	-R$94,10 
"""

# Defina o ano em que essas compras aconteceram
ANO_COMPRA = 2026

with app.app_context():
    # Pega o primeiro usuário do banco (você)
    usuario = Usuario.query.first()
    
    # Busca a categoria padrão caso a linha não tenha categoria definida
    cat_outros = Categoria.query.filter_by(nome="Outros", familia_id=usuario.familia_id).first()
    
    ultima_data = None
    
    linhas = dados_brutos.strip().split('\n')
    print(f"🚀 Iniciando importação de {len(linhas)} registros...")

    for linha in linhas:
        partes = linha.split('\t')
        
        # Tratamento para quando a data está vazia (ex: Claro, Dentista)
        data_str = partes[0].strip()
        if data_str:
            dia_str, mes_str = data_str.split('/')
            mes_num = meses_map[mes_str.lower()]
            data_compra = date(ANO_COMPRA, mes_num, int(dia_str))
            ultima_data = data_compra
        else:
            data_compra = ultima_data

        descricao = partes[1].strip()
        categoria_nome = partes[2].strip() if len(partes) > 2 else ""
        cartao_nome = partes[3].strip() if len(partes) > 3 else ""
        valor_str = partes[4].strip() if len(partes) > 4 else "0"

        # Formata o valor (Tira o R$ e troca vírgula por ponto)
        valor_limpo = valor_str.replace("R$", "").replace(".", "").replace(",", ".").strip()
        valor = Decimal(valor_limpo)

        # Identifica o Cartão
        cartao = MeioPagamento.query.filter_by(nome=cartao_nome).first()
        if not cartao:
            print(f"⚠️ Cartão '{cartao_nome}' não encontrado. Pulando: {descricao}")
            continue

        # Identifica a Categoria
        categoria = Categoria.query.filter_by(nome=categoria_nome).first()
        categoria_id = categoria.id if categoria else (cat_outros.id if cat_outros else None)

        # Expressão Regular para encontrar o parcelamento na descrição (ex: 01/02)
        match = re.search(r'(\d{2})/(\d{2})$', descricao)
        if match:
            parcela_atual = int(match.group(1))
            numero_parcelas = int(match.group(2))
        else:
            parcela_atual = 1
            numero_parcelas = 1

        # A MAGIA AQUI: Calcula a data em que esta parcela específica vai cair
        data_parcela = data_compra + relativedelta(months=(parcela_atual - 1))

        # Calcula a fatura correta baseada na DATA DA PARCELA (e não na compra original)
        fatura = calcular_fatura_para_compra(cartao.id, data_parcela, usuario.familia_id)
        # Cria a movimentação
        nova_mov = MovimentacaoCartao(
            descricao=descricao,
            valor=valor,
            data_compra=data_compra, # A data original fica salva para o seu histórico
            cartao_id=cartao.id,
            categoria_id=categoria_id,
            usuario_id=usuario.id,
            familia_id=usuario.familia_id,
            numero_parcelas=numero_parcelas,
            parcela_atual=parcela_atual,
            fatura_id=fatura.id
        )
        db.session.add(nova_mov)
        
        # Atualiza o saldo da fatura
        fatura.saldo += valor
        print(f"✅ Lançado: {descricao} | Compra: {data_compra.strftime('%d/%m')} | Parcela em: {data_parcela.strftime('%d/%m')} | Fat: {fatura.mes}/{fatura.ano}")

    db.session.commit()
    print("\n🎉 Importação concluída com sucesso!")