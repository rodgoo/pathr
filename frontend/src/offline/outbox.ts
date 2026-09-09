/**
 * A fila de escritas feitas sem rede.
 *
 * O que ela protege: marcar um módulo como concluído no metrô, anotar onde
 * parou num vídeo, escrever a atividade prática. Sem ela essas ações
 * mostrariam um erro e o registro sumiria — e o app existe justamente para
 * acumular esse registro.
 *
 * Duas decisões que explicam o resto do arquivo:
 *
 * 1. **Só entra o que é idempotente.** A chave é `MÉTODO /caminho`, e uma
 *    escrita nova para a mesma chave FUNDE com a que estava lá. Marcar
 *    "concluído" três vezes offline manda um pedido, não três. Por isso a
 *    fila aceita PATCH e PUT de progresso e não aceita `POST /quizzes/…/submit`
 *    nem a geração do roadmap: repetir um POST cria coisa duas vezes, e
 *    corrigir quiz offline exigiria o gabarito no aparelho.
 *
 * 2. **A fila é do dono.** Cada item guarda o id de quem o criou e só é
 *    enviado quando esse mesmo usuário está na sessão. Num aparelho de casa,
 *    com duas contas, a alternativa seria gravar o progresso de uma pessoa na
 *    conta da outra.
 */

import { ApiError } from "@/api/errors";
import { STORE_OUTBOX, idbAll, idbDelete, idbPut } from "./idb";

export interface PendingWrite {
  /** `MÉTODO /caminho`. Duas escritas com a mesma chave viram uma. */
  key: string;
  method: string;
  path: string;
  body: Record<string, unknown> | null;
  /** Id do usuário que a criou. */
  owner: string;
  /** Quando entrou na fila — define a ordem de envio. */
  queuedAt: number;
  attempts: number;
}

export type Sender = (entry: PendingWrite) => Promise<unknown>;

export interface FlushResult {
  sent: number;
  /** Recusadas pelo servidor de forma definitiva e descartadas. */
  dropped: number;
  /** Ainda na fila: a rede caiu de novo, ou o servidor está fora. */
  kept: number;
}

export const outboxKey = (method: string, path: string): string =>
  `${method.toUpperCase()} ${path}`;

/**
 * Guarda uma escrita para depois.
 *
 * Corpos de PATCH são FUNDIDOS, não substituídos: as duas telas que mexem no
 * progresso de um material mandam campos diferentes (uma o status e os
 * minutos, outra o status e onde parou). Substituir faria a segunda apagar o
 * que a primeira registrou.
 */
export async function enqueue(entry: Omit<PendingWrite, "queuedAt" | "attempts">): Promise<void> {
  const existentes = await idbAll<PendingWrite>(STORE_OUTBOX);
  const anterior = existentes.find((item) => item.key === entry.key);

  await idbPut<PendingWrite>(STORE_OUTBOX, {
    ...entry,
    body:
      anterior && anterior.body && entry.body
        ? { ...anterior.body, ...entry.body }
        : entry.body,
    // Mantém o instante da PRIMEIRA vez: a ordem de envio deve ser a ordem em
    // que a pessoa agiu, e reescrever a data mandaria a alteração mais antiga
    // para o fim da fila a cada retoque.
    queuedAt: anterior?.queuedAt ?? Date.now(),
    attempts: anterior?.attempts ?? 0,
  });
}

/** O que está esperando, na ordem em que foi feito. `owner` filtra por conta. */
export async function pending(owner?: string): Promise<PendingWrite[]> {
  const todas = await idbAll<PendingWrite>(STORE_OUTBOX);
  return todas
    .filter((item) => owner === undefined || item.owner === owner)
    .sort((a, b) => a.queuedAt - b.queuedAt);
}

/**
 * Um 4xx que não adianta repetir.
 *
 * 401 fica de fora porque pode ser só a sessão expirada — o cliente renova e
 * a próxima tentativa passa. 408 e 429 são "tente de novo", literalmente.
 * O resto (400, 403, 404, 422) é o servidor dizendo que o pedido está errado
 * ou que o alvo não existe mais: repetir para sempre transformaria um item
 * numa fila que nunca esvazia.
 */
function recusaDefinitiva(erro: unknown): boolean {
  return (
    erro instanceof ApiError &&
    erro.status >= 400 &&
    erro.status < 500 &&
    erro.status !== 401 &&
    erro.status !== 408 &&
    erro.status !== 429
  );
}

/**
 * Tenta enviar tudo que é do `owner`, em ordem.
 *
 * Para no primeiro erro de rede: se a conexão caiu no terceiro item, insistir
 * nos seguintes só gasta bateria. A ordem importa — dois pedidos para o mesmo
 * módulo precisam chegar na ordem em que foram feitos.
 */
export async function flush(owner: string, sender: Sender): Promise<FlushResult> {
  const fila = await pending(owner);
  let sent = 0;
  let dropped = 0;

  for (const item of fila) {
    try {
      await sender(item);
      await idbDelete(STORE_OUTBOX, item.key);
      sent += 1;
    } catch (erro) {
      if (recusaDefinitiva(erro)) {
        await idbDelete(STORE_OUTBOX, item.key);
        dropped += 1;
        continue;
      }
      // Rede fora (`isNetworkError`) ou servidor fora (5xx): o item volta para
      // a fila com uma tentativa a mais e o RESTO espera a próxima janela.
      await idbPut<PendingWrite>(STORE_OUTBOX, { ...item, attempts: item.attempts + 1 });
      return { sent, dropped, kept: fila.length - sent - dropped };
    }
  }

  return { sent, dropped, kept: 0 };
}

/** Apaga a fila inteira. Só no logout com a fila já vazia, ou a pedido. */
export async function clearOutbox(): Promise<void> {
  const todas = await idbAll<PendingWrite>(STORE_OUTBOX);
  await Promise.all(todas.map((item) => idbDelete(STORE_OUTBOX, item.key)));
}
