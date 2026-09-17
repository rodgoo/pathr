/**
 * O serviço de fundo: guarda a chave e é o único que fala com a API.
 *
 * ## Por que a chave não vai para a página
 *
 * O script que preenche o formulário roda DENTRO do site da vaga. Ele é isolado
 * do JavaScript da página, mas é o pedaço mais exposto da extensão — e um bug
 * de vazamento ali entregaria a chave para um site qualquer. Então a chave fica
 * aqui, no serviço de fundo: a página pede "os dados", recebe os dados, e nunca
 * vê a credencial que os buscou.
 *
 * ## Por que a busca acontece aqui
 *
 * Chamada de outra origem feita pelo site esbarraria em CORS. O `fetch` do
 * serviço de fundo, com permissão declarada para o host da API no manifesto,
 * não passa por isso — e assim a API não precisa abrir CORS para
 * `chrome-extension://…`, que é uma origem que ninguém consegue verificar.
 */

const API_PADRAO = "https://api.pathr.notter.com.br";

async function guardado() {
  const { chave, api } = await chrome.storage.local.get(["chave", "api"]);
  return { chave: chave || "", api: (api || API_PADRAO).replace(/\/+$/, "") };
}

/**
 * Uma chamada à API do PathR com a chave da extensão.
 *
 * Distingue "sem chave" de "chave recusada" de "rede fora" porque a saída para
 * a pessoa é diferente em cada caso: colar a chave, criar outra, ou esperar.
 */
async function chamar(caminho, opcoes = {}) {
  const { chave, api } = await guardado();
  if (!chave) return { ok: false, erro: "sem-chave" };

  let resposta;
  try {
    resposta = await fetch(`${api}${caminho}`, {
      ...opcoes,
      headers: {
        "Content-Type": "application/json",
        "X-Pathr-Extensao": chave,
        ...(opcoes.headers || {}),
      },
    });
  } catch (erro) {
    return { ok: false, erro: "rede", detalhe: String(erro?.message || erro) };
  }

  if (resposta.status === 401) return { ok: false, erro: "chave-invalida" };
  if (!resposta.ok) {
    let detalhe = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (corpo?.detail) detalhe = corpo.detail;
    } catch {
      /* resposta sem JSON: fica o código mesmo */
    }
    return { ok: false, erro: "api", detalhe, status: resposta.status };
  }
  return { ok: true, corpo: await resposta.json() };
}

/**
 * Manda uma mensagem para os quadros de uma aba e junta as respostas.
 *
 * O quadro de cima não alcança o de dentro direto — são origens diferentes, e
 * é assim que tem de ser. O serviço de fundo é quem pode falar com os dois.
 */
function paraOsQuadros(abaId, mensagem) {
  return new Promise((resolve) => {
    if (abaId == null) return resolve({ ok: false, erro: "sem-aba" });
    chrome.tabs.sendMessage(abaId, mensagem, (resposta) => {
      // `lastError` acontece quando nenhum quadro respondeu (página sem iframe,
      // ou iframe que não recebeu o script). Não é erro: é "não havia ninguém".
      void chrome.runtime.lastError;
      resolve(resposta || { ok: true, feitos: [] });
    });
  });
}

chrome.runtime.onMessage.addListener((mensagem, _remetente, responder) => {
  (async () => {
    if (mensagem?.tipo === "quadro") {
      // Um quadro de dentro contando o que preencheu: repassa para o de cima.
      const abaId = _remetente.tab?.id;
      if (abaId != null) {
        chrome.tabs.sendMessage(abaId, { tipo: "quadro", carga: mensagem.carga }, { frameId: 0 }, () => {
          void chrome.runtime.lastError;
        });
      }
      responder({ ok: true });
      return;
    }
    if (mensagem?.tipo === "repreencher-quadros") {
      responder(
        await paraOsQuadros(_remetente.tab?.id, {
          tipo: "repreencher",
          respostas: mensagem.respostas || {},
        }),
      );
      return;
    }
    if (mensagem?.tipo === "dados") {
      const r = await chamar("/extensao/dados");
      responder(r.ok ? { ok: true, dados: r.corpo } : r);
      return;
    }
    if (mensagem?.tipo === "curriculo") {
      const r = await chamar("/extensao/curriculo");
      responder(r.ok ? { ok: true, curriculo: r.corpo } : r);
      return;
    }
    if (mensagem?.tipo === "respostas") {
      const r = await chamar("/extensao/respostas", {
        method: "POST",
        body: JSON.stringify({ respostas: mensagem.respostas || [] }),
      });
      responder(r.ok ? { ok: true, ...r.corpo } : r);
      return;
    }
    if (mensagem?.tipo === "preencher") {
      responder(await injetar(mensagem.abaId));
      return;
    }
    responder({ ok: false, erro: "desconhecido" });
  })();
  // `true` mantém o canal aberto: sem isso o `responder` de uma resposta
  // assíncrona chega depois que o Chrome já fechou a porta, e quem pediu fica
  // esperando para sempre.
  return true;
});

/**
 * Injeta o preenchedor na aba ativa.
 *
 * `allFrames: true` porque formulário de vaga mora em `<iframe>` mais vezes do
 * que não (Greenhouse, Lever e Workday embutidos no site da empresa). O painel
 * só aparece no quadro de cima — `conteudo.js` checa isso sozinho.
 */
async function injetar(abaId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId: abaId, allFrames: true },
      files: ["src/campos.js"],
    });
    await chrome.scripting.executeScript({
      target: { tabId: abaId, allFrames: true },
      files: ["src/conteudo.js"],
    });
    return { ok: true };
  } catch (erro) {
    // Páginas internas do navegador (chrome://, a loja de extensões) recusam
    // injeção por política, e isso não é defeito nosso.
    return { ok: false, erro: "injecao", detalhe: String(erro?.message || erro) };
  }
}
