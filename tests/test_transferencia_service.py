"""Testes do app/services/transferencia_service.py.

Como rodar só este arquivo:
    pytest tests/test_transferencia_service.py -v
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models import Movimentacao, Transferencia
from app.services import transferencia_service as transf_service


def test_criar_transferencia_debita_origem_e_credita_destino(db, conta, conta_destino, usuario):
    dados = transf_service.NovaTransferenciaInput(
        origem_id=conta.id, destino_id=conta_destino.id,
        valor=Decimal("40.00"), data=date(2026, 1, 5), descricao="Teste",
    )

    transf_service.criar_transferencia(dados, usuario_id=usuario.id, familia_id=conta.familia_id)

    assert float(conta.saldo_atual) == 60.00       # 100 - 40
    assert float(conta_destino.saldo_atual) == 240.00  # 200 + 40
    assert Transferencia.query.count() == 1


def test_criar_transferencia_contas_iguais_e_bloqueada(db, conta, usuario):
    dados = transf_service.NovaTransferenciaInput(
        origem_id=conta.id, destino_id=conta.id,
        valor=Decimal("10.00"), data=date(2026, 1, 5), descricao="Teste",
    )

    with pytest.raises(transf_service.ContasIguaisError):
        transf_service.criar_transferencia(dados, usuario_id=usuario.id, familia_id=conta.familia_id)


def test_criar_transferencia_com_saldo_insuficiente_e_bloqueada(db, conta, conta_destino, usuario):
    dados = transf_service.NovaTransferenciaInput(
        origem_id=conta.id, destino_id=conta_destino.id,
        valor=Decimal("500.00"), data=date(2026, 1, 5), descricao="Teste",  # a conta só tem 100
    )

    with pytest.raises(transf_service.SaldoInsuficienteError):
        transf_service.criar_transferencia(dados, usuario_id=usuario.id, familia_id=conta.familia_id)

    # Garante que nada foi debitado, já que a transferência foi recusada
    assert float(conta.saldo_atual) == 100.00


def test_criar_transferencia_com_conta_inativa_e_bloqueada(db, conta, conta_destino, usuario):
    conta_destino.status = False
    db.session.commit()

    dados = transf_service.NovaTransferenciaInput(
        origem_id=conta.id, destino_id=conta_destino.id,
        valor=Decimal("10.00"), data=date(2026, 1, 5), descricao="Teste",
    )

    with pytest.raises(transf_service.ContaInativaError):
        transf_service.criar_transferencia(dados, usuario_id=usuario.id, familia_id=conta.familia_id)


def test_excluir_transferencia_estorna_saldos(db, conta, conta_destino, usuario):
    dados = transf_service.NovaTransferenciaInput(
        origem_id=conta.id, destino_id=conta_destino.id,
        valor=Decimal("40.00"), data=date(2026, 1, 5), descricao="Teste",
    )
    transf_service.criar_transferencia(dados, usuario_id=usuario.id, familia_id=conta.familia_id)
    assert float(conta.saldo_atual) == 60.00

    transferencia = Transferencia.query.first()
    transf_service.excluir_transferencia(transferencia)

    assert float(conta.saldo_atual) == 100.00        # voltou pro valor original
    assert float(conta_destino.saldo_atual) == 200.00  # voltou pro valor original
    assert Transferencia.query.count() == 0


def test_editar_transferencia_estorna_valor_antigo_e_aplica_o_novo(db, conta, conta_destino, usuario):
    dados = transf_service.NovaTransferenciaInput(
        origem_id=conta.id, destino_id=conta_destino.id,
        valor=Decimal("40.00"), data=date(2026, 1, 5), descricao="Teste",
    )
    transf_service.criar_transferencia(dados, usuario_id=usuario.id, familia_id=conta.familia_id)
    assert float(conta.saldo_atual) == 60.00
    assert float(conta_destino.saldo_atual) == 240.00

    transferencia = Transferencia.query.first()
    dados_edicao = transf_service.EditarTransferenciaInput(
        origem_id=conta.id, destino_id=conta_destino.id,
        valor=Decimal("70.00"), data=date(2026, 1, 6), descricao="Teste corrigido",
    )
    transf_service.atualizar_transferencia(
        transferencia, dados_edicao, usuario_id=usuario.id, familia_id=conta.familia_id
    )

    # Esperado: estorna os 40 antigos (100 e 200) e aplica os 70 novos
    assert float(conta.saldo_atual) == 30.00        # 100 - 70
    assert float(conta_destino.saldo_atual) == 270.00  # 200 + 70

@pytest.mark.parametrize(
    "valor",
    [
        Decimal("0.00"),
        Decimal("-10.00"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_criar_transferencia_com_valor_invalido_e_bloqueada(
    db, conta, conta_destino, usuario, valor
):
    dados = transf_service.NovaTransferenciaInput(
        origem_id=conta.id,
        destino_id=conta_destino.id,
        valor=valor,
        data=date(2026, 1, 5),
        descricao="Teste inválido",
    )

    with pytest.raises(transf_service.ValorTransferenciaInvalidoError):
        transf_service.criar_transferencia(
            dados,
            usuario_id=usuario.id,
            familia_id=conta.familia_id,
        )

    assert float(conta.saldo_atual) == 100.00
    assert float(conta_destino.saldo_atual) == 200.00
    assert Transferencia.query.count() == 0


def test_editar_transferencia_com_valor_zero_e_bloqueada(
    db, conta, conta_destino, usuario
):
    dados = transf_service.NovaTransferenciaInput(
        origem_id=conta.id,
        destino_id=conta_destino.id,
        valor=Decimal("40.00"),
        data=date(2026, 1, 5),
        descricao="Transferência original",
    )
    transf_service.criar_transferencia(
        dados,
        usuario_id=usuario.id,
        familia_id=conta.familia_id,
    )

    transferencia = Transferencia.query.first()

    dados_edicao = transf_service.EditarTransferenciaInput(
        origem_id=conta.id,
        destino_id=conta_destino.id,
        valor=Decimal("0.00"),
        data=date(2026, 1, 6),
        descricao="Tentativa inválida",
    )

    with pytest.raises(transf_service.ValorTransferenciaInvalidoError):
        transf_service.atualizar_transferencia(
            transferencia,
            dados_edicao,
            usuario_id=usuario.id,
            familia_id=conta.familia_id,
        )

    assert transferencia.valor == Decimal("40.00")
    assert float(conta.saldo_atual) == 60.00
    assert float(conta_destino.saldo_atual) == 240.00



def test_criar_transferencia_vincula_as_duas_movimentacoes(
    db, conta, conta_destino, usuario
):
    dados = transf_service.NovaTransferenciaInput(
        origem_id=conta.id,
        destino_id=conta_destino.id,
        valor=Decimal("40.00"),
        data=date(2026, 1, 5),
        descricao="Teste",
    )

    transf_service.criar_transferencia(
        dados,
        usuario_id=usuario.id,
        familia_id=conta.familia_id,
    )

    transferencia = Transferencia.query.one()
    movimentacoes = Movimentacao.query.filter_by(
        transferencia_id=transferencia.id
    ).all()

    assert len(movimentacoes) == 2
    assert {mov.conta_id for mov in movimentacoes} == {
        conta.id,
        conta_destino.id,
    }
    assert all(mov.valor == Decimal("40.00") for mov in movimentacoes)
    assert all(mov.tipo == "transferencia" for mov in movimentacoes)


def test_editar_transferencia_mantem_vinculo_das_movimentacoes(
    db, conta, conta_destino, usuario
):
    dados = transf_service.NovaTransferenciaInput(
        origem_id=conta.id,
        destino_id=conta_destino.id,
        valor=Decimal("40.00"),
        data=date(2026, 1, 5),
        descricao="Teste",
    )

    transf_service.criar_transferencia(
        dados,
        usuario_id=usuario.id,
        familia_id=conta.familia_id,
    )

    transferencia = Transferencia.query.one()
    transferencia_id = transferencia.id

    dados_edicao = transf_service.EditarTransferenciaInput(
        origem_id=conta.id,
        destino_id=conta_destino.id,
        valor=Decimal("70.00"),
        data=date(2026, 1, 6),
        descricao="Teste editado",
    )

    transf_service.atualizar_transferencia(
        transferencia,
        dados_edicao,
        usuario_id=usuario.id,
        familia_id=conta.familia_id,
    )

    movimentacoes = Movimentacao.query.filter_by(
        transferencia_id=transferencia_id
    ).all()

    assert len(movimentacoes) == 2
    assert all(mov.valor == Decimal("70.00") for mov in movimentacoes)
    assert all(mov.data == date(2026, 1, 6) for mov in movimentacoes)
    assert all(mov.transferencia_id == transferencia_id for mov in movimentacoes)


def test_excluir_transferencia_nao_apaga_movimentacoes_de_outra(
    db, conta, conta_destino, usuario
):
    dados = transf_service.NovaTransferenciaInput(
        origem_id=conta.id,
        destino_id=conta_destino.id,
        valor=Decimal("40.00"),
        data=date(2026, 1, 5),
        descricao="Transferência repetida",
    )

    transf_service.criar_transferencia(
        dados,
        usuario_id=usuario.id,
        familia_id=conta.familia_id,
    )

    transf_service.criar_transferencia(
        dados,
        usuario_id=usuario.id,
        familia_id=conta.familia_id,
    )

    transferencias = Transferencia.query.order_by(Transferencia.id).all()

    assert len(transferencias) == 2

    primeira_id = transferencias[0].id
    segunda_id = transferencias[1].id

    assert Movimentacao.query.filter_by(
        transferencia_id=primeira_id
    ).count() == 2

    assert Movimentacao.query.filter_by(
        transferencia_id=segunda_id
    ).count() == 2

    transf_service.excluir_transferencia(transferencias[0])

    assert db.session.get(Transferencia, primeira_id) is None
    assert db.session.get(Transferencia, segunda_id) is not None

    movimentacoes_restantes = Movimentacao.query.filter_by(
        transferencia_id=segunda_id
    ).all()

    assert len(movimentacoes_restantes) == 2
    assert all(
        mov.transferencia_id == segunda_id
        for mov in movimentacoes_restantes
    )

    assert Movimentacao.query.filter_by(
        transferencia_id=primeira_id
    ).count() == 0
