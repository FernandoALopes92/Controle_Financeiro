document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('modalSuperMov');

  if (!modal) return;

  const etapas = {
    tipo: document.getElementById('supermodal-etapa-tipo'),
    origem: document.getElementById('supermodal-etapa-origem'),
    receita: document.getElementById('supermodal-form-receita'),
    despesaConta: document.getElementById('supermodal-form-despesa-conta'),
    despesaCartao: document.getElementById('supermodal-form-despesa-cartao'),
    transferencia: document.getElementById('supermodal-form-transferencia'),
  };

  const botaoSalvar = modal.querySelector('.modal-footer button[type="submit"]');

  const footer = modal.querySelector('.modal-footer');

  inicializarExibicaoSaldoConta(
    'supermodal_receita_conta',
    'supermodal_receita_saldo_container',
    'supermodal_receita_saldo',
  );

  inicializarExibicaoSaldoConta(
    'supermodal_despesa_conta_conta',
    'supermodal_despesa_conta_saldo_container',
    'supermodal_despesa_conta_saldo',
  );

  configurarSupermodalCartao();
  configurarSupermodalTransferencia();

  inicializarExibicaoSaldoConta(
    'supermodal_transferencia_origem',
    'supermodal_transferencia_saldo_origem_container',
    'supermodal_transferencia_saldo_origem',
  );

  inicializarExibicaoSaldoConta(
    'supermodal_transferencia_destino',
    'supermodal_transferencia_saldo_destino_container',
    'supermodal_transferencia_saldo_destino',
  );

  let etapaAtual = 'tipo';

  const formIds = {
    receita: 'supermodal-receita-form',
    despesaConta: 'supermodal-despesa-conta-form',
    despesaCartao: 'supermodal-despesa-cartao-form',
    transferencia: 'supermodal-transferencia-form',
  };

  function limparFormulario(form) {
    if (!form) return;

    form.reset();

    // esconde os badges de saldo (reset() não dispara o evento "change")
    form.querySelectorAll('[id$="_container"]').forEach((el) => {
      el.style.display = 'none';
    });
  }

  function configurarFooter(nomeEtapa) {
    if (!footer || !botaoSalvar) return;

    const formularios = {
      receita: 'supermodal-receita-form',
      despesaConta: 'supermodal-despesa-conta-form',
      despesaCartao: 'supermodal-despesa-cartao-form',
      transferencia: 'supermodal-transferencia-form',
    };

    const formId = formularios[nomeEtapa];

    if (formId) {
      footer.classList.remove('d-none');

      botaoSalvar.setAttribute('form', formId);
      botaoSalvar.disabled = false;
    } else {
      footer.classList.add('d-none');

      botaoSalvar.removeAttribute('form');
      botaoSalvar.disabled = true;
    }
  }

  function mostrarEtapa(nomeEtapa) {
    Object.values(etapas).forEach((etapa) => {
      if (etapa) {
        etapa.classList.add('d-none');
      }
    });

    const etapa = etapas[nomeEtapa];

    if (!etapa) return;

    etapa.classList.remove('d-none');

    etapaAtual = nomeEtapa;

    configurarFooter(nomeEtapa);

    if (
      nomeEtapa === 'receita' ||
      nomeEtapa === 'despesaConta' ||
      nomeEtapa === 'despesaCartao' ||
      nomeEtapa === 'transferencia'
    ) {
      const dataIds = {
        receita: 'supermodal_receita_data',
        despesaConta: 'supermodal_despesa_conta_data',
        despesaCartao: 'supermodal_cartao_data',
        transferencia: 'supermodal_transferencia_data',
      };

      const data = document.getElementById(dataIds[nomeEtapa]);

      if (data && typeof setHoje === 'function') {
        setHoje(data);
      }
    }
  }

  function voltar() {
    if (etapaAtual === 'origem') {
      mostrarEtapa('tipo');
      return;
    }

    if (etapaAtual === 'receita' || etapaAtual === 'transferencia') {
      mostrarEtapa('tipo');
      return;
    }

    if (etapaAtual === 'despesaConta' || etapaAtual === 'despesaCartao') {
      mostrarEtapa('origem');
    }
  }

  modal.addEventListener('click', (event) => {
    const elemento = event.target.closest('[data-supermodal-action]');

    if (!elemento) return;

    const acao = elemento.dataset.supermodalAction;

    if (acao === 'voltar' || acao === 'voltar-tipo') {
      const formId = formIds[etapaAtual];
      if (formId) limparFormulario(document.getElementById(formId));
    }

    switch (acao) {
      case 'receita':
        mostrarEtapa('receita');
        break;

      case 'despesa':
        mostrarEtapa('origem');
        break;

      case 'transferencia':
        mostrarEtapa('transferencia');
        break;

      case 'despesa-conta':
        mostrarEtapa('despesaConta');
        break;

      case 'despesa-cartao':
        mostrarEtapa('despesaCartao');
        break;

      case 'voltar-tipo':
        mostrarEtapa('tipo');
        break;

      case 'voltar':
        voltar();
        break;
    }
  });

  modal.addEventListener('hidden.bs.modal', () => {
    Object.values(formIds).forEach((id) => {
      limparFormulario(document.getElementById(id));
    });

    mostrarEtapa('tipo');
  });

  mostrarEtapa('tipo');
});

