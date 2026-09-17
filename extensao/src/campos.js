/**
 * Reconhecer campo de formulário: achar, entender o que pergunta, preencher.
 *
 * ## Por que isto não é um seletor por site
 *
 * A tentação óbvia é ter uma receita por site ("no Gupy o nome é #candidate-name").
 * Isso funciona até o site mudar uma classe, e some no site que ninguém previu —
 * e são milhares. Aqui o caminho é outro: o formulário já diz o que quer, em
 * português ou inglês, no rótulo que a pessoa lê. É esse texto que vira CHAVE,
 * pelas mesmas regras do servidor (`services/perguntas.py`), e é a chave que
 * acha a resposta. Site novo, formulário novo, mesma pergunta: funciona.
 *
 * ## Onde está o rótulo
 *
 * Em sete lugares diferentes, porque formulário de verdade é bagunçado:
 * `aria-labelledby`, `aria-label`, `<label for>`, `<label>` em volta, o texto
 * que vem antes do campo, o `placeholder`, e por último `name`/`id`. A ordem é
 * da fonte mais confiável para a menos — `name="f_12"` é chute, `aria-label` é
 * o que um leitor de tela anuncia.
 *
 * `autocomplete` vem antes de tudo isso quando existe: é padrão da web, é o
 * próprio site dizendo "aqui vai o sobrenome", e não depende de idioma.
 *
 * ## O que NUNCA é preenchido sozinho
 *
 * - **caixa de marcar** (aceite de termos, consentimento de dados): marcar isso
 *   no lugar de alguém é declarar concordância em nome dela;
 * - **pergunta sensível** (gênero, raça, deficiência, idade): é opcional por lei
 *   e a resposta é escolha de quem se candidata;
 * - **pergunta aberta sobre a vaga** ("por que você quer trabalhar aqui?"): a
 *   resposta de ontem, em outra empresa, o recrutador percebe.
 *
 * Nada disso é limitação técnica. É onde a extensão para e devolve a pergunta.
 */

