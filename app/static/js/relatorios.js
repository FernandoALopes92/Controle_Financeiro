document.addEventListener('DOMContentLoaded', function () {
  // 1. INICIALIZAÇÃO DOS TOOLTIPS
  var tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]'),
  );
  var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // 2. LÓGICA DO DASHBOARD EXECUTIVO
  if (window.dadosRelatorio) {
    const dados = window.dadosRelatorio;

    document
      .querySelectorAll('.stats-card__sparkline')
      .forEach(function (canvas) {
        const tipo = canvas.dataset.chartType;

        criarMiniGrafico(canvas, dados, tipo);
      });

    const totalReceitas = dados.totalReceitasAno;
    const totalDespesas = dados.totalDespesasAno;
    const totalSobra = totalReceitas - totalDespesas;

    // --- PREENCHENDO OS CARDS (RAIO-X) ---

    // Card 1: Eficiência Financeira (%)
    let eficiencia = 0;
    if (totalReceitas > 0) {
      eficiencia = (totalSobra / totalReceitas) * 100;
    }
    let elEficiencia = document.getElementById('cardEficiencia');
    if (elEficiencia) {
      elEficiencia.innerText = eficiencia.toFixed(1) + '%';
      if (eficiencia < 0)
        elEficiencia.classList.replace('text-dark', 'text-danger');
    }

    // Card 2: Projeção de Fechamento Anual (Baseado na média mensal de sobra)
    // Conta os meses em que houve receita para tirar uma média realista
    let mesesAtivos = dados.receitas.filter((r) => r > 0).length || 1;
    let mediaSobra = totalSobra / mesesAtivos;
    let projecao = mediaSobra * 12;
    let elProjecao = document.getElementById('cardProjecao');
    if (elProjecao) {
      elProjecao.innerText =
        'R$ ' + projecao.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
      if (projecao < 0)
        elProjecao.classList.replace('text-dark', 'text-danger');
    }

    // Card 3: O Grande Vilão
    let vilaoNome = '--';
    let maxValor = -1;
    dados.categoriasValores.forEach((val, index) => {
      if (val > maxValor) {
        maxValor = val;
        vilaoNome = dados.categoriasNomes[index];
      }
    });
    if (document.getElementById('cardVilao'))
      document.getElementById('cardVilao').innerText = vilaoNome;

    // Card 4: Termômetro de Consumo
    let taxaConsumo = 0;
    if (totalReceitas > 0) {
      taxaConsumo = (totalDespesas / totalReceitas) * 100;
    }
    let barraConsumo = document.getElementById('barraConsumo');
    if (barraConsumo) {
      barraConsumo.style.width = Math.min(taxaConsumo, 100) + '%';
      document.getElementById('textoConsumo').innerText =
        taxaConsumo.toFixed(1) + '% consumido';

      // Fica vermelho se consumiu mais de 80% do que ganhou
      if (taxaConsumo > 80) {
        barraConsumo.classList.replace('bg-warning', 'bg-danger');
      }
    }

    // --- PLOTAGEM DOS GRÁFICOS ---
    const formataReal = (valor) =>
      'R$ ' + valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 });

    // Gráfico 1: Linha (Evolução da Sobra)
    const canvasLine = document.getElementById('lineChart');
    if (canvasLine) {
      new Chart(canvasLine.getContext('2d'), {
        type: 'line',
        data: {
          labels: dados.meses,
          datasets: [
            {
              label: 'Sobra Real',
              data: dados.sobras,
              borderColor: '#7f65f2', // Roxo Azulado
              backgroundColor: 'rgba(127, 101, 242, 0.2)', // Fundo semi-transparente abaixo da linha
              borderWidth: 3,
              pointBackgroundColor: '#3b0a87',
              pointRadius: 4,
              fill: true,
              tension: 0.4, // Deixa a linha curvada/suave
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: { label: (ctx) => formataReal(ctx.raw || 0) },
            },
          },
          scales: {
            y: { grid: { borderDash: [4, 4] } },
            x: { grid: { display: false } },
          },
        },
      });
    }

    // Gráfico 2: Barras (Receitas vs Despesas)
    const canvasBar = document.getElementById('barChart');
    if (canvasBar) {
      new Chart(canvasBar.getContext('2d'), {
        type: 'bar',
        data: {
          labels: dados.meses,
          datasets: [
            {
              label: 'Receitas',
              data: dados.receitas,
              backgroundColor: 'rgba(25, 135, 84, 0.85)',
              borderRadius: 4,
            },
            {
              label: 'Despesas',
              data: dados.despesas,
              backgroundColor: 'rgba(220, 53, 69, 0.85)',
              borderRadius: 4,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'top',
              labels: { usePointStyle: true, boxWidth: 8 },
            },
            tooltip: {
              callbacks: { label: (ctx) => formataReal(ctx.raw || 0) },
            },
          },
          scales: {
            y: { beginAtZero: true, grid: { borderDash: [4, 4] } },
            x: { grid: { display: false } },
          },
        },
      });
    }

    // Gráfico 3: Rosca (Categorias)
    const canvasDoughnut = document.getElementById('doughnutChart');
    if (canvasDoughnut) {
      const paletaCores = [
        '#3b0a87',
        '#6a0dad',
        '#7f65f2',
        '#9b59b6',
        '#b892f6',
        '#d8c1f9',
        '#dc3545',
        '#fd7e14',
        '#ffc107',
        '#20c997',
      ];
      new Chart(canvasDoughnut.getContext('2d'), {
        type: 'doughnut',
        data: {
          labels: dados.categoriasNomes,
          datasets: [
            {
              data: dados.categoriasValores,
              backgroundColor: paletaCores,
              borderWidth: 2,
              borderColor: '#ffffff',
              hoverOffset: 8,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '68%',
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) =>
                  ' ' + ctx.label + ': ' + formataReal(ctx.raw || 0),
              },
            },
          },
        },
      });
    }
  }
});

