(() => {

  // ============================================================
  // GRÁFICO DE RECEITAS / DESPESAS / SALDO
  // ============================================================

  // Lê os tokens de cor direto do theme.css, para o gráfico nunca
  // dessincronizar da paleta usada no resto da interface.
  function corToken(nomeVar, fallback) {
    const valor = getComputedStyle(document.documentElement)
      .getPropertyValue(nomeVar)
      .trim();

    return valor || fallback;
  }

  function criarGraficoReceitasDespesas(
    idCanvas,
    totalReceitas,
    totalDespesas,
    totalSaldo,
  ) {
    const canvas = document.getElementById(idCanvas);

    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    const corPrimaria = corToken(
      "--color-primary-600",
      "#6c4cf1"
    );

    const corPrimariaClara = corToken(
      "--color-primary-300",
      "#c4b5fd"
    );

    const corDanger = corToken(
      "--color-danger",
      "#df4a55"
    );

    const corDangerSubtle = corToken(
      "--color-danger-subtle",
      "#fef2f2"
    );

    const corSuccess = corToken(
      "--color-success",
      "#159b67"
    );

    const corSuccessSubtle = corToken(
      "--color-success-subtle",
      "#ecfdf5"
    );


    // Gradiente Receitas
    const gradientReceitas =
      ctx.createLinearGradient(0, 0, 0, 200);

    gradientReceitas.addColorStop(
      0,
      corPrimaria
    );

    gradientReceitas.addColorStop(
      1,
      corPrimariaClara
    );


    // Gradiente Despesas
    const gradientDespesas =
      ctx.createLinearGradient(0, 0, 0, 200);

    gradientDespesas.addColorStop(
      0,
      corDanger
    );

    gradientDespesas.addColorStop(
      1,
      corDangerSubtle
    );


    // Gradiente Saldo
    const gradientSaldo =
      ctx.createLinearGradient(0, 0, 0, 200);

    gradientSaldo.addColorStop(
      0,
      corSuccess
    );

    gradientSaldo.addColorStop(
      1,
      corSuccessSubtle
    );


    if (window.graficoReceitasDespesasInstance) {
      window.graficoReceitasDespesasInstance.destroy();
    }


    window.graficoReceitasDespesasInstance =
      new Chart(ctx, {

        type: "bar",

        data: {

          labels: [
            "Receitas",
            "Despesas",
            "Saldo"
          ],

          datasets: [

            {
              label: "Valor (R$)",

              data: [
                totalReceitas || 0,
                totalDespesas || 0,
                totalSaldo || 0
              ],

              backgroundColor: [
                gradientReceitas,
                gradientDespesas,
                gradientSaldo,
              ],

              borderRadius: 6,

              barThickness: 40,
            },

          ],
        },

        options: {

          animation: {
            duration: 1000,
            easing: "easeOutQuart"
          },

          responsive: true,

          maintainAspectRatio: false,

          plugins: {

            legend: {
              display: false
            },

            tooltip: {

              backgroundColor: "#fff",

              titleColor: "#000",

              bodyColor: "#000",

              borderColor: "#ccc",

              borderWidth: 1,

              callbacks: {

                label: function (context) {

                  return (
                    "R$ " +
                    context.raw.toLocaleString(
                      "pt-BR",
                      {
                        minimumFractionDigits: 2,
                      }
                    )
                  );

                },

              },

            },

          },

          scales: {

            x: {

              grid: {
                display: false
              },

              ticks: {
                color: "#444",
                font: {
                  size: 14
                }
              },

            },

            y: {

              grid: {
                color: "#eee",
                drawBorder: false
              },

              ticks: {

                color: "#555",

                font: {
                  size: 13
                },

                callback: function (value) {

                  return (
                    "R$ " +
                    value.toLocaleString("pt-BR")
                  );

                },

              },

            },

          },

        },

      });

  }


  // ============================================================
  // INICIALIZAÇÃO PRINCIPAL
  // ============================================================

  document.addEventListener(
    "DOMContentLoaded",
    () => {


      // ========================================================
      // DATA PADRÃO
      // ========================================================

      const dataInput =
        document.getElementById("data");

      if (
        dataInput &&
        typeof setHoje === "function"
      ) {

        setHoje(dataInput);

      } else if (dataInput) {

        dataInput.value =
          new Date()
            .toISOString()
            .split("T")[0];

      }


      // ========================================================
      // FILTRO DE CATEGORIAS E RECORRÊNCIA
      // ========================================================

      const radiosTipo =
        document.querySelectorAll(
          'input[name="tipo_lancamento"]'
        );

      const categoriaSelect =
        document.getElementById("categoria_id");

      const tituloRecorrente =
        document.getElementById(
          "tituloRecorrente"
        );

      const textoRecorrente =
        document.getElementById(
          "textoRecorrente"
        );

      const secaoRecorrente =
        document.getElementById(
          "recorrenteSectionContaAvulsa"
        );


      function filtrarCategorias(tipoSelecionado) {

        if (!categoriaSelect) return;

        const options =
          categoriaSelect.querySelectorAll(
            "option:not([disabled])"
          );

        options.forEach((opt) => {

          const tipoOpt =
            opt.getAttribute("data-tipo");

          if (tipoOpt === tipoSelecionado) {

            opt.style.display = "";

          } else {

            opt.style.display = "";

            opt.style.display = "none";

            if (opt.selected) {
              categoriaSelect.value = "";
            }

          }

        });

      }


      function ajustarTextosRecorrencia(
        tipoSelecionado
      ) {

        if (
          !secaoRecorrente ||
          !tituloRecorrente ||
          !textoRecorrente
        ) {
          return;
        }

        secaoRecorrente.style.display = "block";


        if (tipoSelecionado === "receita") {

          tituloRecorrente.innerHTML =
            '<i class="bi bi-arrow-repeat me-1 text-success"></i> Receita Recorrente?';

          textoRecorrente.innerHTML =
            "Ideal para entradas fixas como Salários e Rendimentos.<br>" +
            "O sistema clonará o lançamento para os meses seguintes.";

        } else {

          tituloRecorrente.innerHTML =
            '<i class="bi bi-arrow-repeat me-1 text-danger"></i> Conta Recorrente?';

          textoRecorrente.innerHTML =
            "Ideal para contas fixas como Internet, Telefone ou Assinaturas. " +
            "O sistema clonará o lançamento para os meses seguintes.";

        }

      }


      radiosTipo.forEach((radio) => {

        radio.addEventListener(
          "change",
          (e) => {

            filtrarCategorias(
              e.target.value
            );

            ajustarTextosRecorrencia(
              e.target.value
            );

          }
        );

      });


      // Estado inicial
      if (radiosTipo.length > 0) {

        const radioAtivo =
          document.querySelector(
            'input[name="tipo_lancamento"]:checked'
          );

        if (radioAtivo) {

          filtrarCategorias(
            radioAtivo.value
          );

          ajustarTextosRecorrencia(
            radioAtivo.value
          );

        }

      }


      // ========================================================
      // SALDO DA CONTA
      // ========================================================

      const contaSelect =
        document.getElementById("conta_id");

      if (contaSelect) {

        contaSelect.addEventListener(
          "change",
          function () {

            const saldoContaContainer =
              document.getElementById(
                "saldoContaContainer"
              );

            const saldoConta =
              document.getElementById(
                "saldoConta"
              );

            const selectedOption =
              this.options[
                this.selectedIndex
              ];


            if (
              selectedOption &&
              this.value !== ""
            ) {

              const saldo =
                selectedOption.getAttribute(
                  "data-saldo"
                );

              saldoConta.innerHTML =
                "Saldo: R$ " +
                parseFloat(saldo)
                  .toLocaleString(
                    "pt-BR",
                    {
                      minimumFractionDigits: 2,
                    }
                  );

              saldoContaContainer.style.display =
                "block";

            } else {

              saldoContaContainer.style.display =
                "none";

            }

          }
        );

      }


      // ========================================================
      // GRÁFICO
      // ========================================================

      const canvas =
        document.getElementById(
          "graficoReceitasDespesas"
        );

      if (canvas) {

        const totalReceitas =
          parseFloat(
            canvas.dataset.receitas
          ) || 0;

        const totalDespesas =
          parseFloat(
            canvas.dataset.despesas
          ) || 0;

        const totalSaldo =
          parseFloat(
            canvas.dataset.saldo
          ) || 0;


        criarGraficoReceitasDespesas(
          "graficoReceitasDespesas",
          totalReceitas,
          totalDespesas,
          totalSaldo
        );

      }


      // ========================================================
      // EDITAR MOVIMENTAÇÃO
      // ========================================================

      document
        .querySelectorAll(".btn-editar")
        .forEach((botao) => {

          botao.addEventListener(
            "click",
            async () => {

              const id =
                botao.dataset.id;


              const response =
                await fetch(
                  `/movimentacoes/${id}/json`
                );


              if (!response.ok) {

                alert(
                  "Erro ao carregar movimentação"
                );

                return;

              }


              const mov =
                await response.json();


              const optTarget =
                document.querySelector(
                  `select[name="categoria_id"] option[value="${mov.categoria_id}"]`
                );


              if (optTarget) {

                const tipo =
                  optTarget.getAttribute(
                    "data-tipo"
                  );


                if (tipo === "receita") {

                  document.getElementById(
                    "tipo_receita"
                  ).checked = true;

                } else {

                  document.getElementById(
                    "tipo_despesa"
                  ).checked = true;

                }


                filtrarCategorias(tipo);

                ajustarTextosRecorrencia(
                  tipo
                );

              }


              // Preenche os campos

              document.getElementById(
                "data"
              ).value = mov.data;


              document.querySelector(
                'input[name="descricao"]'
              ).value = mov.descricao;


              document.querySelector(
                'select[name="categoria_id"]'
              ).value =
                mov.categoria_id;


              document.querySelector(
                'input[name="valor"]'
              ).value = mov.valor;


              document.querySelector(
                'select[name="conta_id"]'
              ).value = mov.conta_id;


              document.querySelector(
                'select[name="pago"]'
              ).value =
                mov.pago
                  ? "true"
                  : "false";


              // Atualiza saldo
              document
                .getElementById("conta_id")
                .dispatchEvent(
                  new Event("change")
                );


              // Altera formulário para edição

              const form =
                document.querySelector(
                  "#modalMovimentacaoConta form"
                );


              form.action =
                `/movimentacoes/${id}/editar`;


              document.getElementById(
                "modalMovimentacaoContaLabel"
              ).textContent =
                "Editar Movimentação";


              form.querySelector(
                'button[type="submit"]'
              ).innerText =
                "Atualizar";


              // Abre modal

              const modal =
                new bootstrap.Modal(
                  document.getElementById(
                    "modalMovimentacaoConta"
                  )
                );

              modal.show();

            }
          );

        });


      // ========================================================
      // RESET DO MODAL
      // ========================================================

      const modalMovimentacao =
        document.getElementById(
          "modalMovimentacaoConta"
        );

      if (modalMovimentacao) {

        modalMovimentacao.addEventListener(
          "hidden.bs.modal",
          () => {

            const form =
              document.querySelector(
                "#modalMovimentacaoConta form"
              );

            if (!form) return;


            form.reset();

            form.action =
              "/movimentacoes/nova";


            document.getElementById(
              "modalMovimentacaoContaLabel"
            ).textContent =
              "Nova Movimentação";


            const submit =
              form.querySelector(
                'button[type="submit"]'
              );

            if (submit) {
              submit.innerText =
                "Salvar";
            }


            // Esconde saldo

            const saldoContainer =
              document.getElementById(
                "saldoContaContainer"
              );

            if (saldoContainer) {
              saldoContainer.style.display =
                "none";
            }


            // Reseta para Despesa

            const tipoDespesa =
              document.getElementById(
                "tipo_despesa"
              );

            if (tipoDespesa) {
              tipoDespesa.checked = true;
            }


            filtrarCategorias("despesa");

            ajustarTextosRecorrencia(
              "despesa"
            );

          }
        );

      }

    }
  );


  window.criarGraficoReceitasDespesas =
    criarGraficoReceitasDespesas;

})();


