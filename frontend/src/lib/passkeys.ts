/**
 * Chave de acesso: o que o PathR lembra NESTE aparelho, e a tradução de erros.
 *
 * Mesmo desenho do FinanceR para a parte que não depende do servidor: o app
 * só sabe quais chaves existem depois do login, e antes dele a tela de entrada
 * precisa decidir sozinha se oferece a chave como caminho principal. Daí a
 * marca local, gravada quando uma chave é cadastrada ou usada aqui. Não é
 * segredo nenhum — é preferência de tela.
 *
 * A marca NÃO usa o prefixo `pathr:` de propósito: o logout apaga tudo que
 * começa com `pathr:` (ver limparEstadoGuardado), e esta marca existe
 * justamente para o PRÓXIMO login neste aparelho.
 */

import { browserSupportsWebAuthn } from "@simplewebauthn/browser";

const MARCA = "pathr.passkey";

export function chaveSuportada(): boolean {
  try {
    return browserSupportsWebAuthn();
  } catch {
    return false;
  }
}

export function lembrarChave(): void {
  try {
    window.localStorage.setItem(MARCA, "1");
  } catch {
    // Navegação privada: segue sem lembrar.
  }
}

export function esquecerChave(): void {
  try {
    window.localStorage.removeItem(MARCA);
  } catch {
    // Idem.
  }
}

export function temChaveNesteAparelho(): boolean {
  try {
    return window.localStorage.getItem(MARCA) === "1";
  } catch {
    return false;
  }
}

/**
 * Uma frase de tela para o erro da cerimônia, ou null quando não é erro.
 *
 * Cancelar o pedido do Face ID ou da digital devolve null: a pessoa desistiu,
 * e uma mensagem vermelha por isso seria culpá-la por mudar de ideia.
 */
export function mensagemDeErroDaChave(erro: unknown): string | null {
  const nome = erro instanceof Error ? erro.name : "";
  const texto = erro instanceof Error ? erro.message : String(erro ?? "");
  const codigo = (erro as { code?: string } | null)?.code ?? "";
  if (
    nome === "NotAllowedError" ||
    nome === "AbortError" ||
    /not allowed|cancel|abort|timed out/i.test(texto)
  ) {
    return null;
  }
  if (nome === "InvalidStateError" || codigo === "ERROR_AUTHENTICATOR_PREVIOUSLY_REGISTERED") {
    return "Este aparelho já tem uma chave de acesso cadastrada nesta conta.";
  }
  return texto || "Não foi possível usar a chave de acesso.";
}
