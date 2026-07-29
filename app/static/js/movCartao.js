// === Utilitários ===

function validarSelect(select, mensagem) {
  if (!select) return;
  select.setCustomValidity(select.value ? '' : mensagem);
}

function exibirToast(mensagem, tipo = 'primary') {
  const toastEl = document.getElementById('liveToast');
  const toastBody = document.getElementById('toastMessage');

  toastBody.textContent = mensagem;
  toastEl.className = `toast align-items-center text-bg-${tipo} border-0`;

  const toast = new bootstrap.Toast(toastEl);
  toast.show();
}

// === Parcelamento ===
function toggleParceladoFields(parceladoRadio, valorTipoSection, calcular) {
  valorTipoSection.style.display = parceladoRadio.checked ? 'block' : 'none';

  // Oculta o campo de conta recorrente se for parcelado (Removendo a classe d-flex do Bootstrap)
  const recorrenteSection = document.getElementById('recorrenteSection');
  if (recorrenteSection) {
    if (parceladoRadio.checked) {
      recorrenteSection.classList.remove('d-flex');
      recorrenteSection.classList.add('d-none');
    } else {
      recorrenteSection.classList.remove('d-none');
      recorrenteSection.classList.add('d-flex');
    }
  }
  calcular();
}

function calcularValorParcela(
  valorInput,
  numeroParcelasInput,
  valorTotalRadio,
  textoValorParcela,
  valorParcelaCalculado,
) {
  const valor = parseFloat(valorInput.value.replace(',', '.')) || 0;
  const parcelas = parseInt(numeroParcelasInput.value) || 0;

  if (valorTotalRadio.checked && valor > 0 && parcelas > 0) {
    const valorParcela = valor / parcelas;
    textoValorParcela.innerText = `Valor de cada parcela: R$ ${valorParcela.toFixed(
      2,
    )}`;
    valorParcelaCalculado.style.display = 'block';
  } else {
    valorParcelaCalculado.style.display = 'none';
  }
}

// === Previsão de Fatura ===
// === Previsão de Fatura (Com Escolha do Usuário) ===
function preverFatura() {
  const dataInput = document.getElementById('data');
  const cartaoSelect = document.getElementById('meio_pagamento_id');
  const selectFatura = document.getElementById('fatura_mes_ano'); // Agora é um <select>

  const dataCompra = dataInput.value;
  const cartaoId = cartaoSelect.value;

  // Se o usuário ainda não preencheu os dois campos, limpa o select e avisa
  if (!dataCompra || !cartaoId) {
    selectFatura.innerHTML =
      '<option value="" disabled selected>Selecione data e cartão...</option>';
    return;
  }

  // Mostra que está carregando...
  selectFatura.innerHTML =
    '<option value="" disabled selected>Calculando...</option>';

  fetch('/faturas/prever_fatura', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify({
      data_compra: dataCompra,
      meio_pagamento_id: cartaoId,
    }),
  })
    .then((res) => res.json())
    .then((data) => {
      // Limpa as opções antigas
      selectFatura.innerHTML = '';

      if (data.erro) {
        selectFatura.innerHTML = `<option value="" disabled selected>${data.erro}</option>`;
        return;
      }

      // Preenche o Select com as duas opções que o Python calculou
      data.opcoes.forEach((opcao, index) => {
        const opt = document.createElement('option');
        opt.value = opcao.valor; // Ex: "6-2026"
        opt.innerHTML = opcao.texto; // Ex: "Junho/2026 (Prevista)"

        // Deixa a primeira opção (A Prevista) selecionada por padrão
        if (index === 0) {
          opt.selected = true;
        }

        selectFatura.appendChild(opt);
      });
    })
    .catch(() => {
      selectFatura.innerHTML =
        '<option value="" disabled selected>Erro ao calcular faturas</option>';
    });
}