function inicializarExibicaoSaldoConta(idSelect, idContainer, idLabel) {
  const select = document.getElementById(idSelect);
  const container = document.getElementById(idContainer);
  const label = document.getElementById(idLabel);

  if (!select || !container || !label) return;

  select.addEventListener('change', function () {
    const option = this.options[this.selectedIndex];

    if (option && this.value !== '') {
      const saldo = parseFloat(option.getAttribute('data-saldo')) || 0;

      label.textContent =
        'Saldo: R$ ' +
        saldo.toLocaleString('pt-BR', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });

      container.style.display = 'block';
    } else {
      container.style.display = 'none';
    }
  });
}
function configurarSupermodalCartao() {
  const valorInput = document.getElementById('supermodal_cartao_valor');
  const numeroParcelasInput = document.getElementById('supermodal_cartao_numero_parcelas');

  const valorTotalRadio = document.getElementById('supermodal_cartao_valor_total');

  const valorParcelaRadio = document.getElementById('supermodal_cartao_valor_parcela');

  const parcelamento = document.getElementById('supermodal_cartao_parcelamento');

  const valorParcelaCalculado = document.getElementById('supermodal_cartao_valor_parcela_calculado');

  const textoValorParcela = document.getElementById('supermodal_cartao_texto_valor_parcela');

  const avista = document.getElementById('supermodal_cartao_avista');
  const parcelado = document.getElementById('supermodal_cartao_parcelado');

  const recorrencia = document.getElementById('supermodal_cartao_replicar').closest('.mb-2');

  const cartaoSelect = document.getElementById('supermodal_cartao_meio_pagamento');

  const dataInput = document.getElementById('supermodal_cartao_data');

  if (
    !valorInput ||
    !numeroParcelasInput ||
    !valorTotalRadio ||
    !valorParcelaRadio ||
    !parcelamento ||
    !valorParcelaCalculado ||
    !textoValorParcela ||
    !avista ||
    !parcelado ||
    !cartaoSelect ||
    !dataInput
  ) {
    return;
  }

  function calcularValorParcela() {
    const valor = parseFloat((valorInput.value || '').replace(',', '.')) || 0;

    const parcelas = parseInt(numeroParcelasInput.value, 10) || 0;

    if (valorTotalRadio.checked && valor > 0 && parcelas > 0) {
      const valorParcela = valor / parcelas;

      textoValorParcela.innerText = `Valor de cada parcela: R$ ${valorParcela.toFixed(2)}`;

      valorParcelaCalculado.style.display = 'block';
    } else {
      valorParcelaCalculado.style.display = 'none';
    }
  }

  const formCartao = document.getElementById('supermodal-despesa-cartao-form');

  if (formCartao) {
    formCartao.addEventListener('reset', () => {
      // setTimeout: roda depois que o navegador termina de resetar os campos
      setTimeout(() => {
        atualizarParcelamento();
        valorParcelaCalculado.style.display = 'none';
        textoValorParcela.textContent = '';

        const selectFatura = document.getElementById('supermodal_cartao_fatura');
        if (selectFatura) {
          selectFatura.innerHTML = '<option value="" disabled selected>Selecione data e cartão...</option>';
        }
      }, 0);
    });
  }

  function atualizarParcelamento() {
    const isParcelado = parcelado.checked;

    parcelamento.style.display = isParcelado ? 'block' : 'none';

    recorrencia.style.display = isParcelado ? 'none' : 'block';

    calcularValorParcela();
  }

  avista.addEventListener('change', atualizarParcelamento);
  parcelado.addEventListener('change', atualizarParcelamento);

  valorInput.addEventListener('input', calcularValorParcela);
  numeroParcelasInput.addEventListener('input', calcularValorParcela);

  valorTotalRadio.addEventListener('change', calcularValorParcela);

  valorParcelaRadio.addEventListener('change', () => {
    valorParcelaCalculado.style.display = 'none';
  });

  async function preverFatura() {
    const dataCompra = dataInput.value;
    const cartaoId = cartaoSelect.value;

    const selectFatura = document.getElementById('supermodal_cartao_fatura');

    if (!selectFatura) return;

    if (!dataCompra || !cartaoId) {
      selectFatura.innerHTML = '<option value="" disabled selected>' + 'Selecione data e cartão...' + '</option>';

      return;
    }

    selectFatura.innerHTML = '<option value="" disabled selected>' + 'Calculando...' + '</option>';

    try {
      const response = await fetch('/faturas/prever_fatura', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
          data_compra: dataCompra,
          meio_pagamento_id: cartaoId,
        }),
      });

      const data = await response.json();

      selectFatura.innerHTML = '';

      if (data.erro) {
        selectFatura.innerHTML = `<option value="" disabled selected>${data.erro}</option>`;

        return;
      }

      if (!Array.isArray(data.opcoes) || !data.opcoes.length) {
        selectFatura.innerHTML = '<option value="" disabled selected>' + 'Nenhuma fatura disponível' + '</option>';

        return;
      }

      data.opcoes.forEach((opcao, index) => {
        const option = document.createElement('option');

        option.value = opcao.valor;
        option.textContent = opcao.texto;

        if (index === 0) {
          option.selected = true;
        }

        selectFatura.appendChild(option);
      });
    } catch (erro) {
      console.error('Erro ao prever fatura:', erro);

      selectFatura.innerHTML = '<option value="" disabled selected>' + 'Erro ao calcular faturas' + '</option>';
    }
  }

  cartaoSelect.addEventListener('change', preverFatura);
  dataInput.addEventListener('change', preverFatura);

  atualizarParcelamento();
}

function configurarSupermodalTransferencia() {
  const form = document.getElementById('supermodal-transferencia-form');

  if (!form) return;

  const origem = document.getElementById('supermodal_transferencia_origem');

  const destino = document.getElementById('supermodal_transferencia_destino');

  const valor = document.getElementById('supermodal_transferencia_valor');

  if (!origem || !destino || !valor) return;

  form.addEventListener('submit', function (event) {
    const origemId = origem.value;
    const destinoId = destino.value;
    const valorTransferencia = parseFloat(valor.value) || 0;

    if (origemId === destinoId) {
      event.preventDefault();

      alert('A conta de origem e destino devem ser diferentes.');

      return;
    }

    if (valorTransferencia <= 0) {
      event.preventDefault();

      alert('O valor da transferência deve ser maior que zero.');

      return;
    }

    const opcaoOrigem = origem.options[origem.selectedIndex];

    const saldoDisponivel = parseFloat(opcaoOrigem.getAttribute('data-saldo')) || 0;

    if (valorTransferencia > saldoDisponivel) {
      event.preventDefault();

      alert(
        'Saldo insuficiente na conta de origem. ' +
          'Saldo disponível: R$ ' +
          saldoDisponivel.toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          }),
      );
    }
  });
}
