"""Regras de negócio de movimentações de cartão e faturas."""
from __future__ import annotations
import uuid
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Iterable, Optional, Set
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from app.models import (
    Categoria,
    Fatura,
    MeioPagamento,
    MovimentacaoCartao,
    db,
)
# ---------------------------------------------------------------------------
# Exceções de domínio (controller traduz em flash/json)
# ---------------------------------------------------------------------------
class CartaoServiceError(Exception):
    """Erro genérico de regra de negócio."""
class FaturaFechadaError(CartaoServiceError):
    def __init__(self, mes: int, ano: int):
        self.mes = mes
        self.ano = ano
        super().__init__(f"A fatura {mes}/{ano} já está fechada.")
class CartaoNaoEncontradoError(CartaoServiceError):
    pass
class FaturaNaoSelecionadaError(CartaoServiceError):
    pass
class ValorInvalidoError(CartaoServiceError):
    def __init__(self, valor_input: str):
        self.valor_input = valor_input
        super().__init__(f"O valor '{valor_input}' não é válido. Use 100.00 ou 100,00.")
# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def converter_valor_para_decimal(valor_str: str) -> Optional[Decimal]:
    try:
        if not valor_str:
            return None
        valor_limpo = valor_str.replace(".", "").replace(",", ".").strip()
        return Decimal(valor_limpo)
    except (InvalidOperation, ValueError):
        return None
def _avancar_mes(mes: int, ano: int, incremento: int = 1) -> tuple[int, int]:
    mes += incremento
    while mes > 12:
        mes -= 12
        ano += 1
    return mes, ano
def _parse_mes_ano(fatura_mes_ano: str) -> tuple[int, int]:
    mes, ano = map(int, fatura_mes_ano.split("-"))
    return mes, ano
# ---------------------------------------------------------------------------
# Faturas
# ---------------------------------------------------------------------------
def obter_cartao(cartao_id: int, familia_id: int) -> MeioPagamento:
    cartao = MeioPagamento.query.filter_by(
        id=cartao_id, familia_id=familia_id
    ).first()
    if not cartao:
        raise CartaoNaoEncontradoError("Cartão não encontrado.")
    return cartao
def obter_ou_criar_fatura_aberta(
    cartao: MeioPagamento,
    mes: int,
    ano: int,
    familia_id: int,
) -> Fatura:
    """Busca fatura existente ou cria uma aberta. Levanta FaturaFechadaError se fechada."""
    fatura = Fatura.query.filter_by(
        cartao_id=cartao.id,
        mes=mes,
        ano=ano,
        familia_id=familia_id,
    ).first()
    if not fatura:
        dia_fech = min(cartao.fechamento_dia, monthrange(ano, mes)[1])
        dia_venc = min(cartao.vencimento_dia, monthrange(ano, mes)[1])
        fatura = Fatura(
            cartao_id=cartao.id,
            mes=mes,
            ano=ano,
            data_fechamento=date(ano, mes, dia_fech),
            data_vencimento=date(ano, mes, dia_venc),
            status="aberta",
            saldo=Decimal("0.00"),
            familia_id=familia_id,
        )
        db.session.add(fatura)
        db.session.flush()
    if fatura.status != "aberta":
        raise FaturaFechadaError(mes, ano)
    return fatura
def recalcular_saldo_fatura(fatura_id: int, *, commit: bool = True) -> None:
    fatura = db.session.get(Fatura, fatura_id)
    if not fatura:
        return
    saldo = (
        db.session.query(func.coalesce(func.sum(MovimentacaoCartao.valor), 0))
        .filter_by(fatura_id=fatura_id)
        .scalar()
    )
    fatura.saldo = saldo
    if commit:
        db.session.commit()
def recalcular_saldos_faturas(fatura_ids: Iterable[int]) -> None:
    ids = {fid for fid in fatura_ids if fid}
    for fatura_id in ids:
        recalcular_saldo_fatura(fatura_id, commit=False)
    db.session.commit()
