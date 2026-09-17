/**
 * A janelinha do ícone: conectar a chave e mandar preencher a página.
 *
 * A chave é CONFERIDA antes de ser guardada — uma chamada de verdade à API. Sem
 * isso, uma chave com um caractere a menos ficaria salva, e o erro só apareceria
 * depois, no meio de um formulário, parecendo defeito do preenchimento.
 */

const situacao = document.getElementById("situacao");
const telaConectar = document.getElementById("tela-conectar");
const telaPronta = document.getElementById("tela-pronta");
const formulario = document.getElementById("form-chave");
const campoChave = document.getElementById("chave");
const campoApi = document.getElementById("api");
const erro = document.getElementById("erro");
const botaoConectar = document.getElementById("conectar");
const botaoPreencher = document.getElementById("preencher");
const botaoDesconectar = document.getElementById("desconectar");

const pedir = (mensagem) =>
  new Promise((resolve) => chrome.runtime.sendMessage(mensagem, (r) => resolve(r || {})));

function mostrar(conectada, texto) {
  telaConectar.hidden = conectada;
  telaPronta.hidden = !conectada;
  situacao.textContent = texto;
  situacao.classList.toggle("ligada", conectada);
}

function dizerErro(mensagem) {
  erro.textContent = mensagem;
  erro.hidden = !mensagem;
}

async function conferir() {
  const { chave } = await chrome.storage.local.get(["chave"]);
  if (!chave) return mostrar(false, "Não conectada");

  const resposta = await pedir({ tipo: "dados" });
  if (resposta.ok) {
    const nome = resposta.dados?.pessoa?.nome;
    return mostrar(true, nome ? `Conectada — ${nome}` : "Conectada");
  }
  if (resposta.erro === "chave-invalida") {
    // A chave foi revogada no app. Some daqui: guardar credencial morta só
    // serve para falhar de novo amanhã.
    await chrome.storage.local.remove(["chave"]);
    mostrar(false, "Chave revogada");
    dizerErro("Esta chave não vale mais. Crie outra em Candidaturas.");
    return undefined;
  }
  mostrar(true, "Sem conexão com o PathR");
  return undefined;
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  dizerErro("");
  const chave = campoChave.value.trim();
  const api = campoApi.value.trim();
  if (!chave) return;

  botaoConectar.disabled = true;
  botaoConectar.textContent = "Conferindo…";

  await chrome.storage.local.set(api ? { chave, api } : { chave });
  const resposta = await pedir({ tipo: "dados" });

  botaoConectar.disabled = false;
  botaoConectar.textContent = "Conectar";

  if (resposta.ok) {
    campoChave.value = "";
    const nome = resposta.dados?.pessoa?.nome;
    mostrar(true, nome ? `Conectada — ${nome}` : "Conectada");
    return;
  }

  // Não vale, não fica guardada.
  await chrome.storage.local.remove(["chave"]);
  dizerErro(
    resposta.erro === "chave-invalida"
      ? "Chave inválida ou revogada. Confira se copiou inteira."
      : resposta.erro === "rede"
        ? "Não consegui falar com o PathR. Confira sua conexão ou o endereço da API."
        : resposta.detalhe || "Não deu para conectar agora.",
  );
});

botaoPreencher.addEventListener("click", async () => {
  const [aba] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!aba?.id) return;
  botaoPreencher.disabled = true;
  const resposta = await pedir({ tipo: "preencher", abaId: aba.id });
  botaoPreencher.disabled = false;
  if (!resposta.ok) {
    situacao.textContent = "Esta página não aceita a extensão";
    return;
  }
  // O painel aparece na página; a janelinha sai da frente.
  window.close();
});

botaoDesconectar.addEventListener("click", async () => {
  await chrome.storage.local.remove(["chave"]);
  mostrar(false, "Não conectada");
});

conferir();
