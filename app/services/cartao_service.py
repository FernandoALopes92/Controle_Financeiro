"""Regras de negócio de movimentações de cartão e faturas."""
from __future__ import annotations
import uuid, re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Iterable, Optional, Set
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from app.utils.recorrencia import meses_da_recorrencia
from app.utils.valores import converter_valor_para_decimal  # noqa: F401 (reexportado: usado por rotas e testes)
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

class MovimentacaoAutomaticaProtegidaError(CartaoServiceError):
    """Lançamentos técnicos de rotativo não podem ser alterados individualmente."""


def eh_ajuste_rotativo(mov: MovimentacaoCartao) -> bool:
    """Identifica lançamentos técnicos criados ao transportar saldo entre faturas."""
    descricao = (mov.descricao or "").strip().casefold()
    return (
        descricao == "rotativo transferido p/ próxima fatura".casefold()
        or descricao.startswith("saldo pendente fatura ")
    )


def _validar_movimentacao_editavel(mov: MovimentacaoCartao) -> None:
    if eh_ajuste_rotativo(mov):
        raise MovimentacaoAutomaticaProtegidaError(
            "Este lançamento é automático e não pode ser editado ou excluído individualmente."
        )
class FaturaFechadaError(CartaoServiceError):
    def __init__(self, mes: int, ano: int):
        self.mes = mes
        self.ano = ano
        super().__init__(f"A fatura {mes}/{ano} já está fechada.")
class FaturaBloqueadaError(FaturaFechadaError):
    """Operação recusada porque envolve um lançamento em fatura fechada ou paga."""

    def __init__(self, mensagem: str, mes: int = 0, ano: int = 0):
        CartaoServiceError.__init__(self, mensagem)
        self.mes = mes
        self.ano = ano


class DataCompraBloqueadaError(CartaoServiceError):
    """A data da compra de um parcelado só pode ser alterada na 1ª parcela."""


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
def mes_ano_da_fatura(cartao: MeioPagamento, data_compra: date) -> tuple[int, int]:
    """
    (mês, ano) da fatura em que uma compra feita em data_compra deve cair,
    segundo os dias de fechamento e de vencimento do cartão.
    """
    if data_compra.day <= cartao.fechamento_dia:
        mes_fechamento, ano_fechamento = data_compra.month, data_compra.year
    else:
        mes_fechamento, ano_fechamento = _avancar_mes(data_compra.month, data_compra.year)
    if cartao.vencimento_dia < cartao.fechamento_dia:
        return _avancar_mes(mes_fechamento, ano_fechamento)
    return mes_fechamento, ano_fechamento


def faturas_das_parcelas(
    cartao: MeioPagamento, data_compra: date, numero_parcelas: int
) -> list[tuple[int, int]]:
    """
    Fatura de cada parcela: a da 1ª vem da data da compra e as demais caem nos
    meses seguidos. Nunca se calcula pela data de cada parcela, para não repetir
    nem pular fatura quando o dia da compra está perto do fechamento (29 a 31).
    """
    mes, ano = mes_ano_da_fatura(cartao, data_compra)
    return [_avancar_mes(mes, ano, i) for i in range(numero_parcelas)]


def calcular_fatura_para_compra(
    cartao_id: int,
    data_compra: date,
    familia_id: int,
) -> Fatura:
    """
    Fatura da compra (ou da 1ª parcela) pela data da compra.
    Usado por scripts (importar_excel, gerar_parcelas_futuras).
    """
    cartao = obter_cartao(cartao_id, familia_id)
    mes, ano = mes_ano_da_fatura(cartao, data_compra)
    return obter_ou_criar_fatura_aberta(cartao, mes, ano, familia_id)


def calcular_fatura_da_parcela(
    cartao_id: int,
    data_compra: date,
    parcela_atual: int,
    familia_id: int,
) -> Fatura:
    """
    Fatura da parcela N de uma compra: a da 1ª parcela mais N-1 meses.
    Usado por scripts (importar_excel).
    """
    cartao = obter_cartao(cartao_id, familia_id)
    mes, ano = faturas_das_parcelas(cartao, data_compra, max(parcela_atual, 1))[-1]
    return obter_ou_criar_fatura_aberta(cartao, mes, ano, familia_id)


_MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def prever_opcoes_fatura(
    cartao: MeioPagamento, data_compra: date, parcela_atual: int = 1
) -> list[dict]:
    """
    Retorna as duas opções de fatura exibidas no formulário (prevista + seguinte).
    Para a parcela N (edição), a previsão é a da 1ª parcela mais N-1 meses.
    """
    mes_fatura_1, ano_fatura_1 = mes_ano_da_fatura(cartao, data_compra)
    mes_fatura_1, ano_fatura_1 = _avancar_mes(mes_fatura_1, ano_fatura_1, max(parcela_atual, 1) - 1)
    mes_fatura_2, ano_fatura_2 = _avancar_mes(mes_fatura_1, ano_fatura_1)
    def _label(mes: int, ano: int, sufixo: str = "") -> str:
        # CORREÇÃO: usava datetime(...).strftime("%B"), que depende do idioma
        # do sistema operacional estar configurado em português (quebrava em
        # ambientes sem esse idioma instalado, como o Ubuntu do GitHub Actions).
        nome = _MESES_PT[mes]
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
    replicar: str                # "3_meses" | "6_meses" | "12_meses" | "nao"
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

    # só compras parceladas ou recorrentes precisam de grupo; à vista fica sem
    meses_recorrencia = meses_da_recorrencia(dados.replicar)
    precisa_grupo = dados.tipo_pagamento == "parcelado" or meses_recorrencia > 0
    grupo_id = str(uuid.uuid4()) if precisa_grupo else None

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
            mes_parcela, ano_parcela = _avancar_mes(mes_base, ano_base, parcela - 1)
            fatura = obter_ou_criar_fatura_aberta(
                cartao, mes_parcela, ano_parcela, familia_id
            )
            _criar_mov(
                descricao=dados.descricao,
                valor=valor_parcela,
                data_compra=dados.data_compra,  # data original em todas as parcelas
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
        if meses_recorrencia:
            for i in range(1, meses_recorrencia + 1):
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
def _dia(valor):
    """date ou datetime -> date."""
    return valor.date() if isinstance(valor, datetime) else valor


def _indice_mes(mes: int, ano: int) -> int:
    return ano * 12 + (mes - 1)


def _mes_ano_do_indice(indice: int) -> tuple[int, int]:
    return indice % 12 + 1, indice // 12


_STATUS_LEGIVEL = {"fechada": "fechada", "pago": "paga", "pago_parcial": "paga parcialmente"}


def _descrever(mov: MovimentacaoCartao) -> str:
    if (mov.numero_parcelas or 1) > 1:
        return f"a parcela {mov.parcela_atual}/{mov.numero_parcelas} de '{mov.descricao}'"
    return f"o lançamento '{mov.descricao}'"


def _validar_fatura_aberta(mov: MovimentacaoCartao, acao: str) -> None:
    """Lançamento em fatura que não está aberta é imutável (editar, excluir, mover)."""
    fatura = db.session.get(Fatura, mov.fatura_id) if mov.fatura_id else None
    if fatura and fatura.status != "aberta":
        situacao = _STATUS_LEGIVEL.get(fatura.status, fatura.status)
        raise FaturaBloqueadaError(
            f"Não é possível {acao} {_descrever(mov)}: a fatura {fatura.mes:02d}/{fatura.ano} está {situacao}.",
            fatura.mes,
            fatura.ano,
        )


def _validar_destino_disponivel(
    cartao: MeioPagamento, mes: int, ano: int, familia_id: int, mov: Optional[MovimentacaoCartao] = None
) -> None:
    """Confere, sem criar nada, se a fatura de destino aceita lançamentos."""
    fatura = Fatura.query.filter_by(cartao_id=cartao.id, mes=mes, ano=ano, familia_id=familia_id).first()
    if fatura and fatura.status != "aberta":
        if mov is None:
            raise FaturaFechadaError(mes, ano)
        situacao = _STATUS_LEGIVEL.get(fatura.status, fatura.status)
        raise FaturaBloqueadaError(
            f"Não é possível mover {_descrever(mov)} para a fatura {mes:02d}/{ano}: ela está {situacao}.",
            mes,
            ano,
        )


def _alvos_da_mudanca_de_data(
    mov: MovimentacaoCartao, nova_data: date, familia_id: int
) -> list[MovimentacaoCartao]:
    """
    Quais lançamentos recebem a nova data da compra.
    Parcelado: só a 1ª parcela altera a data, e vale para todas (se já guardam a mesma data).
    Recorrente ou avulso: cada lançamento tem a sua data.
    """
    data_atual = _dia(mov.data_compra)
    if nova_data == data_atual:
        return []
    if (mov.numero_parcelas or 1) > 1:
        if (mov.parcela_atual or 1) > 1:
            raise DataCompraBloqueadaError("A data da compra só pode ser alterada na 1ª parcela.")
        grupo = (
            MovimentacaoCartao.query.filter_by(compra_grupo_id=mov.compra_grupo_id, familia_id=familia_id).all()
            if mov.compra_grupo_id
            else [mov]
        )
        if all(_dia(g.data_compra) == data_atual for g in grupo):
            for g in grupo:
                _validar_fatura_aberta(g, "alterar a data de")
            return grupo
    return [mov]


def atualizar_movimentacao(
    mov: MovimentacaoCartao,
    dados: EditarMovimentacaoInput,
    *,
    familia_id: int,
) -> str:
    """
    Atualiza um lançamento. Com "esta e as próximas" marcado, nome, categoria e valor
    valem também para as seguintes, e se a fatura mudar elas andam o mesmo número de
    meses. As anteriores nunca mudam. Lançamento em fatura fechada ou paga é imutável.
    Tudo é validado antes de gravar: ou muda tudo, ou nada.
    """
    _validar_movimentacao_editavel(mov)
    if not dados.fatura_mes_ano:
        raise FaturaNaoSelecionadaError("Fatura não selecionada.")
    _validar_fatura_aberta(mov, "alterar")

    # ---------------------------- validação ----------------------------
    seguintes = parcelas_seguintes(mov, familia_id) if dados.alterar_proximas else []
    for seguinte in seguintes:
        _validar_fatura_aberta(seguinte, "alterar")

    mes_f, ano_f = _parse_mes_ano(dados.fatura_mes_ano)
    cartao = obter_cartao(dados.cartao_id, familia_id)
    _validar_destino_disponivel(cartao, mes_f, ano_f, familia_id)

    fatura_antiga = db.session.get(Fatura, mov.fatura_id) if mov.fatura_id else None
    deslocamento = (
        _indice_mes(mes_f, ano_f) - _indice_mes(fatura_antiga.mes, fatura_antiga.ano) if fatura_antiga else 0
    )
    destinos = []  # (seguinte, mês, ano, cartão)
    if deslocamento:
        for seguinte in seguintes:
            fatura_s = db.session.get(Fatura, seguinte.fatura_id) if seguinte.fatura_id else None
            if not fatura_s:
                continue
            mes_s, ano_s = _mes_ano_do_indice(_indice_mes(fatura_s.mes, fatura_s.ano) + deslocamento)
            cartao_s = obter_cartao(seguinte.cartao_id, familia_id)
            _validar_destino_disponivel(cartao_s, mes_s, ano_s, familia_id, mov=seguinte)
            destinos.append((seguinte, mes_s, ano_s, cartao_s))

    nova_data = _dia(dados.data_compra)
    alvos_da_data = _alvos_da_mudanca_de_data(mov, nova_data, familia_id)

    # ----------------------------- gravação ----------------------------
    faturas_modificadas: Set[int] = {mov.fatura_id}
    valor_novo = dados.valor * Decimal("-1") if dados.is_estorno else dados.valor
    for alvo in [mov, *seguintes]:
        alvo.descricao = dados.descricao
        alvo.categoria_id = dados.categoria_id
        alvo.valor = valor_novo
        faturas_modificadas.add(alvo.fatura_id)
    for alvo in alvos_da_data:
        alvo.data_compra = nova_data

    mov.cartao_id = dados.cartao_id
    fatura = obter_ou_criar_fatura_aberta(cartao, mes_f, ano_f, familia_id)
    mov.fatura_id = fatura.id
    faturas_modificadas.add(fatura.id)
    for seguinte, mes_s, ano_s, cartao_s in destinos:
        nova_fatura = obter_ou_criar_fatura_aberta(cartao_s, mes_s, ano_s, familia_id)
        seguinte.fatura_id = nova_fatura.id
        faturas_modificadas.add(nova_fatura.id)

    db.session.commit()
    recalcular_saldos_faturas(faturas_modificadas)
    return "Movimentação atualizada com sucesso."


def excluir_movimentacao(
    mov: MovimentacaoCartao,
    *,
    familia_id: int,
    excluir_todas: bool,
) -> Set[int]:
    """
    Exclui um lançamento. Com excluir_todas, exclui esta e as próximas (nunca as anteriores).
    Lançamento em fatura fechada ou paga não pode ser excluído; se algum alvo estiver
    bloqueado, nada é excluído.
    """
    _validar_movimentacao_editavel(mov)
    _validar_fatura_aberta(mov, "excluir")
    alvos = [mov]
    if excluir_todas:
        alvos += parcelas_seguintes(mov, familia_id)
        for alvo in alvos[1:]:
            _validar_fatura_aberta(alvo, "excluir")
    faturas_afetadas: Set[int] = {m.fatura_id for m in alvos if m.fatura_id}
    for alvo in alvos:
        db.session.delete(alvo)
    db.session.commit()
    recalcular_saldos_faturas(faturas_afetadas)
    return faturas_afetadas


def ids_com_proximas(movs: Iterable[MovimentacaoCartao], familia_id: int) -> Set[int]:
    """
    Ids dos lançamentos que têm parcelas/recorrências em faturas posteriores.
    Uma consulta só para a lista inteira; serve para a tela decidir se oferece
    "esta e as próximas".
    """
    movs = list(movs)
    grupos = {m.compra_grupo_id for m in movs if m.compra_grupo_id}
    if not grupos:
        return set()
    ordem = Fatura.ano * 12 + Fatura.mes
    maximos = dict(
        db.session.query(MovimentacaoCartao.compra_grupo_id, func.max(ordem))
        .join(Fatura, MovimentacaoCartao.fatura_id == Fatura.id)
        .filter(MovimentacaoCartao.compra_grupo_id.in_(grupos), MovimentacaoCartao.familia_id == familia_id)
        .group_by(MovimentacaoCartao.compra_grupo_id)
        .all()
    )
    resultado: Set[int] = set()
    for m in movs:
        if not m.compra_grupo_id or not m.fatura_id:
            continue
        fatura = db.session.get(Fatura, m.fatura_id)
        if fatura and fatura.ano * 12 + fatura.mes < maximos.get(m.compra_grupo_id, -1):
            resultado.add(m.id)
    return resultado


# ---------------------------------------------------------------------------
# Grupos (séries de lançamentos: parcelados e recorrentes)
# ---------------------------------------------------------------------------
def obter_grupo_da_parcela_anterior(
    familia_id: int,
    base_descricao: str,
    numero_parcelas: int,
    parcela_atual: int,
) -> Optional[str]:
    """
    Procura o compra_grupo_id da parcela anterior de uma compra parcelada.

    Serve para a importação do Excel: a parcela 03/10 deve entrar no mesmo grupo
    da 02/10 que já está no banco. Não filtra por cartão, porque uma série pode
    trocar de cartão no meio. Ignora grupos que já têm esta parcela, para não
    misturar duas compras com o mesmo nome. Devolve None se não encontrar.
    """
    candidatas = (
        MovimentacaoCartao.query.filter(
            MovimentacaoCartao.familia_id == familia_id,
            MovimentacaoCartao.numero_parcelas == numero_parcelas,
            MovimentacaoCartao.parcela_atual == parcela_atual - 1,
            MovimentacaoCartao.compra_grupo_id.isnot(None),
            func.lower(MovimentacaoCartao.descricao).like(f"{base_descricao.lower()}%"),
        )
        .order_by(MovimentacaoCartao.id.desc())
        .all()
    )
    for anterior in candidatas:
        ja_tem_esta_parcela = MovimentacaoCartao.query.filter_by(
            compra_grupo_id=anterior.compra_grupo_id, parcela_atual=parcela_atual
        ).first()
        if not ja_tem_esta_parcela:
            return anterior.compra_grupo_id
    return None


def parcelas_seguintes(mov: MovimentacaoCartao, familia_id: int) -> list[MovimentacaoCartao]:
    """
    Lançamentos do mesmo grupo (parcelas ou recorrências) em faturas POSTERIORES
    à deste. Usa a ordem das faturas, e não data_compra, porque as compras novas
    guardam a mesma data original em todas as parcelas.
    """
    if not mov.compra_grupo_id:
        return []
    if not mov.fatura_id:  # sem fatura: cai para a data, como antes
        return MovimentacaoCartao.query.filter(
            MovimentacaoCartao.compra_grupo_id == mov.compra_grupo_id,
            MovimentacaoCartao.familia_id == familia_id,
            MovimentacaoCartao.data_compra > mov.data_compra,
        ).all()
    fatura_atual = db.session.get(Fatura, mov.fatura_id)
    ordem_atual = fatura_atual.ano * 12 + fatura_atual.mes
    return (
        MovimentacaoCartao.query.join(Fatura, MovimentacaoCartao.fatura_id == Fatura.id)
        .filter(
            MovimentacaoCartao.compra_grupo_id == mov.compra_grupo_id,
            MovimentacaoCartao.familia_id == familia_id,
            (Fatura.ano * 12 + Fatura.mes) > ordem_atual,
        )
        .all()
    )