def obter_valores_por_categoria(fatura_id: int):
    resultados = (
        db.session.query(
            Categoria.nome,
            func.sum(MovimentacaoCartao.valor).label("total"),
        )
        .join(MovimentacaoCartao, MovimentacaoCartao.categoria_id == Categoria.id)
        .filter(MovimentacaoCartao.fatura_id == fatura_id)
        .group_by(Categoria.nome)
        .all()
    )
    total_geral = sum(r.total for r in resultados)
    categorias = [
        {
            "nome": r.nome,
            "valor": r.total,
            "percentual": round((r.total / total_geral) * 100, 1) if total_geral else 0,
        }
        for r in resultados
    ]
    return categorias, total_geral
def calcular_fatura_para_compra(
    cartao_id: int,
    data_compra: date,
    familia_id: int,
) -> Fatura:
    """
    Calcula mês/ano da fatura com base na data da compra e dias de fechamento/vencimento.
    Usado por scripts (importar_excel, gerar_parcelas_futuras).
    """
    cartao = obter_cartao(cartao_id, familia_id)
    if data_compra.day <= cartao.fechamento_dia:
        mes_fechamento, ano_fechamento = data_compra.month, data_compra.year
    elif data_compra.month == 12:
        mes_fechamento, ano_fechamento = 1, data_compra.year + 1
    else:
        mes_fechamento, ano_fechamento = data_compra.month + 1, data_compra.year
    if cartao.vencimento_dia < cartao.fechamento_dia:
        mes_fatura, ano_fatura = _avancar_mes(mes_fechamento, ano_fechamento)
    else:
        mes_fatura, ano_fatura = mes_fechamento, ano_fechamento
    return obter_ou_criar_fatura_aberta(cartao, mes_fatura, ano_fatura, familia_id)
def prever_opcoes_fatura(cartao: MeioPagamento, data_compra: date) -> list[dict]:
    """Retorna as duas opções de fatura exibidas no formulário (prevista + seguinte)."""
    if data_compra.day <= cartao.fechamento_dia:
        mes_fechamento, ano_fechamento = data_compra.month, data_compra.year
    elif data_compra.month == 12:
        mes_fechamento, ano_fechamento = 1, data_compra.year + 1
    else:
        mes_fechamento, ano_fechamento = data_compra.month + 1, data_compra.year
    if cartao.vencimento_dia < cartao.fechamento_dia:
        mes_fatura_1, ano_fatura_1 = _avancar_mes(mes_fechamento, ano_fechamento)
    else:
        mes_fatura_1, ano_fatura_1 = mes_fechamento, ano_fechamento
    mes_fatura_2, ano_fatura_2 = _avancar_mes(mes_fatura_1, ano_fatura_1)
    def _label(mes: int, ano: int, sufixo: str = "") -> str:
        nome = datetime(ano, mes, 1).strftime("%B").capitalize()
        return f"{nome}/{ano}{sufixo}"
    return [
        {"valor": f"{mes_fatura_1}-{ano_fatura_1}", "texto": _label(mes_fatura_1, ano_fatura_1, " (Prevista)")},
        {"valor": f"{mes_fatura_2}-{ano_fatura_2}", "texto": _label(mes_fatura_2, ano_fatura_2)},
    ]
# ---------------------------------------------------------------------------
# Movimentações — criação
# ---------------------------------------------------------------------------
@dataclass
class NovaMovimentacaoInput:
    descricao: str
    valor: Decimal
    data_compra: datetime
    cartao_id: int
    categoria_id: int
    fatura_mes_ano: str
    tipo_pagamento: str          # "parcelado" | outro (à vista)
    tipo_valor: Optional[str]    # "total" | None
    numero_parcelas: int
    replicar: str                # "3_meses" | "nao"
    is_estorno: bool = False
