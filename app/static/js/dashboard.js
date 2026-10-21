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
  });
