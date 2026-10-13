from types import SimpleNamespace
import pytest

from app.services import cartao_service


@pytest.mark.parametrize(
    "descricao",
    [
        "Rotativo transferido p/ próxima fatura",
        "Saldo pendente fatura 10/26",
        "  saldo PENDENTE fatura 11/26  ",
    ],
)
def test_identifica_lancamentos_tecnicos_do_rotativo(descricao):
    mov = SimpleNamespace(descricao=descricao)
    assert cartao_service.eh_ajuste_rotativo(mov)


def test_compra_normal_nao_e_identificada_como_rotativo():
    mov = SimpleNamespace(descricao="Mercado")
    assert not cartao_service.eh_ajuste_rotativo(mov)


def test_lancamento_rotativo_nao_pode_ser_editado():
    mov = SimpleNamespace(descricao="Rotativo transferido p/ próxima fatura")
    dados = SimpleNamespace()

    with pytest.raises(cartao_service.MovimentacaoAutomaticaProtegidaError):
        cartao_service.atualizar_movimentacao(mov, dados, familia_id=1)


def test_lancamento_rotativo_nao_pode_ser_excluido():
    mov = SimpleNamespace(descricao="Saldo pendente fatura 10/26")

    with pytest.raises(cartao_service.MovimentacaoAutomaticaProtegidaError):
        cartao_service.excluir_movimentacao(
            mov, familia_id=1, excluir_todas=False
        )
