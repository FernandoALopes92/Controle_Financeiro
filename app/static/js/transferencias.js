

  // ==========================================
  // 2. Lógica de Edição (Agora armazena os dados originais)
  // ==========================================
  document.addEventListener('click', function (e) {
    const botao = e.target.closest('.btn-editar-transf');

    if (botao) {
      try {
        const id = botao.dataset.id;
        const origenId = botao.dataset.origem;
        const destinoId = botao.dataset.destino;
        const valor = botao.dataset.valor;
        const data = botao.dataset.data;
        const observacoes = botao.dataset.observacoes;

        modalTransf.querySelector('#conta_origem').value = origenId;
        modalTransf.querySelector('#conta_destino').value = destinoId;
        modalTransf.querySelector('#valor').value = valor;
        modalTransf.querySelector('#dataTransferencia').value = data;
        modalTransf.querySelector('#descricao').value = observacoes || '';

        modalTransf.querySelector('#conta_origem').dispatchEvent(new Event('change'));
        modalTransf.querySelector('#conta_destino').dispatchEvent(new Event('change'));

        const form = modalTransf.querySelector('form');
        form.action = `/transferencias/editar/${id}`;

        // NOVO: Guarda os valores originais no formulário para a trava de segurança usar depois
        form.dataset.origemOriginal = origenId;
        form.dataset.valorOriginal = valor;

        modalTransf.querySelector('#modalTransferenciaLabel').innerHTML =
          '<i class="bi bi-pencil-square me-2"></i>Editar Transferência';
        form.querySelector('button[type="submit"]').innerText = 'Atualizar';
      } catch (erro) {
        console.error('Erro ao preencher o modal de edição:', erro);

        Swal.fire({
          icon: 'error',
          title: 'Erro ao abrir transferência',
          text: 'Não foi possível preencher os dados da transferência. Tente novamente.',
          confirmButtonText: 'Entendi',
        });
      }
    }
  });

  // 3. Lógica para Resetar o Modal ao fechar
  modalTransf.addEventListener('hidden.bs.modal', () => {
    const form = modalTransf.querySelector('form');
    form.reset();
    form.action = '/transferencias/nova';

    // Limpa a memória dos valores antigos
    delete form.dataset.origemOriginal;
    delete form.dataset.valorOriginal;

    modalTransf.querySelector('#modalTransferenciaLabel').innerHTML =
      '<i class="bi bi-arrow-left-right me-2"></i>Nova Transferência';
    form.querySelector('button[type="submit"]').innerText = 'Transferir';

    if (saldoOrigemContainer) saldoOrigemContainer.style.display = 'none';
    if (saldoDestinoContainer) saldoDestinoContainer.style.display = 'none';
  });

  // ==========================================
  // 4. TRAVA DE SEGURANÇA EM TEMPO REAL (Com Saldo Virtual)
  // ==========================================
  const formTransfAntigo = modalTransf.querySelector('form');

  if (formTransfAntigo) {
    formTransfAntigo.addEventListener('submit', function (e) {
      const selectOrigem = formTransfAntigo.querySelector('#conta_origem');
      const selectDestino = formTransfAntigo.querySelector('#conta_destino');
      const inputValor = formTransfAntigo.querySelector('#valor');

      if (!selectOrigem || !selectDestino || !inputValor) return;

      const origemId = selectOrigem.value;
      const destinoId = selectDestino.value;
      const valor = parseFloat(inputValor.value) || 0;

      if (origemId === destinoId) {
        e.preventDefault();

        Swal.fire({
          icon: 'warning',
          title: 'Contas inválidas',
          text: 'A conta de origem e a conta de destino devem ser diferentes.',
          confirmButtonText: 'Entendi',
        });

        return;
      }

      if (valor <= 0) {
        e.preventDefault();

        Swal.fire({
          icon: 'warning',
          title: 'Valor inválido',
          text: 'O valor da transferência deve ser maior que zero.',
          confirmButtonText: 'Entendi',
        });

        return;
      }

      // Prepara o saldo base lendo o HTML
      const optSelecionada = selectOrigem.options[selectOrigem.selectedIndex];
      let saldoDisponivel = parseFloat(optSelecionada.getAttribute('data-saldo')) || 0;

      const modoEdicao = formTransfAntigo.action.includes('editar');

      // A MÁGICA DO SALDO VIRTUAL ACONTECE AQUI
      if (modoEdicao) {
        const origemOriginal = formTransfAntigo.dataset.origemOriginal;
        const valorOriginal = parseFloat(formTransfAntigo.dataset.valorOriginal) || 0;

        // Se a conta de origem continuar a mesma, nós projetamos o estorno do valor antigo
        if (origemId === origemOriginal) {
          saldoDisponivel += valorOriginal;
        }
      }

      // Validação final bloqueando a tela se faltar dinheiro
      if (valor > saldoDisponivel) {
        e.preventDefault();

        Swal.fire({
          icon: 'warning',
          title: 'Saldo insuficiente',
          text:
            'O saldo disponível na conta de origem é R$ ' +
            saldoDisponivel.toLocaleString('pt-BR', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            }) +
            '.',
          confirmButtonText: 'Entendi',
        });

        return;
      }
    });
  }
});

// --- CONFIRMAÇÃO DE EXCLUSÃO DE TRANSFERÊNCIA ---
document.addEventListener('click', (event) => {
  const botao = event.target.closest('.btn-excluir-transf');

  if (!botao) return;

  event.preventDefault();

  const form = botao.closest('form');

  if (!form) return;

  const linha = botao.closest('tr');

  const data = linha?.querySelector('td:nth-child(1)')?.textContent.trim() || '';

  const origem = linha?.querySelector('.conta-origem')?.textContent.trim() || '';

  const destino = linha?.querySelector('.conta-destino')?.textContent.trim() || '';

  const valor = linha?.querySelector('.valor-transferencia')?.textContent.trim() || '';

  Swal.fire({
    title: 'Excluir transferência?',
    html: `
      <div class="system-confirmation">
        <div class="system-confirmation__content">
          <span class="system-confirmation__label">
            Você está prestes a excluir esta transferência:
          </span>

          <strong class="system-confirmation__description">
            Conta de origem: ${origem}
          </strong>

          <strong class="system-confirmation__description">
            Conta de destino: ${destino}
          </strong>

          <span class="system-confirmation__details">
            ${data} · ${valor}
          </span>

          <span class="system-confirmation__warning">
            O dinheiro será devolvido à conta de origem.
          </span>
        </div>
      </div>
    `,
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#df4a55',
    cancelButtonColor: '#adb5bd',
    confirmButtonText: 'Sim, excluir',
    cancelButtonText: 'Cancelar',
  }).then((result) => {
    if (result.isConfirmed) {
      form.submit();
    }
  });
});
