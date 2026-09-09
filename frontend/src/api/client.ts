/**
 * Cliente HTTP da API do PathR.
 *
 * Duas coisas que este arquivo resolve e que nenhuma tela deveria repetir:
 *
 * 1. **Sessão em cookie.** Todo pedido vai com `credentials: "include"`; o
 *    token nunca passa pelo JavaScript, então um XSS não leva a sessão.
 *
 * 2. **Renovação transparente.** Quando um 401 chega, o cliente chama
 *    `/auth/refresh` UMA vez e repete o pedido original. Sem isso, a pessoa
 *    seria deslogada a cada 30 minutos no meio do que estivesse fazendo.
 *    A renovação é compartilhada entre chamadas concorrentes: cinco pedidos
 *    que estouram juntos fazem um refresh, não cinco — cinco rotacionariam o
 *    refresh token cinco vezes e quatro delas seriam vistas como reuso de
 *    token roubado pelo backend, derrubando a sessão inteira.
 */

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "https://localhost:8031";

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

/** Rotas que não devem disparar renovação — elas SÃO o fluxo de sessão. */
const NO_REFRESH = ["/auth/login", "/auth/signup", "/auth/refresh", "/auth/logout"];

/** O refresh em voo, se houver. Compartilhado por todas as chamadas. */
let refreshing: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${BASE_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  })
    .then((response) => response.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Para upload: mandado como está, sem JSON.stringify nem content-type. */
  formData?: FormData;
  signal?: AbortSignal;
}

async function parseError(response: Response): Promise<ApiError> {
  let detail = `Erro ${response.status}`;
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") detail = body.detail;
  } catch {
    // Resposta sem corpo JSON (502 de gateway, por exemplo). A mensagem
    // genérica acima já serve.
  }
  return new ApiError(
    response.status,
    detail,
    response.headers.get("x-pathr-mfa") === "required",
    response.headers.get("x-pathr-unverified") === "1",
  );
}

/**
 * O pedido em si: cookie, renovação transparente e erro tipado.
 *
 * Separado de `request` porque nem toda resposta é JSON — a foto de perfil
 * sai como imagem. Sem isto, quem precisasse dos bytes teria que repetir a
 * lógica de renovação, e uma segunda cópia dela é o tipo de coisa que passa a
 * divergir na primeira correção feita só de um lado.
 */
async function send(path: string, options: RequestOptions = {}): Promise<Response> {
  const disparar = () =>
    fetch(`${BASE_URL}${path}`, {
      method: options.method ?? (options.body || options.formData ? "POST" : "GET"),
      credentials: "include",
      headers: options.formData || !options.body ? undefined : { "Content-Type": "application/json" },
      body: options.formData ?? (options.body ? JSON.stringify(options.body) : undefined),
      signal: options.signal,
    });

  let response = await disparar();

  if (response.status === 401 && !NO_REFRESH.some((route) => path.startsWith(route))) {
    if (await refreshSession()) {
      response = await disparar();
    }
  }

  if (!response.ok) throw await parseError(response);
  return response;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { method: "GET", signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  /**
   * Uma resposta que não é JSON — hoje, a foto de perfil.
   *
   * A imagem vem por aqui e não por `<img src="https://api…">`: o app e a API
   * estão em hosts diferentes, então a tag `img` não mandaria o cookie de
   * sessão e a foto voltaria 401. Buscando como blob, o cookie vai junto.
   */
  blob: (path: string) => send(path).then((response) => response.blob()),
  upload: <T>(path: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<T>(path, { method: "POST", formData: form });
  },
};
