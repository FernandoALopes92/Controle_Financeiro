"""Regressões para não contar transporte de saldo como compra no dashboard."""
from datetime import date
from decimal import Decimal

from app.models import Fatura, Movimentacao, MovimentacaoCartao
from app.routes.dashboard import (
    _calcular_totais_do_mes,
    _top_5_categorias,
    _top_5_despesas,
)


def _criar_fatura(db, cartao, familia, mes, ano):
    fatura = Fatura(
        cartao_id=cartao.id,
        mes=mes,
        ano=ano,
        saldo=Decimal("0.00"),
        status="aberta",
        familia_id=familia.id,
    )
    db.session.add(fatura)
    db.session.flush()
    return fatura


def _criar_mov_cartao(
    db, usuario, familia, cartao, fatura, descricao, valor, categoria_id, data_compra
):
    mov = MovimentacaoCartao(
        usuario_id=usuario.id,
        familia_id=familia.id,
        cartao_id=cartao.id,
        fatura_id=fatura.id,
        descricao=descricao,
        valor=Decimal(valor),
        categoria_id=categoria_id,
        data_compra=data_compra,
        numero_parcelas=1,
        parcela_atual=1,
    )
    db.session.add(mov)
    return mov


def _filtro_fantasma():
    from sqlalchemy import not_
    from app.models import Movimentacao

    return not_(Movimentacao.descricao.ilike("Fatura %")) & not_(
        Movimentacao.descricao.ilike("%Transferência%")
    )


def test_transporte_rotativo_nao_altera_totais_nem_categorias(
    app, db, familia, usuario, cartao, categoria_despesa
):
    with app.app_context():
        janeiro = _criar_fatura(db, cartao, familia, 1, 2026)
        fevereiro = _criar_fatura(db, cartao, familia, 2, 2026)

        # Compra real de R$ 1.000,00 na fatura original.
        _criar_mov_cartao(
            db, usuario, familia, cartao, janeiro,
            "Compra supermercado", "1000.00", categoria_despesa.id, date(2026, 1, 5)
        )
        # Ajustes técnicos gerados pelo pagamento parcial: não são compras.
        _criar_mov_cartao(
            db, usuario, familia, cartao, janeiro,
            "Rotativo transferido p/ próxima fatura", "-600.00", None, date(2026, 1, 20)
        )
        _criar_mov_cartao(
            db, usuario, familia, cartao, fevereiro,
            "Saldo pendente fatura 01/26", "600.00", None, date(2026, 1, 20)
        )
        db.session.commit()

        # O saldo das faturas continua incluindo os ajustes técnicos.
        assert sum(m.valor for m in janeiro.movimentacoes) == Decimal("400.00")
        assert sum(m.valor for m in fevereiro.movimentacoes) == Decimal("600.00")

        filtro = _filtro_fantasma()

        totais_jan = _calcular_totais_do_mes(familia.id, 1, 2026, filtro)
        totais_fev = _calcular_totais_do_mes(familia.id, 2, 2026, filtro)

        assert totais_jan["despesas_cartao_mes"] == 1000.0
        assert totais_jan["despesas_totais"] == 1000.0
        assert totais_fev["despesas_cartao_mes"] == 0.0
        assert totais_fev["despesas_totais"] == 0.0

        cats_jan, ordenadas_jan = _top_5_categorias(
            familia.id, 1, 2026, filtro, totais_jan["despesas_totais"]
        )
        cats_fev, ordenadas_fev = _top_5_categorias(
            familia.id, 2, 2026, filtro, totais_fev["despesas_totais"]
        )

        assert ordenadas_jan == [("Mercado", 1000.0)]
        assert cats_jan[0]["valor"] == 1000.0
        assert ordenadas_fev == []
        assert cats_fev == []

        maiores_jan = _top_5_despesas(familia.id, 1, 2026, filtro)
        maiores_fev = _top_5_despesas(familia.id, 2, 2026, filtro)

        assert [(item["descricao"], item["valor"]) for item in maiores_jan] == [
            ("Compra supermercado", 1000.0)
        ]
        assert maiores_fev == []
