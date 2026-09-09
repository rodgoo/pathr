/**
 * O erro tipado da API e a pergunta que a camada offline faz o tempo todo:
 * "isto foi o servidor recusando, ou foi a rede que não existe?".
 *
 * Mora fora de `client.ts` porque a fila de escrita offline precisa da mesma
 * distinção, e importá-la do cliente criaria um ciclo — o cliente é quem
 * enfileira.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    /** Mensagem em português vinda do backend, pronta para exibir. */
    message: string,
    /** Presente quando o login pediu o segundo fator. */
    readonly mfaRequired = false,
    /**
     * O login foi recusado porque o e-mail ainda não foi confirmado.
     *
     * Vem num cabeçalho e não do texto da mensagem: comparar strings de
     * mensagem para decidir o que a tela mostra quebra na primeira vez que
     * alguém melhora a redação.
     */
    readonly emailUnverified = false,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * O pedido não chegou a ter resposta.
 *
 * `fetch` só rejeita quando a requisição não completou — sem rede, DNS que
 * não resolve, TLS que falha, servidor inalcançável. Um 500 NÃO cai aqui: ele
 * é uma resposta, e vira `ApiError`. A diferença decide tudo na fila offline:
 * o que falhou por rede espera e é reenviado; o que o servidor recusou não
 * adianta reenviar.
 *
 * O cancelamento (`AbortError`) fica de fora de propósito — quem cancelou foi
 * o próprio app, ao desmontar uma tela, e isso não é uma escrita a guardar.
 */
export function isNetworkError(erro: unknown): boolean {
  if (erro instanceof ApiError) return false;
  if (erro instanceof DOMException && erro.name === "AbortError") return false;
  if (erro instanceof Error && erro.name === "AbortError") return false;
  return true;
}

/** Mensagem pronta para exibir a partir de qualquer erro. */
export const messageFor = (erro: unknown): string =>
  erro instanceof ApiError
    ? erro.message
    : "Não consegui falar com o servidor. Verifique sua conexão.";