// ============================================================
// CONFIRMAÇÃO DE EXCLUSÃO
// ============================================================

document.addEventListener(
  "DOMContentLoaded",
  () => {

    aplicarConfirmacaoExclusao(
      ".btn-excluir",
      (id) =>
        `/movimentacoes/${id}/excluir`
    );

  }
);


// ============================================================
// PESQUISA E PAGINAÇÃO — MOVIMENTAÇÕES
// ============================================================

document.addEventListener(
  "DOMContentLoaded",
  () => {

    const tabela =
      document.getElementById(
        "tabelaMovimentacoes"
      );

    const campoPesquisa =
      document.getElementById(
        "movimentacoes-table-search"
      );

    const contador =
      document.getElementById(
        "movimentacoes-table-count"
      );

    const paginacao =
      document.getElementById(
        "movimentacoes-pagination"
      );

    const pageSizeSelect =
      document.getElementById(
        "movimentacoes-page-size"
      );


    if (
      !tabela ||
      !campoPesquisa ||
      !contador ||
      !paginacao
    ) {
      return;
    }


    const linhas =
      Array.from(
        tabela.querySelectorAll(
          "tbody tr"
        )
      );


    let tamanhoPagina =
      parseInt(
        pageSizeSelect?.value || "10",
        10
      );

    let paginaAtual = 1;


    function obterLinhasFiltradas() {

      const pesquisa =
        campoPesquisa.value
          .trim()
          .toLowerCase();


      if (!pesquisa) {
        return linhas;
      }


      return linhas.filter(
        (linha) =>
          linha.textContent
            .trim()
            .toLowerCase()
            .includes(pesquisa)
      );

    }


    function criarBotaoPagina(
      texto,
      pagina,
      ativo = false,
      ariaLabel = ""
    ) {

      const botao =
        document.createElement(
          "button"
        );


      botao.type = "button";


      botao.className =
        `movimentacoes-pagination__button${
          ativo ? " active" : ""
        }`;


      botao.textContent = texto;


      if (ariaLabel) {

        botao.setAttribute(
          "aria-label",
          ariaLabel
        );

      }


      botao.addEventListener(
        "click",
        () => {

          paginaAtual = pagina;

          atualizarTabela();

        }
      );


      return botao;

    }


    function atualizarPaginacao(
      totalPaginas
    ) {

      paginacao.innerHTML = "";


      if (totalPaginas <= 1) {
        return;
      }


      if (paginaAtual > 1) {

        paginacao.appendChild(
          criarBotaoPagina(
            "‹",
            paginaAtual - 1,
            false,
            "Página anterior"
          )
        );

      }


      for (
        let numero = 1;
        numero <= totalPaginas;
        numero += 1
      ) {

        paginacao.appendChild(
          criarBotaoPagina(
            numero,
            numero,
            numero === paginaAtual
          )
        );

      }


      if (paginaAtual < totalPaginas) {

        paginacao.appendChild(
          criarBotaoPagina(
            "›",
            paginaAtual + 1,
            false,
            "Próxima página"
          )
        );

      }

    }


    function atualizarTabela() {

      const linhasFiltradas =
        obterLinhasFiltradas();


      const total =
        linhasFiltradas.length;


      const totalPaginas =
        Math.max(
          1,
          Math.ceil(
            total / tamanhoPagina
          )
        );


      if (
        paginaAtual > totalPaginas
      ) {

        paginaAtual =
          totalPaginas;

      }


      linhas.forEach(
        (linha) => {
          linha.style.display =
            "none";
        }
      );


      const inicio =
        (paginaAtual - 1) *
        tamanhoPagina;


      const fim =
        Math.min(
          inicio + tamanhoPagina,
          total
        );


      linhasFiltradas
        .slice(inicio, fim)
        .forEach(
          (linha) => {
            linha.style.display =
              "";
          }
        );


      if (total === 0) {

        contador.textContent =
          "Nenhuma movimentação encontrada";

      } else {

        contador.textContent =
          `Mostrando ${inicio + 1} a ${fim} de ${total} movimentações`;

      }


      atualizarPaginacao(
        totalPaginas
      );

    }


    campoPesquisa.addEventListener(
      "input",
      () => {

        paginaAtual = 1;

        atualizarTabela();

      }
    );


    pageSizeSelect?.addEventListener(
      "change",
      () => {

        tamanhoPagina =
          parseInt(
            pageSizeSelect.value,
            10
          );

        paginaAtual = 1;

        atualizarTabela();

      }
    );


    atualizarTabela();

  }
);