def _criar_mov(
    *,
    descricao: str,
    valor: Decimal,
    data_compra: datetime,
    cartao_id: int,
    categoria_id: int,
    usuario_id: int,
    familia_id: int,
    fatura_id: int,
    numero_parcelas: int = 1,
    parcela_atual: int = 1,
    compra_grupo_id: str,
) -> MovimentacaoCartao:
    mov = MovimentacaoCartao(
        descricao=descricao,
        valor=valor,
        data_compra=data_compra,
        cartao_id=cartao_id,
        categoria_id=categoria_id,
        usuario_id=usuario_id,
        familia_id=familia_id,
        numero_parcelas=numero_parcelas,
        parcela_atual=parcela_atual,
        compra_grupo_id=compra_grupo_id,
        fatura_id=fatura_id,
    )
    db.session.add(mov)
    return mov
def criar_movimentacao(
    dados: NovaMovimentacaoInput,
    *,
    usuario_id: int,
    familia_id: int,
) -> tuple[str, Set[int]]:
    """
    Cria compra à vista, parcelada ou recorrente (3 meses).
    Retorna (mensagem_sucesso, ids_faturas_modificadas).
    """
    if not dados.fatura_mes_ano:
        raise FaturaNaoSelecionadaError(
            "Aguarde o cálculo da fatura ou selecione uma opção válida."
        )
    valor = dados.valor * Decimal("-1") if dados.is_estorno else dados.valor
    mes_base, ano_base = _parse_mes_ano(dados.fatura_mes_ano)
    cartao = obter_cartao(dados.cartao_id, familia_id)
    grupo_id = str(uuid.uuid4())
    faturas_modificadas: Set[int] = set()
    if dados.tipo_pagamento == "parcelado":
        numero_parcelas = dados.numero_parcelas
        if dados.tipo_valor == "total":
            num_dec = Decimal(numero_parcelas)
            valor_base = (valor / num_dec).quantize(Decimal("0.00"), rounding=ROUND_DOWN)
            residuo = valor - (valor_base * num_dec)
        else:
            valor_base, residuo = valor, Decimal("0.00")
        for parcela in range(1, numero_parcelas + 1):
            valor_parcela = valor_base + residuo if parcela == 1 else valor_base
            data_parcela = dados.data_compra + relativedelta(months=parcela - 1)
            mes_parcela, ano_parcela = _avancar_mes(mes_base, ano_base, parcela - 1)
            fatura = obter_ou_criar_fatura_aberta(
                cartao, mes_parcela, ano_parcela, familia_id
            )
            _criar_mov(
                descricao=dados.descricao,
                valor=valor_parcela,
                data_compra=data_parcela,
                cartao_id=dados.cartao_id,
                categoria_id=dados.categoria_id,
                usuario_id=usuario_id,
                familia_id=familia_id,
                fatura_id=fatura.id,
                numero_parcelas=numero_parcelas,
                parcela_atual=parcela,
                compra_grupo_id=grupo_id,
            )
            faturas_modificadas.add(fatura.id)
        mensagem = f"Compra parcelada registrada com {numero_parcelas} parcelas."
    else:
        fatura = obter_ou_criar_fatura_aberta(cartao, mes_base, ano_base, familia_id)
        _criar_mov(
            descricao=dados.descricao,
            valor=valor,
            data_compra=dados.data_compra,
            cartao_id=dados.cartao_id,
            categoria_id=dados.categoria_id,
            usuario_id=usuario_id,
            familia_id=familia_id,
            fatura_id=fatura.id,
            compra_grupo_id=grupo_id,
        )
        faturas_modificadas.add(fatura.id)
        if dados.replicar == "3_meses":
            for i in range(1, 4):
                mes_futuro, ano_futuro = _avancar_mes(mes_base, ano_base, i)
                fatura_futura = obter_ou_criar_fatura_aberta(
                    cartao, mes_futuro, ano_futuro, familia_id
                )
                _criar_mov(
                    descricao=dados.descricao,
                    valor=valor,
                    data_compra=dados.data_compra + relativedelta(months=i),
                    cartao_id=dados.cartao_id,
                    categoria_id=dados.categoria_id,
                    usuario_id=usuario_id,
                    familia_id=familia_id,
                    fatura_id=fatura_futura.id,
                    compra_grupo_id=grupo_id,
                )
                faturas_modificadas.add(fatura_futura.id)
        mensagem = "Compra à vista registrada com sucesso."
    db.session.commit()
    recalcular_saldos_faturas(faturas_modificadas)
    return mensagem, faturas_modificadas
