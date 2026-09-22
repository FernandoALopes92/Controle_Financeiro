// === Utilitários ===

function validarSelect(select, mensagem) {
  if (!select) return;
  select.setCustomValidity(select.value ? '' : mensagem);
}

function exibirToast(mensagem, tipo = 'primary') {
  const toastEl = document.getElementById('liveToast');
  const toastBody = document.getElementById('toastMessage');

  if (!toastEl || !toastBody) return;

  toastBody.textContent = mensagem;
  toastEl.className = `toast align-items-center text-bg-${tipo} border-0`;

  const toast = new bootstrap.Toast(toastEl);
  toast.show();
}

// === Parcelamento ===

function toggleParceladoFields(parceladoRadio, valorTipoSection, calcular) {
  if (valorTipoSection && parceladoRadio) {
    valorTipoSection.style.display = parceladoRadio.checked ? 'block' : 'none';
  }

  // Oculta o campo de conta recorrente se for parcelado
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
  if (
    !valorInput ||
    !numeroParcelasInput ||
    !valorTotalRadio ||
    !textoValorParcela ||
    !valorParcelaCalculado
  ) {
    return;
  }

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

// === Previsão de Fatura ===

function preverFatura() {
  const dataInput = document.getElementById('data');
  const cartaoSelect = document.getElementById('meio_pagamento_id');
  const selectFatura = document.getElementById('fatura_mes_ano');

  if (!dataInput || !cartaoSelect || !selectFatura) {
    return;
  }

  const dataCompra = dataInput.value;
  const cartaoId = cartaoSelect.value;

  // Se o usuário ainda não preencheu os dois campos
  if (!dataCompra || !cartaoId) {
    selectFatura.innerHTML =
      '<option value="" disabled selected>' +
      'Selecione data e cartão...' +
      '</option>';

    return;
  }

  // Mostra que está carregando
  selectFatura.innerHTML =
    '<option value="" disabled selected>' + 'Calculando...' + '</option>';

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
      selectFatura.innerHTML = '';

      if (data.erro) {
        selectFatura.innerHTML = `<option value="" disabled selected>${data.erro}</option>`;
        return;
      }

      if (!data.opcoes || !Array.isArray(data.opcoes)) {
        selectFatura.innerHTML =
          '<option value="" disabled selected>' +
          'Nenhuma fatura disponível' +
          '</option>';

        return;
      }

      data.opcoes.forEach((opcao, index) => {
        const opt = document.createElement('option');

        opt.value = opcao.valor;
        opt.innerHTML = opcao.texto;

        if (index === 0) {
          opt.selected = true;
        }

        selectFatura.appendChild(opt);
      });
    })
    .catch((erro) => {
      console.error('Erro ao prever fatura:', erro);

      selectFatura.innerHTML =
        '<option value="" disabled selected>' +
        'Erro ao calcular faturas' +
        '</option>';
    });
}

// ==========================================================
// TABELA DE MOVIMENTAÇÕES DO CARTÃO
// ==========================================================