// === Inicializações Comuns ===
function configurarEventosComuns() {
  const valorInput = document.getElementById('valor');
  const numeroParcelasInput = document.getElementById('numero_parcelas');
  const valorTotalRadio = document.getElementById('valor_total');
  const valorParcelaRadio = document.getElementById('valor_parcela');
  const valorTipoSection = document.getElementById('valorTipoSection');
  const valorParcelaCalculado = document.getElementById(
    'valorParcelaCalculado',
  );
  const textoValorParcela = document.getElementById('textoValorParcela');

  const calcular = () =>
    calcularValorParcela(
      valorInput,
      numeroParcelasInput,
      valorTotalRadio,
      textoValorParcela,
      valorParcelaCalculado,
    );

  document
    .getElementById('avista')
    .addEventListener('change', () =>
      toggleParceladoFields(
        document.getElementById('parcelado'),
        valorTipoSection,
        calcular,
      ),
    );
  document
    .getElementById('parcelado')
    .addEventListener('change', () =>
      toggleParceladoFields(
        document.getElementById('parcelado'),
        valorTipoSection,
        calcular,
      ),
    );

  valorInput.addEventListener('input', calcular);
  numeroParcelasInput.addEventListener('input', calcular);
  valorTotalRadio.addEventListener('change', calcular);
  valorParcelaRadio.addEventListener('change', () => {
    valorParcelaCalculado.style.display = 'none';
  });

  document.getElementById('categoria_id').addEventListener('change', (e) => {
    validarSelect(e.target, 'Por favor, selecione uma categoria.');
  });
  document
    .getElementById('meio_pagamento_id')
    .addEventListener('change', (e) => {
      validarSelect(e.target, 'Por favor, selecione um cartão.');
      preverFatura();
    });

  document.getElementById('data').addEventListener('change', preverFatura);
}