// ============================================================
// PESQUISA E PAGINAÇÃO — TRANSFERÊNCIAS
// ============================================================

document.addEventListener(
  "DOMContentLoaded",
  () => {

    const tabela =
      document.getElementById(
        "tabelaTransferencias"
      );

    const campoPesquisa =
      document.getElementById(
        "movimentacoes-table-search"
      );

    const contador =
      document.getElementById(
        "transferencias-table-count"
      );

    const paginacao =
      document.getElementById(
        "transferencias-pagination"
      );

    const pageSizeSelect =
      document.getElementById(
        "transferencias-page-size"
      );


    if (
      !tabela ||
      !campoPesquisa ||
      !contador ||
      !paginacao
    ) {
      return;
    }


    const linhas =
      Array.from(
        tabela.querySelectorAll(
          "tbody tr"
        )
      );


    let tamanhoPagina =
      parseInt(
        pageSizeSelect?.value || "10",
        10
      );

    let paginaAtual = 1;


    function obterLinhasFiltradas() {

      const pesquisa =
        campoPesquisa.value
          .trim()
          .toLowerCase();


      if (!pesquisa) {
        return linhas;
      }


      return linhas.filter(
        (linha) =>
          linha.textContent
            .trim()
            .toLowerCase()
            .includes(pesquisa)
      );

    }


    function criarBotaoPagina(
      texto,
      pagina,
      ativo = false,
      ariaLabel = ""
    ) {

      const botao =
        document.createElement(
          "button"
        );


      botao.type = "button";


      botao.className =
        `movimentacoes-pagination__button${
          ativo ? " active" : ""
        }`;


      botao.textContent = texto;


      if (ariaLabel) {

        botao.setAttribute(
          "aria-label",
          ariaLabel
        );

      }


      botao.addEventListener(
        "click",
        () => {

          paginaAtual = pagina;

          atualizarTabela();

        }
      );


      return botao;

    }


    function atualizarPaginacao(
      totalPaginas
    ) {

      paginacao.innerHTML = "";


      if (totalPaginas <= 1) {
        return;
      }


      if (paginaAtual > 1) {

        paginacao.appendChild(
          criarBotaoPagina(
            "‹",
            paginaAtual - 1,
            false,
            "Página anterior"
          )
        );

      }


      for (
        let numero = 1;
        numero <= totalPaginas;
        numero += 1
      ) {

        paginacao.appendChild(
          criarBotaoPagina(
            numero,
            numero,
            numero === paginaAtual
          )
        );

      }


      if (paginaAtual < totalPaginas) {

        paginacao.appendChild(
          criarBotaoPagina(
            "›",
            paginaAtual + 1,
            false,
            "Próxima página"
          )
        );

      }

    }


    function atualizarTabela() {

      const linhasFiltradas =
        obterLinhasFiltradas();


      const total =
        linhasFiltradas.length;


      const totalPaginas =
        Math.max(
          1,
          Math.ceil(
            total / tamanhoPagina
          )
        );


      if (
        paginaAtual > totalPaginas
      ) {

        paginaAtual =
          totalPaginas;

      }


      linhas.forEach(
        (linha) => {
          linha.style.display =
            "none";
        }
      );


      const inicio =
        (paginaAtual - 1) *
        tamanhoPagina;


      const fim =
        Math.min(
          inicio + tamanhoPagina,
          total
        );


      linhasFiltradas
        .slice(inicio, fim)
        .forEach(
          (linha) => {
            linha.style.display =
              "";
          }
        );


      if (total === 0) {

        contador.textContent =
          "Nenhuma transferência encontrada";

      } else {

        contador.textContent =
          `Mostrando ${inicio + 1} a ${fim} de ${total} transferências`;

      }


      atualizarPaginacao(
        totalPaginas
      );

    }


    campoPesquisa.addEventListener(
      "input",
      () => {

        paginaAtual = 1;

        atualizarTabela();

      }
    );


    pageSizeSelect?.addEventListener(
      "change",
      () => {

        tamanhoPagina =
          parseInt(
            pageSizeSelect.value,
            10
          );

        paginaAtual = 1;

        atualizarTabela();

      }
    );


    atualizarTabela();

  }
);


