// ==========================================
// FUNÇÕES GLOBAIS DE NAVEGAÇÃO DO MODAL
// ==========================================
function irParaEtapa(idEtapaAlvo) {
  const blocos = [
    'etapa-tipo-transacao',
    'etapa-origem-despesa',
    'form-receita',
    'form-despesa-conta',
    'form-despesa-cartao',
    'form-transferencia',
  ];

  blocos.forEach((bloco) => {
    let elemento = document.getElementById(bloco);
    if (elemento) elemento.classList.add('d-none');
  });

  let elementoAlvo = document.getElementById(idEtapaAlvo);
  if (elementoAlvo) {
    elementoAlvo.classList.remove('d-none');

    // Disparadores automáticos de filtro de categoria por etapa
    if (idEtapaAlvo === 'form-receita')
      filtrarCategoriasModal('categoria_id_receita', 'receita');
    if (idEtapaAlvo === 'form-despesa-conta')
      filtrarCategoriasModal('categoria_id_despesa', 'despesa');
    if (idEtapaAlvo === 'form-despesa-cartao')
      filtrarCategoriasModal('categoria_id_cartao', 'despesa');

    if (idEtapaAlvo === 'form-despesa-cartao') {
      if (typeof aplicarMascaraValor === 'function') {
        aplicarMascaraValor('valor_compra_cartao');
      }
    }
  }
}

function voltarPara(idEtapaAnterior) {
  irParaEtapa(idEtapaAnterior);
}

// Filtro interno do Modal (Receita vs Despesa)
function filtrarCategoriasModal(idSelect, tipoDesejado) {
  const select = document.getElementById(idSelect);
  if (!select) return;
  const options = select.querySelectorAll('option:not([disabled])');
  options.forEach((opt) => {
    const tipoOpt = opt.getAttribute('data-tipo');
    if (tipoOpt === tipoDesejado) {
      opt.style.display = '';
    } else {
      opt.style.display = 'none';
      if (opt.selected) select.value = '';
    }
  });
}