// === DOM Ready ===
document.addEventListener('DOMContentLoaded', function () {
  configurarEventosComuns();

  if (typeof aplicarMascaraValor === 'function') {
    aplicarMascaraValor('valor');
  } else {
    console.warn('Atenção: mascara.js não foi carregado corretamente.');
  }

  let instanciaModal = null;

  const barras = document.querySelectorAll('.progress-bar');
  barras.forEach((bar) => {
    const finalWidth = bar.getAttribute('data-final-width');
    setTimeout(() => {
      bar.style.width = finalWidth + '%';
    }, 50); // pequeno atraso para ativar animação
  });

  document.getElementById('novaCompraButton').addEventListener('click', () => {
    const form = document.getElementById('formAddDespesaCartao');
    // Reset padrão
    form.reset();

    // Desliga a chave de estorno por padrão
    const chkEstorno = document.getElementById('is_estorno');
    if (chkEstorno) chkEstorno.checked = false;

    // Remove atributos e define modo 'add'
    form.setAttribute('data-mode', 'add');
    form.removeAttribute('data-id');
    form.removeAttribute('action');

    // Corrige texto do botão
    document.getElementById('btnSalvarMovimentacao').innerText = 'Salvar';

    // Seleciona primeiro item dos selects
    form.categoria_id.selectedIndex = 0;
    form.meio_pagamento_id.selectedIndex = 0;

    // Marca "à vista" como padrão
    document.getElementById('avista').checked = true;
    // document.getElementById("parcelado").checked = false;

    // Habilita os dois tipos de pagamento e remove opacidade
    document.getElementById('avista').disabled = false;
    document.getElementById('parcelado').disabled = false;
    document.getElementById('lblAvista').classList.remove('opacity-25');
    document.getElementById('lblParcelado').classList.remove('opacity-25');

    // Esconde seção de valor tipo
    document.getElementById('valorTipoSection').style.display = 'none';

    // Garante que a caixa de recorrência apareça na Nova Compra
    const recorrenteSection = document.getElementById('recorrenteSection');
    if (recorrenteSection) {
      recorrenteSection.classList.remove('d-none');
      recorrenteSection.classList.add('d-flex');
      const selectReplicar = document.getElementById('replicar');
      if (selectReplicar) selectReplicar.value = 'nao';
    }

    // Limpa número de parcelas
    const parcelasInput = form.querySelector('[name="numero_parcelas"]');
    if (parcelasInput) parcelasInput.value = '';

    // Limpa radios do tipo de valor
    const tipoValorRadios = document.querySelectorAll(
      "input[name='tipo_valor']",
    );
    tipoValorRadios.forEach((radio) => (radio.checked = false));

    // Reseta fatura prevista
    const badgeFatura = document.getElementById('faturaPrevista');
    if (badgeFatura) badgeFatura.innerText = 'Selecione data e cartão'; // Adicionado if de segurança

    // Define a data como hoje
    if (typeof setHoje === 'function') {
      setHoje(document.getElementById('data'));
    }

    // Atualiza fatura prevista
    preverFatura();

    const modalElement = document.getElementById('modalMovimentacaoCartao');
    instanciaModal = bootstrap.Modal.getOrCreateInstance(modalElement);
    instanciaModal.show();
  });

  document.querySelectorAll('.btn-editar').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      try {
        const res = await fetch(`/cartao/mov_cartao/editar/${id}`, {
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!res.ok) throw new Error('Erro ao buscar movimentação');
        const data = await res.json();

        const form = document.getElementById('formAddDespesaCartao');
        form.setAttribute('data-mode', 'edit');
        form.setAttribute('data-id', id);
        form.removeAttribute('action');

        form.descricao.value = data.descricao;

        // Tratamento do valor de estorno
        const valorNumerico = parseFloat(data.valor);
        if (valorNumerico < 0) {
          document.getElementById('is_estorno').checked = true;
          form.valor.value = Math.abs(valorNumerico)
            .toFixed(2)
            .replace('.', ',');
        } else {
          document.getElementById('is_estorno').checked = false;
          form.valor.value = data.valor;
        }

        form.data.value = data.data_compra;

        // --- MOSTRA A CAIXINHA DE RECORRÊNCIA SE FOR GRUPO/PARCELADO ---
        const blocoProximas = document.getElementById('blocoAlterarProximas');
        if (blocoProximas) {
          // Verifica se a compra tem parcelas > 1 ou se faz parte de um grupo recorrente
          if (data.numero_parcelas > 1 || data.compra_grupo_id) {
            blocoProximas.classList.remove('d-none'); // Mostra a caixa
            document.getElementById('alterar_proximas').checked = false; // Garante que começa desmarcada
          } else {
            blocoProximas.classList.add('d-none'); // Esconde se for compra única e avulsa
          }
        }

        // Define o cartão *antes* da fatura
        form.meio_pagamento_id.value = data.meio_pagamento_id;

        // FORÇA a categoria a aparecer (Ignorando qualquer filtro do modal anterior)
        const catSelect = document.getElementById('categoria_id');
        const opcaoCategoria = catSelect.querySelector(
          `option[value="${data.categoria_id}"]`,
        );
        if (opcaoCategoria) {
          opcaoCategoria.style.display = ''; // Garante que não esteja invisível
          catSelect.value = data.categoria_id;
        }

        const avista = document.getElementById('avista');
        const parcelado = document.getElementById('parcelado');

        ['avista', 'parcelado'].forEach((tipo) => {
          document.getElementById(tipo).disabled = false;
          document
            .getElementById(
              'lbl' + tipo.charAt(0).toUpperCase() + tipo.slice(1),
            )
            .classList.remove('opacity-25');
        });

        // Tratamento do Número de Parcelas
        if (data.numero_parcelas === 1) {
          avista.checked = true;
          parcelado.disabled = true;
          document.getElementById('lblParcelado').classList.add('opacity-25');
          form.querySelector('[name="numero_parcelas"]').value = '';
        } else {
          parcelado.checked = true;
          avista.disabled = true;
          document.getElementById('lblAvista').classList.add('opacity-25');
          form.querySelector('[name="numero_parcelas"]').value =
            data.numero_parcelas || '';
        }

        document.getElementById('valorTipoSection').style.display = 'none';

        const recorrenteSection = document.getElementById('recorrenteSection');
        if (recorrenteSection) {
          recorrenteSection.classList.remove('d-flex');
          recorrenteSection.classList.add('d-none');
        }

        document.getElementById('btnSalvarMovimentacao').innerText =
          'Atualizar';

        // ATENÇÃO - A SOLUÇÃO DA FATURA:
        // Desliga a previsão automática temporariamente e busca a fatura ORIGINAL
        const selectFatura = document.getElementById('fatura_mes_ano');

        // Busca o nome bonito do mês e ano através da rota que criamos
        fetch(
          `/faturas/fatura_nome/${data.fatura_id_mes}/${data.fatura_id_ano}`,
        )
          .then((res) => res.json())
          .then((info) => {
            // Limpa o select e injeta a fatura real daquela compra
            selectFatura.innerHTML = `<option value="${data.fatura_id_mes}-${data.fatura_id_ano}" selected>${info.texto}</option>`;
          })
          .catch(() => {
            // Se der erro, cai na previsão padrão
            preverFatura();
          });

        const modalEl = document.getElementById('modalMovimentacaoCartao');
        if (modalEl) {
          const modal = new bootstrap.Modal(modalEl);
          modal.show();
        }
      } catch (err) {
        console.error('Erro ao carregar movimentação:', err);
        exibirToast('Erro ao carregar dados para edição.', 'danger');
      }
    });
  });

  document
    .getElementById('formAddDespesaCartao')
    .addEventListener('submit', async function (e) {
      e.preventDefault();

      const form = this;
      const formData = new FormData(form);

      const modo = form.getAttribute('data-mode');
      const id = form.getAttribute('data-id');
      const url =
        modo === 'edit'
          ? `/cartao/mov_cartao/${id}/edit`
          : '/cartao/mov_cartao/nova';

      try {
        const res = await fetch(url, {
          method: 'POST',
          body: formData,
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });

        const contentType = res.headers.get('Content-Type');

        if (res.redirected) {
          window.location.href = res.url;
        } else if (contentType && contentType.includes('application/json')) {
          const resposta = await res.json();

          if (res.ok && resposta.sucesso) {
            exibirToast(
              resposta.mensagem || 'Movimentação salva com sucesso',
              'success',
            );

            // fecha modal imediatamente
            const modalElement = document.getElementById(
              'modalMovimentacaoCartao',
            );
            const modal = bootstrap.Modal.getInstance(modalElement);
            modal.hide();

            // mostra o toast
            exibirToast(
              resposta.mensagem || 'Movimentação salva com sucesso',
              'success',
            );

            // atualiza a página **imediatamente** (sem esperar)
            setTimeout(() => {
              location.reload();
            }, 1500);
          } else {
            exibirToast(
              resposta.erro || 'Erro ao salvar movimentação.',
              'danger',
            );
          }
        } else {
          const html = await res.text();
          console.error('⚠️ HTML retornado pelo servidor:', html);
          exibirToast('Erro interno no servidor.', 'danger');
        }
      } catch (err) {
        console.error('❌ Erro ao salvar via AJAX:', err);
        exibirToast('Erro ao salvar movimentação.', 'danger');
      }
    });
});