// ============================================================
// ABAS + BOTÕES DE AÇÃO
// ============================================================

document.addEventListener(
  "DOMContentLoaded",
  () => {

    const entradasTab =
      document.getElementById(
        "entradas-tab"
      );

    const transferenciasTab =
      document.getElementById(
        "transferencias-tab"
      );

    const btnMov =
      document.getElementById(
        "btn-nova-movimentacao"
      );

    const btnTransf =
      document.getElementById(
        "btn-nova-transferencia"
      );


    if (
      !entradasTab ||
      !transferenciasTab ||
      !btnMov ||
      !btnTransf
    ) {
      return;
    }


    // --------------------------------------------------------
    // Entradas e Saídas
    // --------------------------------------------------------

    entradasTab.addEventListener(
      "shown.bs.tab",
      () => {

        btnMov.classList.remove(
          "d-none"
        );

        btnTransf.classList.add(
          "d-none"
        );

      }
    );


    // --------------------------------------------------------
    // Transferências
    // --------------------------------------------------------

    transferenciasTab.addEventListener(
      "shown.bs.tab",
      () => {

        btnMov.classList.add(
          "d-none"
        );

        btnTransf.classList.remove(
          "d-none"
        );

      }
    );


    // --------------------------------------------------------
    // Estado inicial
    //
    // Necessário quando a página é aberta diretamente com:
    // ?aba=transferencias
    //
    // Nesse caso não existe clique na aba para disparar
    // "shown.bs.tab".
    // --------------------------------------------------------

    if (
      transferenciasTab.classList.contains(
        "active"
      )
    ) {

      btnMov.classList.add(
        "d-none"
      );

      btnTransf.classList.remove(
        "d-none"
      );

    }

  }
);


