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
03/ago	Lojas Americanas	Lanches/Besteiras	Nubank 	 R$ 16,98 
02/ago	Cinema	Lazer	Nubank 	 R$ 36,48 
27/jul	Uber/99	Uber/99	Pic Pay	 R$ 7,74 
27/jul	Uber/99	Uber/99	Pic Pay	 R$ 8,82 
31/jul	Atual Moda	Roupas/Calçados	Nubank 	 R$ 79,99 
30/jul	Xereta	Lanches/Besteiras	Nubank 	 R$ 4,49 
30/jul	Xereta	Lanches/Besteiras	Nubank 	 R$ 11,50 
30/jul	Caedu	Gastos não previstos	Nubank 	 R$ 12,92 
30/jul	Uber/99	Uber/99	Nubank 	 R$ 7,06 
29/jul	Salgados	Lanches/Besteiras	Nubank 	 R$ 5,00 
29/jul	Sorvete	Lanches/Besteiras	Nubank 	 R$ 9,98 
28/jul	Bolo	Lanches/Besteiras	Nubank 	 R$ 12,00 
28/jul	Doces	Lanches/Besteiras	Nubank 	 R$ 7,00 
28/jul	Uber/99	Uber/99	Nubank 	 R$ 17,94 
28/jul	Uber/99	Uber/99	Nubank 	 R$ 6,93 
28/jul	Padaria	Padaria	Nubank 	 R$ 12,00 

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