// ==========================================
// INICIALIZAÇÃO DOS GRÁFICOS E EVENTOS
// ==========================================
document.addEventListener('DOMContentLoaded', function () {
  const dados = window.dadosDashboard || {};
  const formataDinheiro = (valor) =>
    'R$ ' +
    valor.toLocaleString('pt-BR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  // ========================================================
  // LÓGICA DO SUPER MODAL: CÁLCULOS E CONFLITOS DE RECORRÊNCIA
  // ========================================================
  const inputValor = document.getElementById('valor_compra_cartao');
  const inputParcelas = document.getElementById('numero_parcelas_cartao');
  const radiosTipo = document.querySelectorAll('input[name="tipo_valor"]');
  const boxResumo = document.getElementById('resumoCalculoParcela');
  const textoResumo = document.getElementById('textoCalculoParcela');

  // Elementos de controle do Parcelamento vs Recorrência
  const radioAvista = document.getElementById('avista_cartao');
  const radioParcelado = document.getElementById('parcelado_cartao');
  const secaoParcelas = document.getElementById('valorTipoSection');
  const secaoRecorrenteCard = document.getElementById('recorrenteSectionCard');

  function atualizarCalculo() {
    let valorRaw = inputValor.value.replace(',', '.');
    let valor = parseFloat(valorRaw) || 0;
    let parcelas = parseInt(inputParcelas.value) || 0;

    let tipoSelecionado = document.querySelector(
      'input[name="tipo_valor"]:checked',
    );
    let tipo = tipoSelecionado ? tipoSelecionado.value : 'total';

    if (valor > 0 && parcelas > 1) {
      boxResumo.style.display = 'block';

      if (tipo === 'total') {
        let valorParcela = valor / parcelas;
        textoResumo.innerHTML = `${parcelas}x de R$ ${formataDinheiro(valorParcela).replace('R$ ', '')}`;
      } else {
        let valorTotal = valor * parcelas;
        textoResumo.innerHTML = `Total Final: ${formataDinheiro(valorTotal)}`;
      }
    } else {
      boxResumo.style.display = 'none';
    }
  }

  // Ativa os gatilhos da calculadora em tempo real
  if (inputValor && inputParcelas) {
    inputValor.addEventListener('input', atualizarCalculo);
    inputParcelas.addEventListener('input', atualizarCalculo);
    radiosTipo.forEach((radio) =>
      radio.addEventListener('change', atualizarCalculo),
    );
  }

  // Ativa a regra de Esconder a Recorrência se for Parcelado
  if (radioAvista && radioParcelado && secaoParcelas && secaoRecorrenteCard) {
    radioAvista.addEventListener('change', function () {
      if (this.checked) {
        secaoParcelas.style.display = 'none';
        secaoRecorrenteCard.style.display = 'flex'; // Usando flex para não quebrar seu layout CSS
      }
    });

    radioParcelado.addEventListener('change', function () {
      if (this.checked) {
        secaoParcelas.style.display = 'block';
        secaoRecorrenteCard.style.display = 'none'; // Esconde para evitar conflito

        // Volta o select de recorrência para "Não"
        let selectRecorrente = secaoRecorrenteCard.querySelector(
          'select[name="replicar"]',
        );
        if (selectRecorrente) selectRecorrente.value = 'nao';
      }
    });
  }

  // --- GRÁFICOS (MANTIDOS DA VERSÃO ANTERIOR) ---
  const ctxOrigem = document.getElementById('origemChart');
  if (ctxOrigem && dados.despesasConta !== undefined) {
    new Chart(ctxOrigem.getContext('2d'), {
      type: 'bar',
      data: {
        labels: ['Gastos'],
        datasets: [
          {
            label: 'Conta/PIX',
            data: [dados.despesasConta],
            backgroundColor: '#b892f6',
            borderRadius: 8,
            barThickness: 60,
          },
          {
            label: 'Cartão',
            data: [dados.despesasCartao],
            backgroundColor: '#6c3df4',
            borderRadius: 8,
            barThickness: 60,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        scales: {
          x: { stacked: true, display: false },
          y: { stacked: true, display: false },
        },
        plugins: {
          legend: {
            position: 'bottom',
            labels: { usePointStyle: true, boxWidth: 8, padding: 20 },
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                let valor = context.raw || 0;
                return context.dataset.label + ': ' + formataDinheiro(valor);
              },
            },
          },
        },
      },
    });
  }
  const ctxCategoria = document.getElementById('categoriaChart');
  if (ctxCategoria && dados.nomesCategorias) {
    new Chart(ctxCategoria.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: dados.nomesCategorias,
        datasets: [
          {
            data: dados.valoresCategorias,
            backgroundColor: dados.coresCategorias,
            borderWidth: 2,
            borderColor: '#ffffff',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '65%',
        plugins: {
          legend: { display: false },
        },
      },
    });
  }

  // --- ESCUTA DE SALDOS EM TEMPO REAL ---
  function escutarSaldoElemento(idSelect, idContainer, idLabel) {
    const select = document.getElementById(idSelect);
    const container = document.getElementById(idContainer);
    const label = document.getElementById(idLabel);
    if (!select || !container || !label) return;

    select.addEventListener('change', function () {
      const opt = this.options[this.selectedIndex];
      if (opt && this.value !== '') {
        const saldo = parseFloat(opt.getAttribute('data-saldo')) || 0;
        label.innerHTML = 'Saldo: ' + formataDinheiro(saldo);
        container.style.display = 'block';
      } else {
        container.style.display = 'none';
      }
    });
  }

  escutarSaldoElemento(
    'conta_id_despesa',
    'saldoContaDespesaContainer',
    'saldoContaDespesa',
  );
  escutarSaldoElemento(
    'conta_origem_transf',
    'saldoContaOrigemTransfContainer',
    'saldoContaOrigemTransf',
  );
  escutarSaldoElemento(
    'conta_destino_transf',
    'saldoContaDestinoTransfContainer',
    'saldoContaDestinoTransf',
  );

  // --- PREVISÃO DE FATURA ---
  const dataCartao = document.getElementById('data_cartao');
  const cartaoSelect = document.getElementById('meio_pagamento_id_cartao');
  const selectFatura = document.getElementById('fatura_mes_ano_cartao');

  function preverFaturaSuperModal() {
    if (!dataCartao.value || !cartaoSelect.value) return;
    selectFatura.innerHTML =
      '<option value="" disabled selected>Calculando...</option>';

    fetch('/faturas/prever_fatura', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({
        data_compra: dataCartao.value,
        meio_pagamento_id: cartaoSelect.value,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        selectFatura.innerHTML = '';
        if (data.erro) {
          selectFatura.innerHTML = `<option value="" disabled selected>${data.erro}</option>`;
          return;
        }
        data.opcoes.forEach((opcao, index) => {
          const opt = document.createElement('option');
          opt.value = opcao.valor;
          opt.innerHTML = opcao.texto;
          if (index === 0) opt.selected = true;
          selectFatura.appendChild(opt);
        });
      });
  }

  if (dataCartao && cartaoSelect) {
    dataCartao.addEventListener('change', preverFaturaSuperModal);
    cartaoSelect.addEventListener('change', preverFaturaSuperModal);
  }

  // RESET DO MODAL
  const modalElemento = document.getElementById('modalNovaMov');
  if (modalElemento) {
    modalElemento.addEventListener('hidden.bs.modal', function () {
      irParaEtapa('etapa-tipo-transacao');
      document.getElementById('saldoContaDespesaContainer').style.display =
        'none';
      document.getElementById('saldoContaOrigemTransfContainer').style.display =
        'none';
      document.getElementById(
        'saldoContaDestinoTransfContainer',
      ).style.display = 'none';

      // Limpa os dados preenchidos para não aparecerem na próxima vez
      document
        .querySelectorAll('#modalNovaMov form')
        .forEach((form) => form.reset());
    });
  }
});

// ==========================================
// VALIDAÇÃO EM TEMPO REAL: BLOQUEIA E MOSTRA ALERT
// ==========================================
const formTransf = document.getElementById('form-transferencia');

if (formTransf) {
  formTransf.addEventListener('submit', function (e) {
    const selectOrigem = document.getElementById('conta_origem_transf');
    const selectDestino = document.getElementById('conta_destino_transf');
    const inputValor = document.getElementById('valor_transf');

    if (!selectOrigem || !selectDestino || !inputValor) return;

    const origemId = selectOrigem.value;
    const destinoId = selectDestino.value;
    const valor = parseFloat(inputValor.value) || 0;

    if (origemId === destinoId) {
      alert('⚠️ A conta de origem e destino devem ser diferentes.');
      e.preventDefault();
      return;
    }

    if (valor <= 0) {
      alert('⚠️ O valor da transferência deve ser maior que zero.');
      e.preventDefault();
      return;
    }

    const optSelecionada = selectOrigem.options[selectOrigem.selectedIndex];
    const saldoDisponivel =
      parseFloat(optSelecionada.getAttribute('data-saldo')) || 0;

    if (valor > saldoDisponivel) {
      alert('⚠️ Saldo insuficiente na conta de origem.');
      e.preventDefault();
      return;
    }
  });
}