// ============================================================
// OCULTAR / EXIBIR SALDOS
// ============================================================

document.addEventListener(
  "DOMContentLoaded",
  () => {

    const btnToggleSaldos =
      document.getElementById(
        "btn-toggle-saldos"
      );

    const valoresSigilosos =
      document.querySelectorAll(
        ".valor-sigiloso"
      );


    if (
      !btnToggleSaldos ||
      !valoresSigilosos.length
    ) {
      return;
    }


    btnToggleSaldos.addEventListener(
      "click",
      () => {

        const oculto =
          btnToggleSaldos.getAttribute(
            "aria-pressed"
          ) === "true";


        const icone =
          btnToggleSaldos.querySelector(
            "i"
          );


        valoresSigilosos.forEach(
          (el) => {

            el.textContent =
              oculto
                ? el.dataset.valor
                : "R$ ••••••";

          }
        );


        btnToggleSaldos.setAttribute(
          "aria-pressed",
          String(!oculto)
        );


        if (icone) {

          icone.classList.toggle(
            "bi-eye",
            oculto
          );

          icone.classList.toggle(
            "bi-eye-slash",
            !oculto
          );

        }

      }
    );

  }
);


// ============================================================
// MOSTRAR / OCULTAR CONTAS ZERADAS
// ============================================================

