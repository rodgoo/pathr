/**
 * O que o app já viu, guardado para quando não houver rede.
 *
 * Sem isto, abrir o PathR no avião mostraria a tela de entrada: o app começa
 * perguntando `GET /auth/me`, e uma falha de rede ali é indistinguível de
 * "não está logado". Guardar a última resposta de cada GET resolve as duas
 * coisas de uma vez — a sessão continua reconhecida e as telas abrem com o
 * último conteúdo conhecido.
 *
 * **O cache tem dono.** Um aparelho de casa pode ter duas contas; mostrar o
 * roadmap de uma pessoa para a outra seria pior que não funcionar offline. O
 * dono é adotado da própria resposta de `/auth/me`, e trocar de dono apaga
 * tudo que estava guardado.
 */

import type { User } from "@/api/types";
import { STORE_CACHE, STORE_META, idbAll, idbClear, idbGet, idbPut } from "./idb";
import { project } from "./projections";
import { pending } from "./outbox";

interface CacheEntry {
  path: string;
  body: unknown;
  savedAt: number;
  owner: string;
}

interface OwnerRecord {
  id: "owner";
  userId: string;
}

/**
 * Rotas que NÃO ficam no aparelho.
 *
 * O segredo do segundo fator e a exportação completa dos dados não têm uso
 * offline — só aumentariam o que vaza se alguém abrir o navegador de outra
 * pessoa. A foto de perfil não passa por aqui (vem como blob, não JSON).
 */
const NAO_GUARDAR = ["/auth/mfa", "/profile/export"];

let donoAtual: string | null = null;
let donoCarregado = false;

async function carregaDono(): Promise<string | null> {
  if (donoCarregado) return donoAtual;
  const registro = await idbGet<OwnerRecord>(STORE_META, "owner").catch(() => undefined);
  donoAtual = registro?.userId ?? null;
  donoCarregado = true;
  return donoAtual;
}

/**
 * Declara de quem são os dados guardados. Trocou de pessoa, apaga tudo.
 *
 * A fila de escritas NÃO é apagada junto: ela guarda o id de quem a criou e
 * só é enviada para a sessão certa. Alguém que marcou módulos offline, saiu e
 * emprestou o telefone não deve perder o que fez.
 */
export async function adoptOwner(userId: string): Promise<void> {
  const anterior = await carregaDono();
  if (anterior === userId) return;
  await idbClear(STORE_CACHE).catch(() => undefined);
  await idbPut<OwnerRecord>(STORE_META, { id: "owner", userId });
  donoAtual = userId;
  donoCarregado = true;
}

/** Quem é o dono do cache atual, ou `null` quando ninguém entrou ainda. */
export const currentOwner = (): Promise<string | null> => carregaDono();

const isUser = (body: unknown): body is User =>
  typeof body === "object" && body !== null && typeof (body as User).id === "string";

/**
 * Guarda a resposta de um GET.
 *
 * A resposta de `/auth/me` adota o dono ANTES de ser gravada: fosse depois, a
 * troca de conta apagaria justamente o registro que acabou de chegar, e o app
 * da pessoa nova nunca abriria offline.
 */
export async function saveRead(path: string, body: unknown): Promise<void> {
  if (NAO_GUARDAR.some((rota) => path.startsWith(rota))) return;
  try {
    if (path.startsWith("/auth/me") && isUser(body)) await adoptOwner(body.id);
    const owner = (await carregaDono()) ?? "";
    await idbPut<CacheEntry>(STORE_CACHE, { path, body, savedAt: Date.now(), owner });
  } catch {
    // Sem armazenamento (cota estourada, navegação privada): o app segue
    // online-only. Falhar a requisição por causa do cache seria trocar uma
    // degradação por uma quebra.
  }
}

export interface CachedRead {
  body: unknown;
  savedAt: number;
}

/**
 * A última resposta conhecida para `path`, com as escritas pendentes por cima.
 *
 * Devolve `null` quando não há nada guardado, quando o guardado é de outra
 * conta, ou quando não há armazenamento — nos três casos quem chamou deve
 * propagar o erro de rede original.
 */
export async function readCached(path: string): Promise<CachedRead | null> {
  try {
    const entrada = await idbGet<CacheEntry>(STORE_CACHE, path);
    if (!entrada) return null;
    const dono = await carregaDono();
    if (entrada.owner && dono && entrada.owner !== dono) return null;
    const fila = dono ? await pending(dono) : [];
    return { body: project(path, entrada.body, fila), savedAt: entrada.savedAt };
  } catch {
    return null;
  }
}

/** Quando foi a última vez que alguma resposta chegou do servidor. */
export async function lastSyncAt(): Promise<number | null> {
  try {
    const entradas = await idbAll<CacheEntry>(STORE_CACHE);
    if (entradas.length === 0) return null;
    return entradas.reduce((maior, item) => Math.max(maior, item.savedAt), 0);
  } catch {
    return null;
  }
}

/** No logout: o conteúdo sai do aparelho, o dono deixa de existir. */
export async function clearReads(): Promise<void> {
  try {
    await idbClear(STORE_CACHE);
    await idbClear(STORE_META);
  } catch {
    // Idem: sem armazenamento não há o que limpar.
  } finally {
    donoAtual = null;
    donoCarregado = false;
  }
}

/** Só para os testes: esquece o dono lido, sem tocar no banco. */
export function resetOwnerCacheForTests(): void {
  donoAtual = null;
  donoCarregado = false;
}