function hexToRgba(hex, alpha) {
  hex = hex.replace('#', '');

  if (hex.length === 3) {
    hex = hex
      .split('')
      .map((char) => char + char)
      .join('');
  }

  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);

  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function criarMiniGrafico(canvas, dados, tipo) {
  if (!canvas || !dados) {
    return;
  }

  const cores = {
    receitas: 'var(--color-success)',
    despesas: 'var(--color-danger)',
    economia: 'var(--color-primary-500)',
    meta: 'var(--color-warning)',
  };

  const cor = getComputedStyle(document.documentElement)
    .getPropertyValue(
      tipo === 'receitas'
        ? '--color-success'
        : tipo === 'despesas'
          ? '--color-danger'
          : tipo === 'economia'
            ? '--color-primary-500'
            : '--color-warning',
    )
    .trim();

  const series = {
    receitas: dados.receitas,
    despesas: dados.despesas,
    economia: dados.sobras,
  };

  const valores = series[tipo];

  // ==========================================================
  // META — GRÁFICO DE ROSCA
  // ==========================================================
  if (tipo === 'meta') {
    const metaTotal = Number(dados.metaAno || 0);

    const mesAtual = dados.mesAtual || 12;

    const realizado = dados.sobras
      .slice(0, mesAtual)
      .reduce((total, valor) => total + Number(valor || 0), 0);

    if (metaTotal <= 0) {
      return;
    }

    const realizadoLimitado = Math.max(0, Math.min(realizado, metaTotal));

    const restante = Math.max(0, metaTotal - realizadoLimitado);

    const percentual =
      metaTotal > 0 ? (realizadoLimitado / metaTotal) * 100 : 0;

    const ctx = canvas.getContext('2d');

    const textoCentro = {
      id: 'textoCentroMeta',

      afterDraw(chart) {
        const { ctx, chartArea } = chart;

        const x = (chartArea.left + chartArea.right) / 2;
        const y = (chartArea.top + chartArea.bottom) / 2;

        ctx.save();

        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        ctx.fillStyle = getComputedStyle(document.documentElement)
          .getPropertyValue('--color-warning')
          .trim();

        ctx.font = '800 1.1rem sans-serif';

        ctx.fillText(`${Math.round(percentual)}%`, x, y);

        ctx.restore();
      },
    };

    new Chart(ctx, {
      type: 'doughnut',

      plugins: [textoCentro],

      data: {
        labels: ['Realizado', 'Restante'],

        datasets: [
          {
            data: [realizadoLimitado, restante],

            backgroundColor: [cor, 'rgba(0, 0, 0, 0.06)'],

            borderWidth: 0,

            hoverOffset: 0,
          },
        ],
      },

      options: {
        responsive: true,
        maintainAspectRatio: false,

        cutout: '72%',

        plugins: {
          legend: {
            display: false,
          },

          tooltip: {
            callbacks: {
              label: function (context) {
                const valor = Number(context.raw || 0);

                return (
                  context.label +
                  ': R$ ' +
                  valor.toLocaleString('pt-BR', {
                    minimumFractionDigits: 2,
                  })
                );
              },
            },
          },
        },
      },
    });

    return;
  }

  // ==========================================================
  // GRÁFICOS DE LINHA — RECEITAS / DESPESAS / ECONOMIA
  // ==========================================================

  if (!valores || !valores.length) {
    return;
  }

  const ctx = canvas.getContext('2d');

  const gradiente = ctx.createLinearGradient(0, 0, 0, canvas.height);

  gradiente.addColorStop(0, hexToRgba(cor, 0.2));

  gradiente.addColorStop(1, hexToRgba(cor, 0.0));

  new Chart(ctx, {
    type: 'line',

    data: {
      labels: dados.meses,

      datasets: [
        {
          data: valores,

          borderColor: cor,
          backgroundColor: gradiente,

          borderWidth: 2,

          pointRadius: 0,
          pointHoverRadius: 3,

          tension: 0.4,

          fill: true,
        },
      ],
    },

    options: {
      responsive: true,
      maintainAspectRatio: false,

      plugins: {
        legend: {
          display: false,
        },

        tooltip: {
          enabled: true,

          callbacks: {
            label: function (context) {
              return (
                'R$ ' +
                Number(context.raw || 0).toLocaleString('pt-BR', {
                  minimumFractionDigits: 2,
                })
              );
            },
          },
        },
      },

      scales: {
        x: {
          display: false,
          grid: {
            display: false,
          },
        },

        y: {
          display: false,
          grid: {
            display: false,
          },
        },
      },

      interaction: {
        intersect: false,
        mode: 'index',
      },
    },
  });
}