document.addEventListener(
  "DOMContentLoaded",
  () => {

    const btnToggleContasZeradas =
      document.getElementById(
        "btn-toggle-contas-zeradas"
      );


    const listaContasZeradas =
      document.getElementById(
        "balance-zero-list"
      );


    if (
      !btnToggleContasZeradas ||
      !listaContasZeradas
    ) {
      return;
    }


    btnToggleContasZeradas.addEventListener(
      "click",
      () => {

        const estaAberto =
          btnToggleContasZeradas.getAttribute(
            "aria-expanded"
          ) === "true";


        listaContasZeradas.classList.toggle(
          "d-none"
        );


        btnToggleContasZeradas.setAttribute(
          "aria-expanded",
          String(!estaAberto)
        );


        const texto =
          btnToggleContasZeradas.querySelector(
            "span"
          );


        const icone =
          btnToggleContasZeradas.querySelector(
            "i"
          );


        if (!estaAberto) {

          if (texto) {
            texto.textContent =
              "Ocultar contas zeradas";
          }


          if (icone) {

            icone.classList.remove(
              "bi-chevron-down"
            );

            icone.classList.add(
              "bi-chevron-up"
            );

          }

        } else {

          if (texto) {
            texto.textContent =
              "Mostrar contas zeradas";
          }


          if (icone) {

            icone.classList.remove(
              "bi-chevron-up"
            );

            icone.classList.add(
              "bi-chevron-down"
            );

          }

        }

      }
    );

  }
);  