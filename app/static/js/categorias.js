// ==========================================================
// CATEGORIAS: filtro de pesquisa
//
// Regras:
// - sem termo: mostra tudo;
// - o termo casa com a categoria principal: mostra ela e TODAS as subcategorias;
// - o termo casa só com subcategorias: mostra as que casam + a principal delas
//   (para o contexto não se perder);
// - categorias desativadas também são filtradas (pelo nome, incluindo a principal).
// A busca ignora maiúsculas/minúsculas e acentos ("saude" acha "Saúde").
// ==========================================================

(function () {
  const campo = document.getElementById('filtroCategorias');

  if (!campo) {
    return;
  }

  const linhas = Array.from(document.querySelectorAll('tr[data-cat-nivel]'));
  const semResultado = document.getElementById('semResultadoCategorias');

  const normalizar = (texto) =>
    (texto || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim();

  const casa = (linha, termo) => normalizar(linha.dataset.catNome).includes(termo);

  function filtrar() {
    const termo = normalizar(campo.value);

    // Agrupa principal + subcategorias pelo id da principal
    const grupos = {};

    linhas.forEach((linha) => {
      const grupo = linha.dataset.catGrupo;

      if (!grupo) {
        return;
      }

      grupos[grupo] = grupos[grupo] || { principal: null, subs: [] };

      if (linha.dataset.catNivel === 'principal') {
        grupos[grupo].principal = linha;
      } else {
        grupos[grupo].subs.push(linha);
      }
    });

    let visiveis = 0;

    Object.values(grupos).forEach(({ principal, subs }) => {
      const principalCasa = !termo || (principal && casa(principal, termo));
      let algumaSubVisivel = false;

      subs.forEach((sub) => {
        const mostrar = principalCasa || casa(sub, termo);
        sub.hidden = !mostrar;
        algumaSubVisivel = algumaSubVisivel || mostrar;
      });

      if (principal) {
        const mostrarPrincipal = principalCasa || algumaSubVisivel;
        principal.hidden = !mostrarPrincipal;
        visiveis += mostrarPrincipal ? 1 : 0;
      }
    });

    // Desativadas
    let desativadasVisiveis = 0;

    linhas
      .filter((linha) => linha.dataset.catNivel === 'desativada')
      .forEach((linha) => {
        const mostrar = !termo || casa(linha, termo);
        linha.hidden = !mostrar;
        desativadasVisiveis += mostrar ? 1 : 0;
      });

    linhas
      .filter((linha) => linha.dataset.catNivel === 'titulo-desativadas')
      .forEach((linha) => {
        linha.hidden = desativadasVisiveis === 0;
      });

    if (semResultado) {
      semResultado.hidden = !termo || visiveis + desativadasVisiveis > 0;
    }
  }

  campo.addEventListener('input', filtrar);
  filtrar();
})();