# ---------------------------------------------------------------------------
# Movimentações — edição e exclusão
# ---------------------------------------------------------------------------
@dataclass
class EditarMovimentacaoInput:
    descricao: str
    valor: Decimal
    data_compra: datetime
    cartao_id: int
    categoria_id: int
    fatura_mes_ano: str
    is_estorno: bool = False
    alterar_proximas: bool = False
def atualizar_movimentacao(
    mov: MovimentacaoCartao,
    dados: EditarMovimentacaoInput,
    *,
    familia_id: int,
) -> str:
    faturas_modificadas: Set[int] = set()
    fatura_antiga_id = mov.fatura_id
    # 1. Descrição e categoria (grupo ou individual)
    if mov.compra_grupo_id:
        MovimentacaoCartao.query.filter_by(
            compra_grupo_id=mov.compra_grupo_id,
            familia_id=familia_id,
        ).update({"descricao": dados.descricao, "categoria_id": dados.categoria_id})
        db.session.expire(mov)
    else:
        mov.descricao = dados.descricao
        mov.categoria_id = dados.categoria_id
    # 2. Valor (sempre atômico na parcela atual)
    valor_novo = dados.valor * Decimal("-1") if dados.is_estorno else dados.valor
    mov.valor = valor_novo
    if dados.alterar_proximas and mov.compra_grupo_id:
        futuras = MovimentacaoCartao.query.filter(
            MovimentacaoCartao.compra_grupo_id == mov.compra_grupo_id,
            MovimentacaoCartao.data_compra > mov.data_compra,
            MovimentacaoCartao.familia_id == familia_id,
        ).all()
        for futura in futuras:
            futura.valor = valor_novo
            if futura.fatura_id:
                faturas_modificadas.add(futura.fatura_id)
    # 3. Data, cartão e fatura
    if not dados.fatura_mes_ano:
        raise FaturaNaoSelecionadaError("Fatura não selecionada.")
    mov.data_compra = dados.data_compra
    mov.cartao_id = dados.cartao_id
    mes_f, ano_f = _parse_mes_ano(dados.fatura_mes_ano)
    cartao = obter_cartao(dados.cartao_id, familia_id)
    fatura = obter_ou_criar_fatura_aberta(cartao, mes_f, ano_f, familia_id)
    mov.fatura_id = fatura.id
    db.session.commit()
    faturas_modificadas.update({fatura_antiga_id, fatura.id})
    recalcular_saldos_faturas(faturas_modificadas)
    return "Movimentação atualizada com sucesso."
def excluir_movimentacao(
    mov: MovimentacaoCartao,
    *,
    familia_id: int,
    excluir_todas: bool,
) -> Set[int]:
    faturas_afetadas: Set[int] = set()
    if excluir_todas:
        if mov.compra_grupo_id:
            vizinhos = MovimentacaoCartao.query.filter_by(
                compra_grupo_id=mov.compra_grupo_id,
                familia_id=familia_id,
            ).all()
        else:
            base_nome = mov.descricao
            if " (" in base_nome and ")" in base_nome:
                base_nome = base_nome.rsplit(" (", 1)[0]
            vizinhos = MovimentacaoCartao.query.filter(
                MovimentacaoCartao.cartao_id == mov.cartao_id,
                MovimentacaoCartao.familia_id == familia_id,
                MovimentacaoCartao.descricao.like(f"{base_nome} (%/%)"),
            ).all()
    else:
        vizinhos = [mov]
    for m in vizinhos:
        if m.fatura_id:
            faturas_afetadas.add(m.fatura_id)
        db.session.delete(m)
    db.session.commit()
    recalcular_saldos_faturas(faturas_afetadas)
    return faturas_afetadas