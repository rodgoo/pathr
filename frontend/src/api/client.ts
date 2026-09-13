/**
 * Cliente HTTP da API do PathR.
 *
 * Quatro coisas que este arquivo resolve e que nenhuma tela deveria repetir:
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
 *
 * 3. **Leitura sem rede.** Toda resposta de GET é guardada no aparelho. Se o
 *    pedido seguinte não completar por falta de rede, o cliente devolve a
 *    última resposta conhecida em vez de um erro — é o que faz o app
 *    instalado no iPhone abrir no metrô em vez de mostrar a tela de entrada.
 *
 * 4. **Escrita sem rede.** As escritas de progresso marcadas como
 *    enfileiráveis entram numa fila local quando a rede falha e são enviadas
 *    quando ela volta. Só entra o que é idempotente — ver `offline/outbox`.
 *
 * Os pontos 3 e 4 valem só para falha de REDE. Um 4xx do servidor continua
 * sendo erro na tela: o pedido chegou e foi recusado, e fingir que deu certo
 * esconderia o problema até a próxima abertura do app.
 */

import { readCached, saveRead, currentOwner } from "@/offline/cache";
import { ID_DESTA_ABA } from "@/offline/eventos";
import { enqueue, outboxKey, pending, type PendingWrite } from "@/offline/outbox";
import { offlineStatus } from "@/offline/status";
import { ApiError, isNetworkError } from "./errors";

export { ApiError } from "./errors";

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "https://localhost:8031";

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

/**
 * O que fazer com esta escrita quando não houver rede.
 *
 * Ausente = a escrita falha e a tela mostra o erro, que é o certo para tudo
 * que o servidor precisa processar na hora (corrigir um quiz, gerar um plano,
 * entrar na conta). Presente = vai para a fila, e `optimistic` diz o que
 * devolver enquanto isso.
 */
export interface OfflineWrite<T> {
  optimistic?: () => T;
}

interface RequestOptions<T = unknown> {
  method?: string;
  body?: unknown;
  /** Para upload: mandado como está, sem JSON.stringify nem content-type. */
  formData?: FormData;
  signal?: AbortSignal;
  offline?: OfflineWrite<T>;
}

async function parseError(response: Response): Promise<ApiError> {
  let detail = `Erro ${response.status}`;
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") detail = body.detail;
    // Algumas recusas trazem, além da frase, o que fazer em seguida — o @
    // ocupado vem com sugestões. A frase continua sendo o que se mostra.
    else if (typeof body?.detail?.mensagem === "string") detail = body.detail.mensagem;
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
 *
 * Também é o caminho por onde a fila offline reenvia: ela precisa do erro
 * cru, sem cache nem reenfileiramento, para decidir entre insistir e
 * descartar.
 */
async function send(path: string, options: RequestOptions = {}): Promise<Response> {
  const disparar = () =>
    fetch(`${BASE_URL}${path}`, {
      method: options.method ?? (options.body || options.formData ? "POST" : "GET"),
      credentials: "include",
      // Quem escreveu isto. O servidor devolve o mesmo id no aviso que manda
      // aos outros aparelhos, e é assim que esta aba reconhece o próprio eco
      // e não reconsulta por causa da escrita que ela mesma acabou de fazer.
      headers: {
        "X-Pathr-Client": ID_DESTA_ABA,
        ...(options.formData || !options.body ? {} : { "Content-Type": "application/json" }),
      },
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

/** A rede respondeu: o app volta a se considerar online. */
function marcaOnline(): void {
  const atual = offlineStatus.get();
  if (!atual.online || atual.servingCache) {
    offlineStatus.patch({ online: true, servingCache: false });
  }
}

/** A rede não respondeu. Não mexe em `servingCache`: quem serviu, avisa. */
function marcaOffline(): void {
  if (offlineStatus.get().online) offlineStatus.patch({ online: false });
}

async function atualizaContagem(): Promise<void> {
  const dono = await currentOwner();
  const fila = await pending(dono ?? undefined).catch(() => []);
  offlineStatus.patch({ pendingCount: fila.length });
}

/**
 * Enfileira uma escrita que não chegou ao servidor.
 *
 * Devolve `false` quando não dá para enfileirar — ninguém logado, ou
 * armazenamento indisponível. Aí o erro original sobe e a tela o mostra, que
 * é melhor que dizer "guardado" sem ter guardado nada.
 */
async function enfileira(path: string, method: string, body: unknown): Promise<boolean> {
  try {
    const owner = await currentOwner();
    if (!owner) return false;
    await enqueue({
      key: outboxKey(method, path),
      method: method.toUpperCase(),
      path,
      body: (body ?? null) as Record<string, unknown> | null,
      owner,
    });
    await atualizaContagem();
    return true;
  } catch {
    return false;
  }
}

export async function request<T>(path: string, options: RequestOptions<T> = {}): Promise<T> {
  const method = (options.method ?? (options.body || options.formData ? "POST" : "GET")).toUpperCase();

  try {
    const response = await send(path, options as RequestOptions);
    marcaOnline();
    if (response.status === 204) return undefined as T;
    const body = (await response.json()) as T;
    if (method === "GET") {
      void saveRead(path, body).then(() => offlineStatus.patch({ lastSyncAt: Date.now() }));
    }
    return body;
  } catch (erro) {
    if (!isNetworkError(erro)) throw erro;
    marcaOffline();

    if (method === "GET") {
      const guardado = await readCached(path);
      if (guardado) {
        offlineStatus.patch({ servingCache: true, lastSyncAt: guardado.savedAt });
        return guardado.body as T;
      }
      throw erro;
    }

    if (options.offline && !options.formData) {
      if (await enfileira(path, method, options.body)) {
        offlineStatus.patch({ servingCache: true });
        return (options.offline.optimistic?.() ?? undefined) as T;
      }
    }
    throw erro;
  }
}

/**
 * Reenvia um item da fila. Sem cache, sem reenfileiramento, sem otimismo:
 * a fila precisa ver o erro cru para decidir entre insistir e descartar.
 */
export async function sendPending(entry: PendingWrite): Promise<void> {
  await send(entry.path, { method: entry.method, body: entry.body ?? undefined });
  marcaOnline();
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { method: "GET", signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body: unknown, offline?: OfflineWrite<T>) =>
    request<T>(path, { method: "PATCH", body, offline }),
  put: <T>(path: string, body: unknown, offline?: OfflineWrite<T>) =>
    request<T>(path, { method: "PUT", body, offline }),
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
  /** Formulário com vários campos e arquivo opcional — o relato com foto. */
  form: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", formData: form }),
};
