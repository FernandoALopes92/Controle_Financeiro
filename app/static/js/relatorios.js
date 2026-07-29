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
          cutout: '70%',
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