//excluir
document.addEventListener('DOMContentLoaded', () => {
  const formsExcluir = document.querySelectorAll('.form-excluir');

  formsExcluir.forEach((form) => {
    form.addEventListener('submit', function (event) {
      // Impede que a tela recarregue antes de você responder
      event.preventDefault();

      // Pega o número de parcelas (se não tiver, assume que é 1)
      const numeroParcelas = parseInt(this.getAttribute('data-parcelas')) || 1;
      const inputExcluirTodas = this.querySelector('.input-excluir-todas');

      // 1ª Pergunta de segurança
      if (confirm('Tem certeza que deseja excluir este lançamento?')) {
        // 2ª Pergunta: Se for parcelado, dá a opção de limpar tudo
        if (numeroParcelas > 1) {
          const apagarTodas = confirm(
            '⚠️ COMPRA PARCELADA DETECTADA!\n\n' +
              '• Clique em [OK] se quiser apagar TODAS as parcelas desta compra.\n' +
              '• Clique em [Cancelar] se quiser apagar APENAS esta parcela.',
          );

          if (apagarTodas) {
            inputExcluirTodas.value = 'true';
          } else {
            inputExcluirTodas.value = 'false';
          }
        }

        // Agora sim, envia para o Python excluir
        this.submit();
      }
    });
  });
});

////// Saldo no Modal Pagar

