/**
 * O painel que aparece na página da vaga, e o que ele faz.
 *
 * Roda quando a pessoa clica em "Preencher esta página" na PathR Extension —
 * nunca antes. A extensão não fica lendo tudo o que se navega: sem o clique,
 * nada disto é injetado.
 *
 * ## A ordem das coisas
 *
 * 1. pede ao serviço de fundo o que o PathR já sabe (banco de respostas + perfil);
 * 2. lê o formulário e monta o plano (`campos.js`);
 * 3. preenche o que dá, anexa o currículo se houver campo de arquivo;
 * 4. mostra: o que preencheu, de onde veio cada valor, e o que ficou faltando;
 * 5. o que faltou vira campo de resposta ali mesmo — respondeu, vai para o banco
 *    e preenche na hora; da próxima vez, em qualquer site, a extensão já sabe.
 *
 * O botão de enviar do site continua sendo do site. A extensão nunca o aperta:
 * conferir antes de mandar currículo para uma empresa é da pessoa.
 *
 * ## Um script por quadro, um painel só
 *
 * Formulário de vaga mora dentro de `<iframe>` mais vezes do que não — o site
 * da empresa por fora, o Greenhouse ou o Lever por dentro. Por isso este script
 * entra em TODOS os quadros: cada um lê e preenche o que tem. Mas painel é um
 * só, no quadro de cima; os de dentro mandam para ele o que fizeram e o que não
 * souberam. Sem isso, ou a extensão ignora o formulário (que está no iframe),
 * ou desenha um painel dentro de cada quadro, empilhados.
 *
 * ## Shadow DOM
 *
 * O painel vive num shadow root. Sem isso, um `div { display: flex !important }`
 * de qualquer site desmonta o painel — e ao contrário, o CSS do painel vazaria
 * para o formulário que estamos tentando preencher.
 */