function configurarTabelaCartao() {
  const tabelaCartao = document.getElementById('tabelaMovimentacoesCartoes');

  const pageSizeSelect = document.getElementById('cartao-page-size');

  const campoPesquisa = document.getElementById('cartao-table-search');

  const contadorTabela = document.getElementById('cartao-table-count');

  const containerPaginacao = document.getElementById('cartao-pagination');

  // Se não existe tabela nesta página, simplesmente não faz nada
  if (!tabelaCartao) {
    return;
  }

  let paginaCartaoAtual = 1;

  let tamanhoPaginaCartao = parseInt(pageSizeSelect?.value || '15', 10);

  // ----------------------------------------------------------
  // Obtém todas as linhas da tabela
  // ----------------------------------------------------------

  function obterLinhasCartao() {
    return Array.from(tabelaCartao.querySelectorAll('tbody tr'));
  }

  // ----------------------------------------------------------
  // Obtém as linhas que passam pelos filtros
  // ----------------------------------------------------------

  function obterLinhasFiltradasCartao() {
    const linhas = obterLinhasCartao();

    const pesquisa = (campoPesquisa?.value || '').trim().toLowerCase();

    const filtroCategoria =
      document
        .querySelector('#menuFiltroCategoria select')
        ?.value?.trim()
        .toLowerCase() || '';

    const filtroCartao =
      document
        .querySelector('#menuFiltroCartao select')
        ?.value?.trim()
        .toLowerCase() || '';

    return linhas.filter((linha) => {
      const celulas = linha.querySelectorAll('td');

      if (!celulas.length) {
        return false;
      }

      // Texto completo da linha para pesquisa
      const textoLinha = linha.textContent.trim().toLowerCase();

      // Categoria
      const categoria =
        celulas[3]?.getAttribute('data-categoria')?.trim().toLowerCase() || '';

      // Cartão
      const cartao =
        celulas[4]?.getAttribute('data-cartao')?.trim().toLowerCase() || '';

      // Pesquisa geral
      const passaPesquisa = !pesquisa || textoLinha.includes(pesquisa);

      // Filtro categoria
      const passaCategoria = !filtroCategoria || categoria === filtroCategoria;

      // Filtro cartão
      const passaCartao = !filtroCartao || cartao === filtroCartao;

      return passaPesquisa && passaCategoria && passaCartao;
    });
  }

  // ----------------------------------------------------------
  // Atualiza tabela
  // ----------------------------------------------------------

  function atualizarTabelaCartao() {
    const linhasFiltradas = obterLinhasFiltradasCartao();

    const total = linhasFiltradas.length;

    // Quantidade de páginas
    const totalPaginas =
      tamanhoPaginaCartao >= 999999
        ? 1
        : Math.max(1, Math.ceil(total / tamanhoPaginaCartao));

    // Garante que a página atual continue válida
    if (paginaCartaoAtual > totalPaginas) {
      paginaCartaoAtual = totalPaginas;
    }

    if (paginaCartaoAtual < 1) {
      paginaCartaoAtual = 1;
    }

    // Esconde todas as linhas
    const todasAsLinhas = obterLinhasCartao();

    todasAsLinhas.forEach((linha) => {
      linha.style.display = 'none';
    });

    // --------------------------------------------------------
    // Define intervalo da página
    // --------------------------------------------------------

    let inicio = 0;
    let fim = total;

    if (tamanhoPaginaCartao < 999999) {
      inicio = (paginaCartaoAtual - 1) * tamanhoPaginaCartao;

      fim = inicio + tamanhoPaginaCartao;
    }

    const linhasPagina = linhasFiltradas.slice(inicio, fim);

    // Mostra somente as linhas da página atual
    linhasPagina.forEach((linha) => {
      linha.style.display = '';
    });

    // --------------------------------------------------------
    // Atualiza contador
    // --------------------------------------------------------

    if (contadorTabela) {
      if (!total) {
        contadorTabela.textContent = 'Nenhuma movimentação encontrada';
      } else {
        const primeiro = inicio + 1;

        const ultimo = Math.min(fim, total);

        contadorTabela.textContent = `Mostrando ${primeiro} a ${ultimo} de ${total} movimentações`;
      }
    }

    // --------------------------------------------------------
    // Atualiza paginação
    // --------------------------------------------------------

    atualizarPaginacaoCartao(totalPaginas);
  }

  // ----------------------------------------------------------
  // Atualiza controles de paginação
  // ----------------------------------------------------------

  function atualizarPaginacaoCartao(totalPaginas) {
    if (!containerPaginacao) {
      return;
    }

    containerPaginacao.innerHTML = '';

    // Página anterior
    if (totalPaginas > 1 && paginaCartaoAtual > 1) {
      adicionarBotaoPaginaCartao(
        paginaCartaoAtual - 1,
        '<i class="bi bi-chevron-left"></i>',
        'Página anterior',
      );
    }

    // Números das páginas
    for (let numero = 1; numero <= totalPaginas; numero++) {
      adicionarBotaoPaginaCartao(numero, numero, `Página ${numero}`);
    }

    // Próxima página
    if (totalPaginas > 1 && paginaCartaoAtual < totalPaginas) {
      adicionarBotaoPaginaCartao(
        paginaCartaoAtual + 1,
        '<i class="bi bi-chevron-right"></i>',
        'Próxima página',
      );
    }
  }

  // ----------------------------------------------------------
  // Cria botão de página
  // ----------------------------------------------------------

  function adicionarBotaoPaginaCartao(numero, conteudo, ariaLabel) {
    if (!containerPaginacao) {
      return;
    }

    const botao = document.createElement('button');

    botao.type = 'button';

    botao.className = 'movimentacoes-pagination__button';

    if (numero === paginaCartaoAtual) {
      botao.classList.add('active');
    }

    botao.setAttribute('aria-label', ariaLabel);

    botao.innerHTML = conteudo;

    botao.addEventListener('click', () => {
      paginaCartaoAtual = numero;

      atualizarTabelaCartao();

      tabelaCartao?.closest('.table-responsive')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    });

    containerPaginacao.appendChild(botao);
  }

  // ----------------------------------------------------------
  // Alterar quantidade por página
  // ----------------------------------------------------------

  pageSizeSelect?.addEventListener('change', () => {
    tamanhoPaginaCartao = parseInt(pageSizeSelect.value, 10) || 15;

    paginaCartaoAtual = 1;

    atualizarTabelaCartao();
  });

  // ----------------------------------------------------------
  // Pesquisa
  // ----------------------------------------------------------

  campoPesquisa?.addEventListener('input', () => {
    paginaCartaoAtual = 1;

    atualizarTabelaCartao();
  });

  // ----------------------------------------------------------
  // Expõe funções para os filtros do HTML
  // ----------------------------------------------------------

  window.atualizarTabelaCartao = atualizarTabelaCartao;

  window.resetarPaginaCartao = () => {
    paginaCartaoAtual = 1;
    atualizarTabelaCartao();
  };

  // ----------------------------------------------------------
  // Primeira atualização
  // ----------------------------------------------------------

  atualizarTabelaCartao();
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

  const avista = document.getElementById('avista');

  const parcelado = document.getElementById('parcelado');

  const categoriaSelect = document.getElementById('categoria_id');

  const cartaoSelect = document.getElementById('meio_pagamento_id');

  const dataInput = document.getElementById('data');

  // Se os elementos do modal não existirem,
  // não tenta inicializar essa parte.
  if (
    !valorInput ||
    !numeroParcelasInput ||
    !valorTotalRadio ||
    !valorParcelaRadio ||
    !valorTipoSection ||
    !valorParcelaCalculado ||
    !textoValorParcela ||
    !avista ||
    !parcelado ||
    !categoriaSelect ||
    !cartaoSelect ||
    !dataInput
  ) {
    return;
  }

  const calcular = () =>
    calcularValorParcela(
      valorInput,
      numeroParcelasInput,
      valorTotalRadio,
      textoValorParcela,
      valorParcelaCalculado,
    );

  avista.addEventListener('change', () =>
    toggleParceladoFields(parcelado, valorTipoSection, calcular),
  );

  parcelado.addEventListener('change', () =>
    toggleParceladoFields(parcelado, valorTipoSection, calcular),
  );

  valorInput.addEventListener('input', calcular);

  numeroParcelasInput.addEventListener('input', calcular);

  valorTotalRadio.addEventListener('change', calcular);

  valorParcelaRadio.addEventListener('change', () => {
    valorParcelaCalculado.style.display = 'none';
  });

  categoriaSelect.addEventListener('change', (e) => {
    validarSelect(e.target, 'Por favor, selecione uma categoria.');
  });

  cartaoSelect.addEventListener('change', (e) => {
    validarSelect(e.target, 'Por favor, selecione um cartão.');

    preverFatura();
  });

  dataInput.addEventListener('change', preverFatura);
}

