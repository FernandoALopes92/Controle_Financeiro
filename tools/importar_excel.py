# importar_excel.py
import re
import uuid
from datetime import date
from decimal import Decimal
from app import create_app
from app.models import db, MovimentacaoCartao, Categoria, MeioPagamento, Usuario
from app.services.cartao_service import calcular_fatura_para_compra, obter_grupo_da_parcela_anterior
from dateutil.relativedelta import relativedelta

app = create_app()

# Dicionário para converter o mês em texto para número
meses_map = {
    'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12
}

# Cole abaixo as linhas copiadas da planilha (separadas por TAB):
#   data <TAB> descrição <TAB> categoria <TAB> cartão <TAB> valor
# ATENÇÃO: depois de importar, APAGUE as linhas daqui. Se rodar de novo com as
# mesmas linhas, tudo é importado em duplicidade.
dados_brutos = """
"""

# Defina o ano em que essas compras aconteceram
ANO_COMPRA = 2026

if not dados_brutos.strip():
    print("⚠️ Nada para importar: cole as linhas da planilha em dados_brutos e rode de novo.")
    raise SystemExit(0)

with app.app_context():
    # Pega o primeiro usuário do banco (você)
    usuario = Usuario.query.first()

    # Busca a categoria padrão caso a linha não tenha categoria definida
    cat_outros = Categoria.query.filter_by(nome="Outros", familia_id=usuario.familia_id).first()

    ultima_data = None

    # Compras parceladas deste lote: (descrição sem o 01/02, nº de parcelas) -> grupo
    grupos_do_lote = {}

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

        # Grupo da compra: só as parceladas têm grupo (à vista fica sem).
        # Todas as parcelas da mesma compra compartilham o mesmo grupo; se a parcela
        # anterior já está no banco, reaproveita o grupo dela.
        compra_grupo_id = None
        if numero_parcelas > 1:
            base_descricao = re.sub(r'\s*\d{2}/\d{2}$', '', descricao).strip()
            chave = (base_descricao.lower(), numero_parcelas)
            if chave not in grupos_do_lote:
                grupos_do_lote[chave] = (
                    obter_grupo_da_parcela_anterior(
                        usuario.familia_id, base_descricao, numero_parcelas, parcela_atual
                    )
                    or str(uuid.uuid4())
                )
            compra_grupo_id = grupos_do_lote[chave]

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
            compra_grupo_id=compra_grupo_id,
            fatura_id=fatura.id
        )
        db.session.add(nova_mov)

        # Atualiza o saldo da fatura
        fatura.saldo += valor
        print(f"✅ Lançado: {descricao} | Compra: {data_compra.strftime('%d/%m')} | Parcela em: {data_parcela.strftime('%d/%m')} | Fat: {fatura.mes}/{fatura.ano}")

    db.session.commit()
    print("\n🎉 Importação concluída com sucesso!")