function atualizarSaldoConta(faturaId) {
  // 1. Localiza os elementos necessários dentro do modal específico
  const modal = document.getElementById('modalPagarFatura' + faturaId);
  const selectElement = modal.querySelector('select[name="conta_id"]');
  const valorInput = document.getElementById('valor_' + faturaId);
  const campoSaldo = document.getElementById('saldoConta_' + faturaId);
  const botaoConfirmar = modal.querySelector('.btn.btn-purple');

  // 2. Obtém os valores atuais
  const selectedOption = selectElement.options[selectElement.selectedIndex];
  const saldoConta = parseFloat(selectedOption.getAttribute('data-saldo')) || 0;
  const valorPagamento = parseFloat(valorInput.value) || 0;

  // 3. Validações
  if (campoSaldo) {
    // Formata o saldo da conta para exibir
    campoSaldo.textContent =
      'R$ ' +
      saldoConta.toLocaleString('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });

    // Compara se o pagamento cabe na conta
    if (valorPagamento > saldoConta) {
      campoSaldo.classList.remove('text-success');
      campoSaldo.classList.add('text-danger');
      if (botaoConfirmar) botaoConfirmar.disabled = true;
    } else if (valorPagamento <= 0) {
      // Impede pagamento de zero ou negativo
      if (botaoConfirmar) botaoConfirmar.disabled = true;
    } else {
      campoSaldo.classList.remove('text-danger');
      campoSaldo.classList.add('text-success');
      if (botaoConfirmar) botaoConfirmar.disabled = false;
    }
  }
}

function toggleFiltro(tipo) {
  const menuCat = document.getElementById('menuFiltroCategoria');
  const menuCartao = document.getElementById('menuFiltroCartao');

  if (tipo === 'categoria') {
    menuCat.classList.toggle('d-none');
    menuCartao.classList.add('d-none'); // Fecha o outro
  } else {
    menuCartao.classList.toggle('d-none');
    menuCat.classList.add('d-none'); // Fecha o outro
  }
}

function aplicarFiltroTabelaMovCartoes() {
  // Pega os valores selecionados nos menus suspensos do cabeçalho da tabela
  const valCatSelect = document
    .querySelector('#menuFiltroCategoria select')
    .value.toLowerCase();
  const valCartaoSelect = document
    .querySelector('#menuFiltroCartao select')
    .value.toLowerCase();

  const tabela = document.getElementById('tabelaMovimentacoesCartoes');
  if (!tabela) return;

  const linhas = tabela.querySelectorAll('tbody tr');

  linhas.forEach((row) => {
    // Busca o texto invisível injetado no HTML via data-attributes (o '3' é a coluna da categoria e '4' do cartão, base 0)
    const celulaCategoria = row.querySelectorAll('td')[3];
    const celulaCartao = row.querySelectorAll('td')[4];

    // Captura o nome injetado, ou joga vazio se der algum erro
    const nomeCategoria = celulaCategoria
      ? celulaCategoria.getAttribute('data-categoria').toLowerCase()
      : '';
    const nomeCartao = celulaCartao
      ? celulaCartao.getAttribute('data-cartao').toLowerCase()
      : '';

    // Lógica do filtro "E" (AND): Só mostra se passar nos dois testes
    const exibeCat = valCatSelect === '' || nomeCategoria === valCatSelect;
    const exibeCartao =
      valCartaoSelect === '' || nomeCartao === valCartaoSelect;

    if (exibeCat && exibeCartao) {
      row.style.display = ''; // Mostra a linha
    } else {
      row.style.display = 'none'; // Esconde a linha
    }
  });

  // Fecha os menus automaticamente após aplicar o filtro
  document.getElementById('menuFiltroCategoria').classList.add('d-none');
  document.getElementById('menuFiltroCartao').classList.add('d-none');
}

/* // Cria dinamicamente os menus de filtro
function criarMenuFiltro(id, opcoes) {
  const menu = document.getElementById(id);
  if (!menu) return;

  const select = document.createElement('select');
  select.classList.add('form-select', 'form-select-sm', 'mb-1');
  select.innerHTML =
    `<option value="">Todos</option>` +
    opcoes.map((op) => `<option value="${op}">${op}</option>`).join('');

  select.addEventListener('change', function () {
    aplicarFiltroTabelaMovCartoes();
    menu.classList.add('d-none'); // Fecha após selecionar
  });

  // Limpa e insere novo select
  menu.innerHTML = '';
  menu.appendChild(select);
}

// Fecha dropdowns se clicar fora
document.addEventListener('click', function (e) {
  const menus = [
    document.getElementById('menuFiltroCategoria'),
    document.getElementById('menuFiltroCartao'),
  ];
  const icones = document.querySelectorAll('.filtro-icon');
  if (![...menus, ...icones].some((el) => el && el.contains(e.target))) {
    menus.forEach((menu) => menu.classList.add('d-none'));
  }
});

// Executa ao carregar
document.addEventListener('DOMContentLoaded', function () {
  const categorias = Array.from(
    new Set(
      Array.from(
        document.querySelectorAll(
          '#tabelaMovimentacoesCartoes tbody td:nth-child(4)',
        ),
      ).map((td) => td.textContent.trim()),
    ),
  );
  const cartoes = Array.from(
    new Set(
      Array.from(
        document.querySelectorAll(
          '#tabelaMovimentacoesCartoes tbody td:nth-child(5)',
        ),
      ).map((td) => td.textContent.trim()),
    ),
  );

  criarMenuFiltro('menuFiltroCategoria', categorias);
  criarMenuFiltro('menuFiltroCartao', cartoes);
});
 */

// Fecha os menus de filtro se o usuário clicar em qualquer outro lugar da tela
document.addEventListener('click', function (e) {
  const menuCat = document.getElementById('menuFiltroCategoria');
  const menuCartao = document.getElementById('menuFiltroCartao');

  // Se o clique NÃO foi dentro de um menu aberto, e NÃO foi no ícone do funil
  if (
    !e.target.closest('.filtro-dropdown') &&
    !e.target.closest('.filtro-icon')
  ) {
    if (menuCat) menuCat.classList.add('d-none');
    if (menuCartao) menuCartao.classList.add('d-none');
  }
});