(() => {
  if (window.PathRCampos) return; // injetado de novo na mesma aba

  // ---------------------------------------------------------------------
  // As chaves canônicas — o mesmo mapa de services/perguntas.py
  // ---------------------------------------------------------------------

  const SINONIMOS = {
    nome: ["nome completo", "nome e sobrenome", "full name", "your name", "nombre completo", "nome"],
    primeiro_nome: ["primeiro nome", "first name", "given name", "nome (sem sobrenome)"],
    sobrenome: ["sobrenome", "last name", "family name", "surname", "apelido"],
    email: ["e mail", "email", "correio eletronico", "endereco de e mail"],
    telefone: ["telefone", "celular", "whatsapp", "phone", "mobile", "contato telefonico"],
    endereco: ["endereco", "logradouro", "rua", "address", "street"],
    numero: ["numero", "number", "num"],
    complemento: ["complemento", "apto", "apartamento", "unidade"],
    bairro: ["bairro", "district", "neighborhood"],
    cidade: ["cidade", "municipio", "city", "onde voce mora", "localidade"],
    estado: ["estado", "uf", "state", "provincia"],
    pais: ["pais", "country"],
    cep: ["cep", "codigo postal", "zip", "postal code"],
    linkedin: ["linkedin", "perfil do linkedin"],
    github: ["github", "portfolio de codigo", "repositorio"],
    portfolio: ["portfolio", "site pessoal", "website", "seu site"],
    curriculo: ["curriculo", "curriculum", "cv", "resume", "anexe seu curriculo", "upload do curriculo"],
    carta: ["carta de apresentacao", "cover letter", "carta de motivacao"],
    pretensao: [
      "pretensao salarial", "pretensao", "remuneracao desejada", "salario desejado",
      "salary expectation", "expected salary", "quanto voce espera receber",
    ],
    salario_atual: ["salario atual", "remuneracao atual", "current salary"],
    disponibilidade: [
      "disponibilidade", "quando pode comecar", "aviso previo", "notice period",
      "start date", "data de inicio",
    ],
    modelo_trabalho: ["modelo de trabalho", "remoto", "hibrido", "presencial", "work model", "onsite"],
    ingles: ["ingles", "english level", "nivel de ingles", "fluencia em ingles"],
    outros_idiomas: ["outros idiomas", "idiomas", "languages"],
    experiencia_anos: ["anos de experiencia", "tempo de experiencia", "years of experience"],
    escolaridade: ["escolaridade", "formacao academica", "education", "graduacao"],
    autorizacao: [
      "autorizacao para trabalhar", "work authorization", "visto", "visa",
      "elegivel para trabalhar",
    ],
    mudanca: ["disponibilidade para mudanca", "willing to relocate", "mudar de cidade"],
    referencias: ["referencias", "references"],
    cpf: ["cpf", "documento", "tax id"],
  };

  const SENSIVEIS = {
    genero: ["genero", "gender", "sexo"],
    raca: ["raca", "cor", "etnia", "race", "ethnicity"],
    deficiencia: ["deficiencia", "pcd", "disability", "laudo"],
    orientacao: ["orientacao sexual", "sexual orientation", "lgbt"],
    idade: ["idade", "data de nascimento", "age", "birth date", "birthday"],
  };

  const ABERTAS = [
    "por que", "porque", "why do you", "why are you", "o que te motiva",
    "conte sobre", "descreva", "tell us", "fale sobre", "como voce",
  ];

  /**
   * `autocomplete` → chave canônica. Quando o site preenche este atributo, ele
   * é melhor que qualquer rótulo: é padrão, é explícito e não tem idioma.
   */
  const POR_AUTOCOMPLETE = {
    name: "nome",
    "given-name": "primeiro_nome",
    "family-name": "sobrenome",
    email: "email",
    tel: "telefone",
    "tel-national": "telefone",
    "street-address": "endereco",
    "address-line1": "endereco",
    "address-line2": "complemento",
    "address-level1": "estado",
    "address-level2": "cidade",
    "postal-code": "cep",
    country: "pais",
    "country-name": "pais",
    url: "portfolio",
    organization: "empresa_atual",
    bday: "sensivel:idade",
    sex: "sensivel:genero",
  };

  // ---------------------------------------------------------------------
  // Texto
  // ---------------------------------------------------------------------

  function normalizar(texto) {
    return (texto || "")
      .normalize("NFKD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  /**
   * A forma aparece como PALAVRA INTEIRA na pergunta.
   *
   * Com substring crua, "cidade" contém "idade" e todo campo de cidade virava
   * pergunta sensível; "cor" aparece dentro de "corporativo"; "cv" dentro de
   * "cvs". Fronteira de palavra resolve os três.
   */
  function contem(pergunta, forma) {
    const escapada = forma.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(?<![a-z0-9])${escapada}(?![a-z0-9])`).test(pergunta);
  }

  function eSensivel(pergunta) {
    const limpo = normalizar(pergunta);
    return Object.values(SENSIVEIS).some((formas) => formas.some((f) => contem(limpo, f)));
  }

  function eAberta(pergunta) {
    const limpo = normalizar(pergunta);
    return ABERTAS.some((inicio) => limpo.includes(inicio));
  }

  /**
   * A chave canônica de uma pergunta.
   *
   * "Nome completo", "Nome" e "Full name" saem daqui iguais — é o que faz uma
   * resposta valer para todos os sites. Pergunta desconhecida vira `livre:…`
   * com o próprio texto: também é reaproveitada, mas só quando reaparecer
   * exatamente igual.
   */
  function chave(pergunta) {
    const limpo = normalizar(pergunta);
    if (!limpo) return "";
    for (const [nome, formas] of Object.entries(SENSIVEIS)) {
      if (formas.some((f) => contem(limpo, f))) return `sensivel:${nome}`;
    }
    // Ordem: a forma mais longa primeiro, para "pretensao salarial" ganhar de
    // "pretensao" e "nome completo" não cair em "nome" por acaso de ordem.
    let melhor = null;
    for (const [nome, formas] of Object.entries(SINONIMOS)) {
      for (const forma of formas) {
        if (contem(limpo, forma) && (!melhor || forma.length > melhor.tamanho)) {
          melhor = { nome, tamanho: forma.length };
        }
      }
    }
    if (melhor) return melhor.nome;
    return `livre:${limpo.slice(0, 80)}`;
  }

  // ---------------------------------------------------------------------
  // Achar os campos, inclusive dentro de shadow DOM
  // ---------------------------------------------------------------------

  const SELETOR = [
    "input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=image]):not([type=reset])",
    "textarea",
    "select",
    "[contenteditable=true]",
  ].join(",");

  function visivel(elemento) {
    if (!elemento.isConnected) return false;
    if (elemento.disabled || elemento.readOnly) return false;
    const caixa = elemento.getBoundingClientRect();
    if (caixa.width === 0 && caixa.height === 0) return false;
    const estilo = getComputedStyle(elemento);
    return estilo.visibility !== "hidden" && estilo.display !== "none" && estilo.opacity !== "0";
  }

  /**
   * Varre a página inteira, entrando em shadow DOM aberto.
   *
   * Componentes de formulário modernos (os "web components" de Workday, SAP e
   * afins) escondem o `<input>` real dentro de um shadow root, e um
   * `document.querySelectorAll` comum não vê nada lá dentro — a extensão
   * enxergava zero campo justamente nos sites mais chatos.
   */
  function todosOsCampos(raiz = document) {
    const achados = [];
    const pilha = [raiz];
    while (pilha.length) {
      const atual = pilha.pop();
      let elementos = [];
      try {
        elementos = Array.from(atual.querySelectorAll("*"));
      } catch {
        continue;
      }
      for (const elemento of elementos) {
        if (elemento.matches?.(SELETOR) && visivel(elemento)) achados.push(elemento);
        if (elemento.shadowRoot) pilha.push(elemento.shadowRoot);
      }
    }
    return achados;
  }

  // ---------------------------------------------------------------------
  // O rótulo de um campo
  // ---------------------------------------------------------------------

  function textoDe(elemento) {
    if (!elemento) return "";
    // `innerText` e não `textContent`: o segundo traz o texto de coisas
    // escondidas (dicas, menus fechados) e polui o rótulo.
    return (elemento.innerText || elemento.textContent || "").replace(/\s+/g, " ").trim();
  }

  /** O bloco tem campo próprio dentro dele? Então o texto é dele, não do vizinho. */
  function temCampoDentro(no) {
    return Boolean(no.matches?.(SELETOR) || no.querySelector?.(SELETOR));
  }

  function textoAnterior(campo) {
    // O rótulo "solto" antes do campo, que muitos formulários usam sem <label>.
    let no = campo.previousElementSibling;
    let voltas = 0;
    while (no && voltas < 3) {
      // Vizinho que tem campo dentro é OUTRA pergunta. Sem esta guarda, um
      // <div><span>Cidade</span><input></div> seguido de outro campo empresta
      // "Cidade" para o campo seguinte — e o formulário sai preenchido errado,
      // que é pior do que sair vazio.
      if (!temCampoDentro(no)) {
        const texto = textoDe(no);
        if (texto && texto.length < 160) return texto;
      }
      no = no.previousElementSibling;
      voltas += 1;
    }
    const pai = campo.parentElement;
    // O texto do pai só vale quando ele embrulha UM campo — este. Com dois, o
    // texto é do grupo e casaria com qualquer sinônimo que estiver ali dentro.
    if (pai && pai.querySelectorAll(SELETOR).length === 1) {
      const texto = textoDe(pai);
      if (texto && texto.length < 160) return texto;
    }
    return "";
  }

  /** Tudo o que a página diz sobre este campo, da fonte melhor para a pior. */
  function rotuloDe(campo) {
    const raiz = campo.getRootNode();

    const porIds = (atributo) =>
      (campo.getAttribute(atributo) || "")
        .split(/\s+/)
        .map((id) => textoDe(raiz.getElementById?.(id) || document.getElementById(id)))
        .filter(Boolean)
        .join(" ");

    const candidatos = [
      porIds("aria-labelledby"),
      campo.getAttribute("aria-label"),
      campo.id ? textoDe(raiz.querySelector?.(`label[for="${CSS.escape(campo.id)}"]`)) : "",
      textoDe(campo.closest?.("label")),
      textoDe(campo.closest?.("fieldset")?.querySelector("legend")),
      textoAnterior(campo),
      campo.getAttribute("placeholder"),
      campo.getAttribute("title"),
      // Último recurso: o nome do campo no HTML. "first_name" e "candidateEmail"
      // viram texto legível; "f_12" não vira nada, e tudo bem.
      (campo.getAttribute("name") || campo.id || "").replace(/([a-z])([A-Z])/g, "$1 $2"),
    ];

    for (const candidato of candidatos) {
      const texto = (candidato || "").replace(/\s+/g, " ").trim();
      if (texto && texto.length >= 2) return texto.slice(0, 300);
    }
    return "";
  }

  /** A chave do campo: `autocomplete` manda; o rótulo decide o resto. */
  function chaveDoCampo(campo) {
    const auto = (campo.getAttribute("autocomplete") || "").toLowerCase().trim();
    if (auto && auto !== "off" && auto !== "on") {
      const direto = POR_AUTOCOMPLETE[auto.split(/\s+/).pop()];
      if (direto) return direto;
    }
    if (campo.type === "email") return "email";
    if (campo.type === "tel") return "telefone";
    if (campo.type === "file") {
      const aceita = (campo.getAttribute("accept") || "").toLowerCase();
      const rotulo = normalizar(rotuloDe(campo));
      if (contem(rotulo, "carta") || rotulo.includes("cover letter")) return "carta";
      if (aceita.includes("pdf") || aceita.includes("doc") || !aceita) return "curriculo";
    }
    return chave(rotuloDe(campo));
  }

  // ---------------------------------------------------------------------
  // Preencher
  // ---------------------------------------------------------------------

  /**
   * Escreve no campo de um jeito que o site perceba.
   *
   * `campo.value = x` direto não funciona em React: o React guarda o último
   * valor que ELE escreveu e, vendo o mesmo de volta no evento, conclui que
   * nada mudou — o texto aparece na tela e some no primeiro clique, ou o botão
   * de enviar continua desabilitado. Por isso o setter nativo do protótipo:
   * ele fura o descritor que o React instalou e o `input` que vai depois é
   * aceito como digitação de gente.
   */
  function escrever(campo, valor) {
    const prototipo =
      campo instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototipo, "value")?.set;
    campo.focus();
    if (setter) setter.call(campo, valor);
    else campo.value = valor;
    campo.dispatchEvent(new Event("input", { bubbles: true }));
    campo.dispatchEvent(new Event("change", { bubbles: true }));
    campo.dispatchEvent(new Event("blur", { bubbles: true }));
  }

  function escreverEmEditavel(campo, valor) {
    campo.focus();
    campo.textContent = valor;
    campo.dispatchEvent(new InputEvent("input", { bubbles: true, data: valor }));
    campo.dispatchEvent(new Event("change", { bubbles: true }));
  }

  /**
   * Escolhe a opção de um `<select>` pelo texto.
   *
   * Compara normalizado e aceita opção que CONTENHA a resposta ("São Paulo" na
   * opção "São Paulo - SP"), porque lista de estado e de país nunca vem escrita
   * do mesmo jeito em dois sites.
   */
  function escolherNoSelect(campo, valor) {
    const alvo = normalizar(valor);
    if (!alvo) return false;
    const opcoes = Array.from(campo.options || []);
    const casa =
      opcoes.find((o) => normalizar(o.textContent) === alvo || normalizar(o.value) === alvo) ||
      opcoes.find((o) => {
        const texto = normalizar(o.textContent);
        return texto && (texto.includes(alvo) || alvo.includes(texto));
      });
    if (!casa) return false;
    campo.focus();
    campo.value = casa.value;
    campo.dispatchEvent(new Event("input", { bubbles: true }));
    campo.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  /** Marca a opção de um grupo de rádio cujo rótulo casa com a resposta. */
  function escolherNoRadio(grupo, valor) {
    const alvo = normalizar(valor);
    if (!alvo) return false;
    const casa = grupo.find((opcao) => {
      const texto = normalizar(rotuloDe(opcao) + " " + (opcao.value || ""));
      return texto === alvo || texto.includes(alvo) || alvo.includes(texto);
    });
    if (!casa) return false;
    casa.click(); // click e não `checked = true`: é o clique que dispara o site
    return true;
  }

  /**
   * Anexa um arquivo num `<input type=file>`.
   *
   * Não dá para atribuir `files` — a lista é somente leitura, por segurança:
   * senão qualquer página mandaria seu disco embora. `DataTransfer` é a porta
   * legítima, e ela existe porque o arquivo vem de uma ação da pessoa (o clique
   * que abriu a extensão), não da página.
   */
  function anexar(campo, arquivo) {
    try {
      const pacote = new DataTransfer();
      pacote.items.add(arquivo);
      campo.files = pacote.files;
      campo.dispatchEvent(new Event("input", { bubbles: true }));
      campo.dispatchEvent(new Event("change", { bubbles: true }));
      return campo.files.length > 0;
    } catch {
      return false;
    }
  }

  function arquivoDeBase64(base64, nome, tipo) {
    const binario = atob(base64);
    const bytes = new Uint8Array(binario.length);
    for (let i = 0; i < binario.length; i += 1) bytes[i] = binario.charCodeAt(i);
    return new File([bytes], nome || "curriculo.pdf", { type: tipo || "application/pdf" });
  }

  // ---------------------------------------------------------------------
  // A varredura: o que dá para preencher e o que fica faltando
  // ---------------------------------------------------------------------

  /**
   * Junta os rádios pelo `name`: um grupo é UMA pergunta, não cinco.
   */
  function agruparRadios(campos) {
    const grupos = new Map();
    for (const campo of campos) {
      if (campo.type !== "radio") continue;
      const nome = campo.name || rotuloDe(campo.closest("fieldset") || campo);
      if (!grupos.has(nome)) grupos.set(nome, []);
      grupos.get(nome).push(campo);
    }
    return grupos;
  }

  /**
   * Lê o formulário e devolve o plano: `{preenchiveis, pendentes}`.
   *
   * Nada é escrito aqui. Separar leitura de escrita é o que permite mostrar
   * "vou preencher isto" antes de mexer na página de alguém.
   */
  function analisar(dados) {
    const respostas = dados.respostas || {};
    const perfil = dados.perfil || {};
    const campos = todosOsCampos();
    const grupos = agruparRadios(campos);
    const jaVistas = new Set();
    const preenchiveis = [];
    const pendentes = [];

    const anotar = (campo, rotulo, canonica, tipo) => {
      if (!rotulo) return;
      if (jaVistas.has(canonica)) return; // a mesma pergunta duas vezes na página
      jaVistas.add(canonica);

      if (canonica.startsWith("sensivel:")) {
        pendentes.push({ rotulo, chave: canonica, motivo: "sensivel", tipo });
        return;
      }
      if (eAberta(rotulo)) {
        pendentes.push({ rotulo, chave: canonica, motivo: "aberta", tipo });
        return;
      }
      const valor = respostas[canonica] || perfil[canonica] || "";
      if (!valor) {
        pendentes.push({ rotulo, chave: canonica, motivo: "desconhecida", tipo });
        return;
      }
      preenchiveis.push({
        campo,
        rotulo,
        chave: canonica,
        valor,
        origem: respostas[canonica] ? "banco" : "perfil",
        tipo,
      });
    };

    for (const campo of campos) {
      const rotulo = rotuloDe(campo);
      const canonica = chaveDoCampo(campo);
      if (!canonica) continue;

      if (campo.type === "checkbox") {
        // Aceite de termos, consentimento de dados, "concordo com": marcar isso
        // por alguém é declarar concordância no lugar dela. Fica pendente.
        if (!jaVistas.has(canonica) && rotulo) {
          jaVistas.add(canonica);
          pendentes.push({ rotulo, chave: canonica, motivo: "escolha", tipo: "checkbox" });
        }
        continue;
      }
      if (campo.type === "radio") continue; // tratado pelo grupo, abaixo
      if (campo.type === "file") {
        preenchiveis.push({ campo, rotulo, chave: canonica, valor: "", origem: "arquivo", tipo: "file" });
        continue;
      }
      anotar(campo, rotulo, canonica, campo.tagName === "SELECT" ? "select" : "texto");
    }

    for (const [, grupo] of grupos) {
      const referencia = grupo[0];
      const rotulo =
        textoDe(referencia.closest("fieldset")?.querySelector("legend")) ||
        rotuloDe(referencia.closest("[role=radiogroup]") || referencia);
      anotar(grupo, rotulo, chave(rotulo), "radio");
    }

    return { preenchiveis, pendentes, total: campos.length };
  }

  /** Executa o plano. Devolve o que realmente entrou na página. */
  async function preencher(plano, curriculo) {
    const feitos = [];
    const falhas = [];

    for (const item of plano) {
      const { campo, tipo } = item;
      let ok = false;
      try {
        if (tipo === "file") {
          if (!curriculo || item.chave !== "curriculo") continue;
          ok = anexar(campo, arquivoDeBase64(curriculo.base64, curriculo.nome, curriculo.tipo));
          if (ok) item.valor = curriculo.nome;
        } else if (tipo === "radio") {
          ok = escolherNoRadio(campo, item.valor);
        } else if (tipo === "select") {
          ok = escolherNoSelect(campo, item.valor);
        } else if (campo.isContentEditable) {
          escreverEmEditavel(campo, item.valor);
          ok = true;
        } else {
          escrever(campo, item.valor);
          ok = campo.value === item.valor;
        }
      } catch (erro) {
        ok = false;
      }
      (ok ? feitos : falhas).push(item);
    }

    return { feitos, falhas };
  }

  window.PathRCampos = {
    normalizar,
    chave,
    eSensivel,
    eAberta,
    rotuloDe,
    chaveDoCampo,
    todosOsCampos,
    analisar,
    preencher,
    escrever,
  };
})();