(async () => {
  const NO_TOPO = window.top === window.self;
  const Campos = window.PathRCampos;

  const pedir = (mensagem) =>
    new Promise((resolve) => chrome.runtime.sendMessage(mensagem, (resposta) => resolve(resposta || {})));

  /** Sem os nós do DOM: só isto atravessa a fronteira entre quadros. */
  const semDom = (itens) =>
    itens.map(({ rotulo, chave, valor, origem, tipo, motivo }) => ({
      rotulo,
      chave,
      valor,
      origem,
      tipo,
      motivo,
    }));

  // -----------------------------------------------------------------------
  // O que o PathR sabe, e o primeiro preenchimento
  // -----------------------------------------------------------------------

  const resposta = await pedir({ tipo: "dados" });
  if (!resposta.ok) {
    if (NO_TOPO) desenharErro(resposta);
    return;
  }

  const dados = resposta.dados;
  let plano = Campos.analisar(dados);

  let curriculo = null;
  if (plano.preenchiveis.some((item) => item.tipo === "file")) {
    const baixado = await pedir({ tipo: "curriculo" });
    if (baixado.ok) curriculo = baixado.curriculo;
  }

  let resultado = await Campos.preencher(plano.preenchiveis, curriculo);

  // -----------------------------------------------------------------------
  // Quadro de dentro: preenche, conta para o de cima e fica ouvindo
  // -----------------------------------------------------------------------

  if (!NO_TOPO) {
    if (plano.total > 0) {
      pedir({
        tipo: "quadro",
        carga: {
          feitos: semDom(resultado.feitos),
          falhas: semDom(resultado.falhas),
          pendentes: plano.pendentes,
          total: plano.total,
        },
      });
    }
    chrome.runtime.onMessage.addListener((mensagem, _remetente, responder) => {
      if (mensagem?.tipo !== "repreencher") return undefined;
      repreencher(mensagem.respostas || {}).then((feitos) =>
        responder({ ok: true, feitos: semDom(feitos) }),
      );
      return true;
    });
    return;
  }

  /** Preenche de novo, só as perguntas que acabaram de ganhar resposta. */
  async function repreencher(novas) {
    const novoPlano = Campos.analisar({ ...dados, respostas: { ...dados.respostas, ...novas } });
    const alvo = novoPlano.preenchiveis.filter((item) => item.chave in novas);
    if (!alvo.length) return [];
    const feito = await Campos.preencher(alvo, curriculo);
    plano = novoPlano;
    return feito.feitos;
  }

  // -----------------------------------------------------------------------
  // Quadro de cima: o painel
  // -----------------------------------------------------------------------

  const JA_ABERTO = "pathr-extension-painel";
  document.getElementById(JA_ABERTO)?.remove();

  const hospedeiro = document.createElement("div");
  hospedeiro.id = JA_ABERTO;
  // `all: initial` e z-index no teto: o painel precisa ficar por cima de modal
  // de site e não pode herdar nada de fora.
  // Canto inferior direito, longe do botão de enviar da maioria dos formulários.
  hospedeiro.style.cssText =
    "all: initial; position: fixed; right: 20px; bottom: 20px; z-index: 2147483647;";
  const sombra = hospedeiro.attachShadow({ mode: "open" });
  document.documentElement.appendChild(hospedeiro);

  const folha = document.createElement("link");
  folha.rel = "stylesheet";
  folha.href = chrome.runtime.getURL("src/painel.css");
  sombra.appendChild(folha);

  const painel = document.createElement("div");
  painel.className = "painel";
  sombra.appendChild(painel);

  // O que os quadros de dentro relataram, somado ao daqui.
  const deQuadros = { feitos: [], falhas: [], pendentes: [], total: 0 };
  chrome.runtime.onMessage.addListener((mensagem) => {
    if (mensagem?.tipo !== "quadro") return undefined;
    const carga = mensagem.carga || {};
    deQuadros.feitos.push(...(carga.feitos || []));
    deQuadros.falhas.push(...(carga.falhas || []));
    deQuadros.pendentes.push(...(carga.pendentes || []));
    deQuadros.total += carga.total || 0;
    desenhar();
    return undefined;
  });

  desenhar();

  function criar(tag, classe, texto) {
    const elemento = document.createElement(tag);
    if (classe) elemento.className = classe;
    if (texto != null) elemento.textContent = texto;
    return elemento;
  }

  function moldura() {
    painel.textContent = "";
    const topo = criar("header", "topo");
    const marca = criar("div", "marca");
    const icone = criar("img", "icone");
    icone.src = chrome.runtime.getURL("icones/icone-48.png");
    icone.alt = "";
    marca.append(icone, criar("span", "nome", "PathR Extension"));
    const fechar = criar("button", "fechar", "×");
    fechar.title = "Fechar";
    fechar.setAttribute("aria-label", "Fechar");
    fechar.addEventListener("click", () => hospedeiro.remove());
    topo.append(marca, fechar);
    painel.appendChild(topo);
    const corpo = criar("div", "corpo");
    painel.appendChild(corpo);
    return corpo;
  }

  function desenharErro(falha) {
    const corpo = moldura();
    const bloco = criar("div", "aviso");
    bloco.append(
      criar(
        "p",
        "aviso-titulo",
        falha.erro === "sem-chave" || falha.erro === "chave-invalida"
          ? "Conecte a extensão à sua conta"
          : "Não consegui falar com o PathR",
      ),
    );
    bloco.append(
      criar(
        "p",
        "aviso-detalhe",
        falha.erro === "sem-chave"
          ? "Abra a PathR Extension na barra do navegador e cole a chave que o app mostra em Candidaturas."
          : falha.erro === "chave-invalida"
            ? "Esta chave não vale mais. Crie outra em Candidaturas e cole aqui."
            : falha.detalhe || "Tente de novo em instantes.",
      ),
    );
    corpo.appendChild(bloco);
  }

  function numero(quantos, rotulo) {
    const bloco = criar("div", "numero");
    bloco.append(criar("strong", null, String(quantos)), criar("span", null, rotulo));
    return bloco;
  }

  function listaDe(itens, comEtiqueta) {
    const lista = criar("ul", "lista");
    for (const item of itens) {
      const linha = criar("li", "item");
      linha.append(criar("span", "item-rotulo", item.rotulo));
      linha.append(
        criar(
          "span",
          "item-valor",
          comEtiqueta
            ? item.valor || "arquivo anexado"
            : item.tipo === "file"
              ? "o site não aceitou o arquivo por aqui — anexe à mão"
              : "campo fora do comum; preencha à mão",
        ),
      );
      if (comEtiqueta) {
        linha.append(
          criar("span", "etiqueta", item.origem === "banco" ? "você já respondeu" : "do seu perfil"),
        );
      }
      lista.appendChild(linha);
    }
    return lista;
  }

  /** Pendentes daqui e dos quadros, sem repetir a mesma pergunta. */
  function pendentesTodas() {
    const vistas = new Set();
    return [...plano.pendentes, ...deQuadros.pendentes].filter((item) => {
      if (vistas.has(item.chave)) return false;
      vistas.add(item.chave);
      return true;
    });
  }

  function desenhar() {
    const area = moldura();
    const feitos = [...resultado.feitos, ...deQuadros.feitos];
    const falhas = [...resultado.falhas, ...deQuadros.falhas];
    const pendentes = pendentesTodas();
    const total = plano.total + deQuadros.total;

    if (total === 0) {
      const bloco = criar("div", "aviso");
      bloco.append(criar("p", "aviso-titulo", "Nenhum campo nesta página"));
      bloco.append(
        criar(
          "p",
          "aviso-detalhe",
          "Se o formulário abre numa janela ou depois de um botão, abra-o primeiro e clique de novo.",
        ),
      );
      area.appendChild(bloco);
      return;
    }

    const resumo = criar("div", "resumo");
    resumo.append(numero(feitos.length, "preenchidos"));
    resumo.append(numero(pendentes.length, "faltando"));
    if (falhas.length) resumo.append(numero(falhas.length, "não deu"));
    area.appendChild(resumo);

    if (feitos.length) {
      area.appendChild(criar("h2", "titulo", "Preenchi"));
      area.appendChild(listaDe(feitos, true));
    }

    if (falhas.length) {
      area.appendChild(criar("h2", "titulo", "Não consegui preencher"));
      area.appendChild(listaDe(falhas, false));
    }

    if (pendentes.length) {
      area.appendChild(criar("h2", "titulo", "Preciso da sua resposta"));
      area.appendChild(
        criar(
          "p",
          "explicacao",
          "O que você responder aqui fica guardado e serve para as próximas vagas, em qualquer site.",
        ),
      );
      const formulario = criar("form", "perguntas");
      for (const pendente of pendentes) formulario.appendChild(campoDePergunta(pendente));
      const enviar = criar("button", "botao", "Salvar e preencher");
      enviar.type = "submit";
      formulario.appendChild(enviar);
      formulario.addEventListener("submit", (evento) => {
        evento.preventDefault();
        salvar(formulario, enviar);
      });
      area.appendChild(formulario);
    }

    area.appendChild(criar("p", "rodape", "Confira e envie você — a extensão não aperta enviar."));
  }

  /** Um campo para a pergunta que faltou, com o motivo dito na cara. */
  function campoDePergunta(pendente) {
    const bloco = criar("label", "pergunta");
    bloco.append(criar("span", "pergunta-texto", pendente.rotulo));
    const motivo = {
      sensivel: "opcional por lei — só você responde",
      aberta: "muda a cada vaga; escreva para esta",
      escolha: "aceite ou opção: a escolha é sua",
      desconhecida: "ainda não sei esta",
    }[pendente.motivo];
    bloco.append(criar("span", `motivo motivo-${pendente.motivo}`, motivo));
    const entrada = criar(pendente.motivo === "aberta" ? "textarea" : "input", "entrada");
    entrada.dataset.chave = pendente.chave;
    entrada.dataset.rotulo = pendente.rotulo;
    entrada.dataset.motivo = pendente.motivo;
    if (entrada.tagName === "TEXTAREA") entrada.rows = 3;
    bloco.append(entrada);
    return bloco;
  }

  // -----------------------------------------------------------------------
  // O que a pessoa respondeu volta para o banco — e entra no formulário
  // -----------------------------------------------------------------------

  async function salvar(formulario, botao) {
    const respondidas = Array.from(formulario.querySelectorAll(".entrada"))
      .map((entrada) => ({
        pergunta: entrada.dataset.rotulo,
        resposta: entrada.value.trim(),
        chave: entrada.dataset.chave,
        motivo: entrada.dataset.motivo,
      }))
      .filter((item) => item.resposta);
    if (!respondidas.length) return;

    botao.disabled = true;
    botao.textContent = "Salvando…";

    // Sensível e aberta NÃO vão para o banco — o servidor também recusa, mas
    // mandar e deixar ele filtrar seria mandar o dado à toa.
    const guardaveis = respondidas.filter(
      (item) => item.motivo !== "sensivel" && item.motivo !== "aberta",
    );
    if (guardaveis.length) {
      const salvo = await pedir({
        tipo: "respostas",
        respostas: guardaveis.map(({ pergunta, resposta }) => ({ pergunta, resposta })),
      });
      if (salvo.ok && salvo.respostas) Object.assign(dados.respostas, salvo.respostas);
    }

    // Preenche agora com TUDO o que foi respondido, inclusive o que não se
    // guarda: a pessoa acabou de escrever para esta vaga.
    const novas = Object.fromEntries(respondidas.map((item) => [item.chave, item.resposta]));
    const feitosAqui = await repreencher(novas);

    // E os quadros de dentro: a pergunta pode estar no iframe do formulário.
    const nosQuadros = await pedir({ tipo: "repreencher-quadros", respostas: novas });

    resultado = {
      feitos: [...resultado.feitos, ...feitosAqui],
      falhas: resultado.falhas,
    };
    deQuadros.feitos.push(...(nosQuadros.feitos || []));
    const respondidasChaves = new Set(Object.keys(novas));
    deQuadros.pendentes = deQuadros.pendentes.filter((item) => !respondidasChaves.has(item.chave));
    desenhar();
  }
})();
