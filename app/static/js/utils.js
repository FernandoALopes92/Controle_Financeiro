function getCsrfToken() {
  // Lê o token CSRF da meta tag definida em navbar/base.html
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

function fecharAlertsAutomaticamente(tempo = 1500) {
  // Espera o tempo definido (padrão 4 segundos) e fecha os alerts automaticamente
  setTimeout(() => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach((alert) => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      bsAlert.close();
    });
  }, tempo); // tempo em milissegundos
}

// Chama a função para fechar os alerts após 1.5 segundos
fecharAlertsAutomaticamente(1500); //

const tiposToast = {
  success: 'success',
  danger: 'danger',
  warning: 'warning',
  info: 'info',
  primary: 'primary',
};

const temposToast = {
  success: 4000,
  primary: 3000,
  info: 3000,
  warning: 4000,
  danger: 5000,
};

function exibirToast(mensagem, tipo = 'primary') {
  const toastEl = document.getElementById('liveToast');
  const toastBody = document.getElementById('toastMessage');

  if (!toastEl || !toastBody) {
    return;
  }

  const classeToast = tiposToast[tipo] || 'primary';
  const tempoToast = temposToast[tipo] || 3000;

  toastBody.textContent = mensagem;
  toastEl.className = `toast align-items-center text-bg-${classeToast} border-0`;

  let toast = bootstrap.Toast.getInstance(toastEl);

  if (toast) {
    toast.dispose();
  }

  toast = new bootstrap.Toast(toastEl, {
    autohide: true,
    delay: tempoToast,
  });

  toast.show();
}

//Definir data de Hoje
function setHoje(input) {
  if (typeof input === 'string') {
    input = document.getElementById(input);
  }

  if (input && !input.value) {
    const hoje = new Date();
    const dia = hoje.getDate().toString().padStart(2, '0');
    const mes = (hoje.getMonth() + 1).toString().padStart(2, '0');
    const ano = hoje.getFullYear();
    input.value = `${ano}-${mes}-${dia}`;
  }
}

// document.addEventListener("DOMContentLoaded", () => {
//   const flashDiv = document.getElementById("flash-messages");
//   const rawMessages = flashDiv?.dataset.messages;

//   if (!rawMessages || rawMessages.trim() === "") {
//     console.warn("Nenhuma mensagem flash encontrada ou conteúdo vazio.");
//     return;
//   }

//   let messages = [];
//   try {
//     messages = JSON.parse(rawMessages);
//   } catch (e) {
//     console.warn("Erro ao interpretar mensagens flash:", e);
//     return;
//   }

//   messages.forEach(([categoria, mensagem]) => {
//     let tipoToast = "primary";
//     switch (categoria) {
//       case "success":
//       case "sucesso":
//         tipoToast = "success";
//         break;
//       case "error":
//       case "danger":
//       case "erro":
//         tipoToast = "danger";
//         break;
//       case "warning":
//       case "alert":
//         tipoToast = "warning";
//         break;
//       case "info":
//         tipoToast = "info";
//         break;
//     }
//     exibirToast(mensagem, tipoToast);
//   });
// });

document.addEventListener('DOMContentLoaded', () => {
  const flashDiv = document.getElementById('flash-messages');
  const rawMessages = flashDiv?.dataset.messages;

  if (!rawMessages || rawMessages.trim() === '') {
    console.warn('Nenhuma mensagem flash encontrada ou conteúdo vazio.');
    return;
  }

  let messages = [];
  try {
    messages = JSON.parse(rawMessages);
  } catch (e) {
    console.warn('Erro ao interpretar mensagens flash:', e);
    return;
  }

  messages.forEach(([categoria, mensagem]) => {
    exibirToast(mensagem, categoria);
  });
});

function formatarMoeda(valor) {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(Number(valor));
}

function aplicarConfirmacaoExclusao(selector, urlBuilder, onSuccess = () => location.reload()) {
  document.querySelectorAll(selector).forEach((botao) => {
    botao.addEventListener('click', () => {
      const id = botao.dataset.id;
      const descricao = botao.dataset.descricao;
      const valor = botao.dataset.valor;
      const data = botao.dataset.data;

      const url = typeof urlBuilder === 'function' ? urlBuilder(id) : urlBuilder;

      Swal.fire({
        title: 'Excluir movimentação?',
        html: `
          <div class="system-confirmation">


            <div class="system-confirmation__content">
              <span class="system-confirmation__label">
                Você está prestes a excluir:
              </span>

              <strong class="system-confirmation__description">
                ${descricao}
              </strong>

              <span class="system-confirmation__details">
                ${data} · ${formatarMoeda(valor)}
              </span>

              <span class="system-confirmation__warning">
                Essa ação não pode ser desfeita.
              </span>
            </div>
          </div>
        `,
        icon: 'warning',
        showCancelButton: true,
        cancelButtonColor: '#adb5bd',
        confirmButtonColor: '#df4a55',
        confirmButtonText: 'Sim, excluir',
        cancelButtonText: 'Cancelar',
        reverseButtons: true,
      }).then((result) => {
        if (result.isConfirmed) {
          fetch(url, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Requested-With': 'XMLHttpRequest',
              'X-CSRFToken': getCsrfToken(),
            },
          })
            .then((res) => {
              if (!res.ok) throw new Error('Erro ao excluir');
              return res.json();
            })
            .then((json) => {
              Swal.fire('Excluído!', json.mensagem, 'success').then(onSuccess);
            })
            .catch(() => {
              Swal.fire('Erro', 'Não foi possível excluir.', 'error');
            });
        }
      });
    });
  });
}
//////////////////////////////////////////////
// Função genérica para aplicar máscara de valor monetário
function aplicarMascaraValor(idInput) {
  var elemento = document.getElementById(idInput);
  if (elemento) {
    IMask(elemento, {
      mask: Number,
      scale: 2, // casas decimais
      signed: false, // não permite número negativo
      thousandsSeparator: '.', // separador de milhar
      padFractionalZeros: true, // preenche zeros na fração (ex: 10 -> 10,00)
      normalizeZeros: true,
      radix: ',', // separador decimal
      mapToRadix: ['.'], // aceita ponto como vírgula
    });
  }
}

// (Opcional) Função para aplicar máscara de porcentagem
function aplicarMascaraPorcentagem(idInput) {
  var elemento = document.getElementById(idInput);
  if (elemento) {
    IMask(elemento, {
      mask: Number,
      scale: 2,
      signed: false,
      thousandsSeparator: '',
      padFractionalZeros: true,
      normalizeZeros: true,
      radix: ',',
      mapToRadix: ['.'],
      min: 0,
      max: 100,
    });
  }
}

// (Opcional) Função para aplicar máscara de número inteiro (sem casas decimais)
function aplicarMascaraNumeroInteiro(idInput) {
  var elemento = document.getElementById(idInput);
  if (elemento) {
    IMask(elemento, {
      mask: Number,
      scale: 0, // sem casas decimais
      signed: false,
      thousandsSeparator: '.',
      radix: ',',
      mapToRadix: ['.'],
    });
  }
}
/////////////////////////////////////////////