// === DOM Ready ===

document.addEventListener('DOMContentLoaded', function () {
  configurarEventosComuns();

  // ========================================================
  // IMPORTANTE:
  // Inicializa a tabela AQUI, ao carregar a página.
  // Não fica mais dentro do botão "Nova Compra".
  // ========================================================

  configurarTabelaCartao();

  if (typeof aplicarMascaraValor === 'function') {
    aplicarMascaraValor('valor');
  } else {
    console.warn('Atenção: mascara.js não foi carregado corretamente.');
  }

  let instanciaModal = null;

  // ========================================================
  // Barras de progresso
  // ========================================================

  const barras = document.querySelectorAll('.progress-bar');

  barras.forEach((bar) => {
    const finalWidth = bar.getAttribute('data-final-width');

    setTimeout(() => {
      bar.style.width = finalWidth + '%';
    }, 50);
  });

  // ========================================================
  // NOVA COMPRA
  // ========================================================

  const novaCompraButton = document.getElementById('novaCompraButton');

  if (novaCompraButton) {
    novaCompraButton.addEventListener('click', () => {
      const form = document.getElementById('formAddDespesaCartao');

      if (!form) return;

      // Reset padrão
      form.reset();

      // Desliga a chave de estorno por padrão
      const chkEstorno = document.getElementById('is_estorno');

      if (chkEstorno) {
        chkEstorno.checked = false;
      }

      // Modo adicionar
      form.setAttribute('data-mode', 'add');

      form.removeAttribute('data-id');

      form.removeAttribute('action');

      // Texto do botão
      const btnSalvar = document.getElementById('btnSalvarMovimentacao');

      if (btnSalvar) {
        btnSalvar.innerText = 'Salvar';
      }

      // Seleciona primeiro item dos selects
      if (form.categoria_id) {
        form.categoria_id.selectedIndex = 0;
      }

      if (form.meio_pagamento_id) {
        form.meio_pagamento_id.selectedIndex = 0;
      }

      // Marca "à vista" como padrão
      const avista = document.getElementById('avista');

      const parcelado = document.getElementById('parcelado');

      if (avista) {
        avista.checked = true;
        avista.disabled = false;
      }

      if (parcelado) {
        parcelado.disabled = false;
      }

      // Remove opacidade
      const lblAvista = document.getElementById('lblAvista');

      const lblParcelado = document.getElementById('lblParcelado');

      lblAvista?.classList.remove('opacity-25');

      lblParcelado?.classList.remove('opacity-25');

      // Esconde seção de valor tipo
      const valorTipoSection = document.getElementById('valorTipoSection');

      if (valorTipoSection) {
        valorTipoSection.style.display = 'none';
      }

      // ====================================================
      // Recorrência
      // ====================================================

      const recorrenteSection = document.getElementById('recorrenteSection');

      if (recorrenteSection) {
        recorrenteSection.classList.remove('d-none');

        recorrenteSection.classList.add('d-flex');

        const selectReplicar = document.getElementById('replicar');

        if (selectReplicar) {
          selectReplicar.value = 'nao';
        }
      }

      // ====================================================
      // Limpa número de parcelas
      // ====================================================

      const parcelasInput = form.querySelector('[name="numero_parcelas"]');

      if (parcelasInput) {
        parcelasInput.value = '';
      }

      // ====================================================
      // Limpa radios do tipo de valor
      // ====================================================

      const tipoValorRadios = document.querySelectorAll(
        "input[name='tipo_valor']",
      );

      tipoValorRadios.forEach((radio) => {
        radio.checked = false;
      });

      // ====================================================
      // Reseta fatura prevista
      // ====================================================

      const badgeFatura = document.getElementById('faturaPrevista');

      if (badgeFatura) {
        badgeFatura.innerText = 'Selecione data e cartão';
      }

      // ====================================================
      // Define a data como hoje
      // ====================================================

      if (typeof setHoje === 'function') {
        setHoje(document.getElementById('data'));
      }

      // Atualiza fatura prevista
      preverFatura();

      // ====================================================
      // Abre modal
      // ====================================================

      const modalElement = document.getElementById('modalMovimentacaoCartao');

      if (modalElement) {
        instanciaModal = bootstrap.Modal.getOrCreateInstance(modalElement);

        instanciaModal.show();
      }
    });
  }

  // ========================================================
  // EDITAR
  // ========================================================

  document.querySelectorAll('.btn-editar').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;

      try {
        const res = await fetch(`/cartao/mov_cartao/editar/${id}`, {
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
          },
        });

        if (!res.ok) {
          throw new Error('Erro ao buscar movimentação');
        }

        const data = await res.json();

        const form = document.getElementById('formAddDespesaCartao');

        if (!form) {
          return;
        }

        form.setAttribute('data-mode', 'edit');

        form.setAttribute('data-id', id);

        form.removeAttribute('action');

        // Descrição
        if (form.descricao) {
          form.descricao.value = data.descricao;
        }

        // ==================================================
        // Valor / Estorno
        // ==================================================

        const valorNumerico = parseFloat(data.valor);

        const isEstorno = document.getElementById('is_estorno');

        if (valorNumerico < 0) {
          if (isEstorno) {
            isEstorno.checked = true;
          }

          if (form.valor) {
            form.valor.value = Math.abs(valorNumerico)
              .toFixed(2)
              .replace('.', ',');
          }
        } else {
          if (isEstorno) {
            isEstorno.checked = false;
          }

          if (form.valor) {
            form.valor.value = data.valor;
          }
        }

        // Data
        if (form.data) {
          form.data.value = data.data_compra;
        }

        // ==================================================
        // Próximas parcelas
        // ==================================================

        const blocoProximas = document.getElementById('blocoAlterarProximas');

        if (blocoProximas) {
          if (data.numero_parcelas > 1 || data.compra_grupo_id) {
            blocoProximas.classList.remove('d-none');

            const alterarProximas = document.getElementById('alterar_proximas');

            if (alterarProximas) {
              alterarProximas.checked = false;
            }
          } else {
            blocoProximas.classList.add('d-none');
          }
        }

        // ==================================================
        // Cartão
        // ==================================================

        if (form.meio_pagamento_id) {
          form.meio_pagamento_id.value = data.meio_pagamento_id;
        }

        // ==================================================
        // Categoria
        // ==================================================

        const catSelect = document.getElementById('categoria_id');

        if (catSelect) {
          const opcaoCategoria = catSelect.querySelector(
            `option[value="${data.categoria_id}"]`,
          );

          if (opcaoCategoria) {
            opcaoCategoria.style.display = '';

            catSelect.value = data.categoria_id;
          }
        }

        // ==================================================
        // Tipos de pagamento
        // ==================================================

        const avista = document.getElementById('avista');

        const parcelado = document.getElementById('parcelado');

        ['avista', 'parcelado'].forEach((tipo) => {
          const radio = document.getElementById(tipo);

          if (!radio) {
            return;
          }

          radio.disabled = false;

          const label = document.getElementById(
            'lbl' + tipo.charAt(0).toUpperCase() + tipo.slice(1),
          );

          label?.classList.remove('opacity-25');
        });

        // ==================================================
        // Número de parcelas
        // ==================================================

        const numeroParcelas = form.querySelector('[name="numero_parcelas"]');

        if (data.numero_parcelas === 1) {
          if (avista) {
            avista.checked = true;
          }

          if (parcelado) {
            parcelado.disabled = true;
          }

          document.getElementById('lblParcelado')?.classList.add('opacity-25');

          if (numeroParcelas) {
            numeroParcelas.value = '';
          }
        } else {
          if (parcelado) {
            parcelado.checked = true;
            parcelado.disabled = false;
          }

          if (avista) {
            avista.disabled = true;
          }

          document.getElementById('lblAvista')?.classList.add('opacity-25');

          if (numeroParcelas) {
            numeroParcelas.value = data.numero_parcelas || '';
          }
        }

        // ==================================================
        // Oculta tipo de valor
        // ==================================================

        const valorTipoSection = document.getElementById('valorTipoSection');

        if (valorTipoSection) {
          valorTipoSection.style.display = 'none';
        }

        // ==================================================
        // Oculta recorrência
        // ==================================================

        const recorrenteSection = document.getElementById('recorrenteSection');

        if (recorrenteSection) {
          recorrenteSection.classList.remove('d-flex');

          recorrenteSection.classList.add('d-none');
        }

        // ==================================================
        // Botão atualizar
        // ==================================================

        const btnSalvar = document.getElementById('btnSalvarMovimentacao');

        if (btnSalvar) {
          btnSalvar.innerText = 'Atualizar';
        }

        // ==================================================
        // Fatura original
        // ==================================================

        const selectFatura = document.getElementById('fatura_mes_ano');

        if (selectFatura) {
          fetch(
            `/faturas/fatura_nome/${data.fatura_id_mes}/${data.fatura_id_ano}`,
          )
            .then((res) => res.json())
            .then((info) => {
              selectFatura.innerHTML = `<option value="${data.fatura_id_mes}-${data.fatura_id_ano}" selected>${info.texto}</option>`;
            })
            .catch(() => {
              preverFatura();
            });
        }

        // ==================================================
        // Abre modal
        // ==================================================

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

  // ========================================================
  // SUBMIT DO FORMULÁRIO
  // ========================================================

  const formAddDespesaCartao = document.getElementById('formAddDespesaCartao');

  if (formAddDespesaCartao) {
    formAddDespesaCartao.addEventListener('submit', async function (e) {
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
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
          },
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

            // Fecha modal
            const modalElement = document.getElementById(
              'modalMovimentacaoCartao',
            );

            if (modalElement) {
              const modal = bootstrap.Modal.getInstance(modalElement);

              modal?.hide();
            }

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
  }
});

// ==========================================================
// EXCLUIR MOVIMENTAÇÃO
// ==========================================================

document.addEventListener('DOMContentLoaded', () => {
  const formsExcluir = document.querySelectorAll('.form-excluir');

  formsExcluir.forEach((form) => {
    form.addEventListener('submit', function (event) {
      event.preventDefault();

      const numeroParcelas =
        parseInt(this.getAttribute('data-parcelas'), 10) || 1;

      const inputExcluirTodas = this.querySelector('.input-excluir-todas');

      // Primeira confirmação
      if (confirm('Tem certeza que deseja excluir este lançamento?')) {
        // Segunda confirmação para parceladas
        if (numeroParcelas > 1) {
          const apagarTodas = confirm(
            '⚠️ COMPRA PARCELADA DETECTADA!\n\n' +
              '• Clique em [OK] se quiser apagar TODAS as parcelas desta compra.\n' +
              '• Clique em [Cancelar] se quiser apagar APENAS esta parcela.',
          );

          if (inputExcluirTodas) {
            inputExcluirTodas.value = apagarTodas ? 'true' : 'false';
          }
        }

        this.submit();
      }
    });
  });
});

// ==========================================================
// SALDO NO MODAL PAGAR
// ==========================================================

function atualizarSaldoConta(faturaId) {
  const modal = document.getElementById('modalPagarFatura' + faturaId);

  if (!modal) {
    return;
  }

  const selectElement = modal.querySelector('select[name="conta_id"]');

  const valorInput = document.getElementById('valor_' + faturaId);

  const campoSaldo = document.getElementById('saldoConta_' + faturaId);

  const botaoConfirmar = modal.querySelector('.btn.btn-purple');

  if (!selectElement || !valorInput) {
    return;
  }

  const selectedOption = selectElement.options[selectElement.selectedIndex];

  const saldoConta =
    parseFloat(selectedOption?.getAttribute('data-saldo')) || 0;

  const valorPagamento = parseFloat(valorInput.value) || 0;

  if (campoSaldo) {
    campoSaldo.textContent =
      'R$ ' +
      saldoConta.toLocaleString('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });

    if (valorPagamento > saldoConta) {
      campoSaldo.classList.remove('text-success');

      campoSaldo.classList.add('text-danger');

      if (botaoConfirmar) {
        botaoConfirmar.disabled = true;
      }
    } else if (valorPagamento <= 0) {
      if (botaoConfirmar) {
        botaoConfirmar.disabled = true;
      }
    } else {
      campoSaldo.classList.remove('text-danger');

      campoSaldo.classList.add('text-success');

      if (botaoConfirmar) {
        botaoConfirmar.disabled = false;
      }
    }
  }
}

// ==========================================================
// FILTROS DA TABELA
// ==========================================================

function toggleFiltro(tipo) {
  const menuCat = document.getElementById('menuFiltroCategoria');

  const menuCartao = document.getElementById('menuFiltroCartao');

  if (!menuCat || !menuCartao) {
    return;
  }

  if (tipo === 'categoria') {
    menuCat.classList.toggle('d-none');

    menuCartao.classList.add('d-none');
  } else {
    menuCartao.classList.toggle('d-none');

    menuCat.classList.add('d-none');
  }
}

// ==========================================================
// Aplica filtro de Categoria / Cartão
// ==========================================================

function aplicarFiltroTabelaMovCartoes() {
  // Sempre volta para a primeira página
  // quando algum filtro é alterado.
  if (window.resetarPaginaCartao) {
    window.resetarPaginaCartao();
  }

  // Fecha os menus
  const menuCategoria = document.getElementById('menuFiltroCategoria');

  const menuCartao = document.getElementById('menuFiltroCartao');

  menuCategoria?.classList.add('d-none');

  menuCartao?.classList.add('d-none');
}

// ==========================================================
// Fecha menus ao clicar fora
// ==========================================================

document.addEventListener('click', function (e) {
  const menuCat = document.getElementById('menuFiltroCategoria');

  const menuCartao = document.getElementById('menuFiltroCartao');

  // Se o clique não foi dentro do menu
  // e não foi no ícone do filtro,
  // fecha os menus.
  if (
    !e.target.closest('.filtro-dropdown') &&
    !e.target.closest('.filtro-icon')
  ) {
    if (menuCat) {
      menuCat.classList.add('d-none');
    }

    if (menuCartao) {
      menuCartao.classList.add('d-none');
    }
  }
});