// Nova função inteligente que abre/fecha qualquer bloco passando o nome da classe
function toggleLinhaExpandivel(targetClass, iconId) {
  const subRows = document.querySelectorAll('.' + targetClass);
  const icon = document.getElementById(iconId);

  // Mostra/Oculta as sub-linhas
  subRows.forEach((row) => {
    row.classList.toggle('d-none');
  });

  // Troca o ícone de + para -
  if (icon) {
    if (icon.classList.contains('bi-plus-square-fill')) {
      icon.classList.remove('bi-plus-square-fill');
      icon.classList.add('bi-minus-square-fill');
    } else {
      icon.classList.remove('bi-minus-square-fill');
      icon.classList.add('bi-plus-square-fill');
    }
  }
}

function toggleSecaoRelatorio(button) {
  const section = button.closest('.report-section');

  if (!section) {
    return;
  }

  const tableWrapper = section.querySelector('.report-table-wrapper');

  if (!tableWrapper) {
    return;
  }

  const chevron = button.querySelector('.report-section__chevron');
  const label = button.querySelector('span');

  const isHidden = tableWrapper.classList.toggle('d-none');

  if (isHidden) {
    label.innerHTML =
      '<i class="bi bi-layout-text-window-reverse"></i> Ver detalhes';

    chevron.classList.remove('bi-chevron-up');
    chevron.classList.add('bi-chevron-down');
  } else {
    label.innerHTML =
      '<i class="bi bi-layout-text-window-reverse"></i> Ocultar detalhes';

    chevron.classList.remove('bi-chevron-down');
    chevron.classList.add('bi-chevron-up');
  }
}
