"""Testes do app/services/transferencia_service.py.

Como rodar só este arquivo:
    pytest tests/test_transferencia_service.py -v
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models import Transferencia
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