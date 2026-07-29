console.log('O arquivo transferencias.js foi carregado com sucesso!');

document.addEventListener('DOMContentLoaded', () => {
  const modalTransf = document.getElementById('modalTransferencia');
  if (!modalTransf) return;

  // 1. Lógica para mostrar o Saldo da Conta Dinamicamente
  const contaOrigem = modalTransf.querySelector('#conta_origem');
  const saldoOrigemContainer = modalTransf.querySelector(
    '#saldoContaOrigemContainer',
  );
  const saldoOrigem = modalTransf.querySelector('#saldoContaOrigem');

  const contaDestino = modalTransf.querySelector('#conta_destino');
  const saldoDestinoContainer = modalTransf.querySelector(
    '#saldoContaDestinoContainer',
  );
  const saldoDestino = modalTransf.querySelector('#saldoContaDestino');

  function atualizarSaldo(selectElem, containerElem, labelElem) {
    if (!selectElem) return;
    const selectedOption = selectElem.options[selectElem.selectedIndex];

    if (selectedOption && selectElem.value !== '') {
      const saldo = selectedOption.getAttribute('data-saldo');
      labelElem.innerHTML =
        'Saldo: R$ ' +
        parseFloat(saldo).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
      containerElem.style.display = 'block';
    } else {
      containerElem.style.display = 'none';
    }
  }

  if (contaOrigem) {
    contaOrigem.addEventListener('change', () =>
      atualizarSaldo(contaOrigem, saldoOrigemContainer, saldoOrigem),
    );
  }
  if (contaDestino) {
    contaDestino.addEventListener('change', () =>
      atualizarSaldo(contaDestino, saldoDestinoContainer, saldoDestino),
    );
  }

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

        modalTransf
          .querySelector('#conta_origem')
          .dispatchEvent(new Event('change'));
        modalTransf
          .querySelector('#conta_destino')
          .dispatchEvent(new Event('change'));

        const form = modalTransf.querySelector('form');
        form.action = `/transferencias/editar/${id}`;

        // NOVO: Guarda os valores originais no formulário para a trava de segurança usar depois
        form.dataset.origemOriginal = origenId;
        form.dataset.valorOriginal = valor;

        modalTransf.querySelector('#modalTransferenciaLabel').innerHTML =
          '<i class="bi bi-pencil-square me-2"></i>Editar Transferência';
        form.querySelector('button[type="submit"]').innerText = 'Atualizar';
      } catch (erro) {
        alert('Erro interno ao preencher o modal de edição: ' + erro.message);
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
        alert('⚠️ A conta de origem e destino devem ser diferentes.');
        e.preventDefault();
        return;
      }

      if (valor <= 0) {
        alert('⚠️ O valor da transferência deve ser maior que zero.');
        e.preventDefault();
        return;
      }

      // Prepara o saldo base lendo o HTML
      const optSelecionada = selectOrigem.options[selectOrigem.selectedIndex];
      let saldoDisponivel =
        parseFloat(optSelecionada.getAttribute('data-saldo')) || 0;

      const modoEdicao = formTransfAntigo.action.includes('editar');

      // A MÁGICA DO SALDO VIRTUAL ACONTECE AQUI
      if (modoEdicao) {
        const origemOriginal = formTransfAntigo.dataset.origemOriginal;
        const valorOriginal =
          parseFloat(formTransfAntigo.dataset.valorOriginal) || 0;

        // Se a conta de origem continuar a mesma, nós projetamos o estorno do valor antigo
        if (origemId === origemOriginal) {
          saldoDisponivel += valorOriginal;
        }
      }

      // Validação final bloqueando a tela se faltar dinheiro
      if (valor > saldoDisponivel) {
        alert(
          '⚠️ Saldo insuficiente na conta de origem. O limite disponível (com o estorno) é R$ ' +
            saldoDisponivel.toLocaleString('pt-BR', {
              minimumFractionDigits: 2,
            }),
        );
        e.preventDefault(); // Impede o envio e mantém o modal aberto!
        return;
      }
    });
  }
});
