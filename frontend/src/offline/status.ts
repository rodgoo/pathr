/**
 * O que a interface precisa saber sobre a rede, num lugar só.
 *
 * Duas coisas moram aqui porque nascem na camada de rede e são consumidas por
 * componentes que não a chamam: a barra que anuncia "offline, N alterações
 * guardadas", e o sinal que manda as telas recarregarem depois que a fila
 * esvaziou.
 *
 * São duas assinaturas separadas de propósito. Se fossem um store só, cada
 * mudança de contador de pendências remontaria toda consulta da tela — e é
 * exatamente a sincronização que dispara essas mudanças.
 */

export interface OfflineStatus {
  /** Há rede? Vem do navegador e das requisições que de fato falharam. */
  online: boolean;
  /** Escritas guardadas esperando a rede. */
  pendingCount: number;
  /** Uma sincronização está em curso. */
  syncing: boolean;
  /** A tela está mostrando conteúdo guardado, não o do servidor. */
  servingCache: boolean;
  /** Quando alguma resposta chegou do servidor pela última vez. */
  lastSyncAt: number | null;
  /**
   * Escritas que o servidor recusou de forma definitiva na última
   * sincronização — um módulo apagado noutro aparelho, por exemplo.
   *
   * Aparece na interface porque o contrário seria pior: a pessoa registrou
   * algo, viu "guardado", e o registro sumiria sem ninguém dizer nada.
   */
  discarded: number;
}

function criaStore<T>(inicial: T) {
  let estado = inicial;
  const ouvintes = new Set<() => void>();
  return {
    get: () => estado,
    set: (proximo: T) => {
      if (Object.is(estado, proximo)) return;
      estado = proximo;
      ouvintes.forEach((ouvinte) => ouvinte());
    },
    subscribe: (ouvinte: () => void) => {
      ouvintes.add(ouvinte);
      return () => ouvintes.delete(ouvinte);
    },
  };
}

const inicial: OfflineStatus = {
  online: typeof navigator === "undefined" ? true : navigator.onLine,
  pendingCount: 0,
  syncing: false,
  servingCache: false,
  lastSyncAt: null,
  discarded: 0,
};

const status = criaStore<OfflineStatus>(inicial);

/**
 * Uma contagem que sobe quando os dados do servidor mudaram por baixo das
 * telas — hoje, quando a fila offline foi enviada com sucesso.
 *
 * `useQuery` observa este número e recarrega. Sem ele, uma sincronização
 * bem-sucedida deixaria a tela mostrando a projeção local para sempre, e a
 * primeira divergência com o servidor só apareceria no próximo F5.
 */
const revisao = criaStore(0);

export const offlineStatus = {
  get: status.get,
  subscribe: status.subscribe,
  /** Mescla um pedaço do estado. */
  patch: (parte: Partial<OfflineStatus>) => status.set({ ...status.get(), ...parte }),
};

/**
 * Vários avisos seguidos viram um.
 *
 * Voltar ao app com a fila cheia dispara dois gatilhos quase juntos — a
 * sincronização que subiu a fila e a reconferência do primeiro plano. Sem
 * juntá-los, cada tela aberta faria duas rodadas de requisições para chegar
 * ao mesmo resultado.
 */
let agendado: number | null = null;

export const dataRevision = {
  get: revisao.get,
  subscribe: revisao.subscribe,
  bump: () => {
    if (agendado !== null) return;
    agendado = window.setTimeout(() => {
      agendado = null;
      revisao.set(revisao.get() + 1);
    }, 60);
  },
};
