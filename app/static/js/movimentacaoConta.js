(() => {
  function criarGraficoReceitasDespesas(
    idCanvas,
    totalReceitas,
    totalDespesas,
  ) {
    const canvas = document.getElementById(idCanvas);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    // Gradiente Receitas (roxo)
    const gradientReceitas = ctx.createLinearGradient(0, 0, 0, 200);
    gradientReceitas.addColorStop(0, '#6C3DF4');
    gradientReceitas.addColorStop(1, '#A88BFC');

    // Gradiente Despesas (vermelho pastel)
    const gradientDespesas = ctx.createLinearGradient(0, 0, 0, 200);
    gradientDespesas.addColorStop(0, '#F27878');
    gradientDespesas.addColorStop(1, '#FFC1C1');

    if (window.graficoReceitasDespesasInstance) {
      window.graficoReceitasDespesasInstance.destroy();
    }

    window.graficoReceitasDespesasInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Receitas', 'Despesas'],
        datasets: [
          {
            label: 'Valor (R$)',
            data: [totalReceitas || 0, totalDespesas || 0],
            backgroundColor: [gradientReceitas, gradientDespesas],
            borderRadius: 6,
            barThickness: 40,
          },
        ],
      },
      options: {
        animation: { duration: 1000, easing: 'easeOutQuart' },
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#fff',
            titleColor: '#000',
            bodyColor: '#000',
            borderColor: '#ccc',
            borderWidth: 1,
            callbacks: {
              label: function (context) {
                return (
                  'R$ ' +
                  context.raw.toLocaleString('pt-BR', {
                    minimumFractionDigits: 2,
                  })
                );
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#444', font: { size: 14 } },
          },
          y: {
            grid: { color: '#eee', drawBorder: false },
            ticks: {
              color: '#555',
              font: { size: 13 },
              callback: function (value) {
                return 'R$ ' + value.toLocaleString('pt-BR');
              },
            },
          },
        },
      },
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    // Define data hoje no input com id "data"
    const dataInput = document.getElementById('data');
    if (dataInput && typeof setHoje === 'function') {
      setHoje(dataInput);
    } else if (dataInput) {
      dataInput.value = new Date().toISOString().split('T')[0];
    }

    // --- FILTRO DE CATEGORIAS E RECORRÊNCIA UNIFICADOS ---
    const radiosTipo = document.querySelectorAll(
      'input[name="tipo_lancamento"]',
    );
    const categoriaSelect = document.getElementById('categoria_id');
    const tituloRecorrente = document.getElementById('tituloRecorrente');
    const textoRecorrente = document.getElementById('textoRecorrente');
    const secaoRecorrente = document.getElementById(
      'recorrenteSectionContaAvulsa',
    );

    function filtrarCategorias(tipoSelecionado) {
      if (!categoriaSelect) return;
      const options = categoriaSelect.querySelectorAll(
        'option:not([disabled])',
      );

      options.forEach((opt) => {
        const tipoOpt = opt.getAttribute('data-tipo');
        if (tipoOpt === tipoSelecionado) {
          opt.style.display = '';
        } else {
          opt.style.display = 'none';
          if (opt.selected) categoriaSelect.value = '';
        }
      });
    }

    // Lógica Inteligente de Transição de Textos da Recorrência
    function ajustarTextosRecorrencia(tipoSelecionado) {
      if (!secaoRecorrente || !tituloRecorrente || !textoRecorrente) return;

      secaoRecorrente.style.display = 'block'; // Sempre visível para ambos

      if (tipoSelecionado === 'receita') {
        tituloRecorrente.innerHTML =
          '<i class="bi bi-arrow-repeat me-1 text-success"></i> Receita Recorrente?';
        textoRecorrente.innerHTML =
          'Ideal para entradas fixas como Salários e Rendimentos.<br> O sistema clonará o lançamento para os meses seguintes.';
      } else {
        tituloRecorrente.innerHTML =
          '<i class="bi bi-arrow-repeat me-1 text-danger"></i> Conta Recorrente?';
        textoRecorrente.innerHTML =
          'Ideal para contas fixas como Internet, Telefone ou Assinaturas. O sistema clonará o lançamento para os meses seguintes.';
      }
    }

    // Ouve o clique nos botões de Receita/Despesa (Gatilho único para os dois comportamentos)
    radiosTipo.forEach((radio) => {
      radio.addEventListener('change', (e) => {
        filtrarCategorias(e.target.value);
        ajustarTextosRecorrencia(e.target.value);
      });
    });

    // Aplica o estado inicial ao carregar a tela (Despesa padrão)
    if (radiosTipo.length > 0) {
      const radioAtivo = document.querySelector(
        'input[name="tipo_lancamento"]:checked',
      );
      if (radioAtivo) {
        filtrarCategorias(radioAtivo.value);
        ajustarTextosRecorrencia(radioAtivo.value);
      }
    }
    // ----------------------------------------------------

    // Atualiza saldo quando mudar a conta selecionada
    const contaSelect = document.getElementById('conta_id');
    if (contaSelect) {
      contaSelect.addEventListener('change', function () {
        const saldoContaContainer = document.getElementById(
          'saldoContaContainer',
        );
        const saldoConta = document.getElementById('saldoConta');
        const selectedOption = this.options[this.selectedIndex];

        if (selectedOption && this.value !== '') {
          const saldo = selectedOption.getAttribute('data-saldo');
          saldoConta.innerHTML =
            'Saldo: R$ ' +
            parseFloat(saldo).toLocaleString('pt-BR', {
              minimumFractionDigits: 2,
            });
          saldoContaContainer.style.display = 'block';
        } else {
          saldoContaContainer.style.display = 'none';
        }
      });
    }

    // Cria gráfico automaticamente se canvas existir e tiver dados
    const canvas = document.getElementById('graficoReceitasDespesas');
    if (canvas) {
      const totalReceitas = parseFloat(canvas.dataset.receitas) || 0;
      const totalDespesas = parseFloat(canvas.dataset.despesas) || 0;
      criarGraficoReceitasDespesas(
        'graficoReceitasDespesas',
        totalReceitas,
        totalDespesas,
      );
    }

    // Botão Editar
    document.querySelectorAll('.btn-editar').forEach((botao) => {
      botao.addEventListener('click', async () => {
        const id = botao.dataset.id;

        const response = await fetch(`/movimentacoes/${id}/json`);
        if (!response.ok) {
          alert('Erro ao carregar movimentação');
          return;
        }

        const mov = await response.json();

        const optTarget = document.querySelector(
          `select[name="categoria_id"] option[value="${mov.categoria_id}"]`,
        );
        if (optTarget) {
          const tipo = optTarget.getAttribute('data-tipo');
          if (tipo === 'receita') {
            document.getElementById('tipo_receita').checked = true;
          } else {
            document.getElementById('tipo_despesa').checked = true;
          }
          filtrarCategorias(tipo);
          ajustarTextosRecorrencia(tipo);
        }

        // Preenche os campos
        document.getElementById('data').value = mov.data;
        document.querySelector('input[name="descricao"]').value = mov.descricao;
        document.querySelector('select[name="categoria_id"]').value =
          mov.categoria_id;
        document.querySelector('input[name="valor"]').value = mov.valor;
        document.querySelector('select[name="conta_id"]').value = mov.conta_id;
        document.querySelector('select[name="pago"]').value = mov.pago
          ? 'true'
          : 'false';

        // Atualiza o saldo da conta automaticamente
        document.getElementById('conta_id').dispatchEvent(new Event('change'));

        // Altera o form para edição
        const form = document.querySelector('#modalMovimentacaoConta form');
        form.action = `/movimentacoes/${id}/editar`;

        document.getElementById('modalMovimentacaoContaLabel').innerHTML =
          '<i class="bi bi-pencil-square me-2"></i>Editar Movimentação';
        form.querySelector('button[type="submit"]').innerText = 'Atualizar';

        // Abre o modal
        const modal = new bootstrap.Modal(
          document.getElementById('modalMovimentacaoConta'),
        );
        modal.show();
      });
    });

    // Limpa e reseta o formulário ao fechar o modal
    document
      .getElementById('modalMovimentacaoConta')
      .addEventListener('hidden.bs.modal', () => {
        const form = document.querySelector('#modalMovimentacaoConta form');
        form.reset();
        form.action = '/movimentacoes/nova';
        document.getElementById('modalMovimentacaoContaLabel').innerHTML =
          '<i class="bi bi-journal-plus me-2"></i>Nova Movimentação';
        form.querySelector('button[type="submit"]').innerText = 'Salvar';

        // Esconde saldo conta
        document.getElementById('saldoContaContainer').style.display = 'none';

        // Reseta o filtro de categorias e textos para "Despesa"
        document.getElementById('tipo_despesa').checked = true;
        filtrarCategorias('despesa');
        ajustarTextosRecorrencia('despesa');
      });
  });

  window.criarGraficoReceitasDespesas = criarGraficoReceitasDespesas;
})();

// --- ATIVAÇÃO DO BOTÃO EXCLUIR ---
document.addEventListener('DOMContentLoaded', () => {
  if (typeof aplicarConfirmacaoExclusao === 'function') {
    aplicarConfirmacaoExclusao(
      '.btn-excluir',
      (id) => `/movimentacoes/${id}/excluir`,
    );
  } else {
    document.querySelectorAll('.btn-excluir').forEach((botao) => {
      botao.addEventListener('click', () => {
        const id = botao.dataset.id;
        if (
          confirm(
            'Tem certeza que deseja excluir esta movimentação? O saldo da conta será recalculado automaticamente.',
          )
        ) {
          fetch(`/movimentacoes/${id}/excluir`, {
            method: 'POST',
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
              'X-CSRFToken': getCsrfToken(),
            },
          })
            .then((res) => {
              if (res.ok) location.reload();
              else alert('Erro ao tentar excluir a movimentação.');
            })
            .catch((err) => console.error('Erro:', err));
        }
      });
    });
  }
});
