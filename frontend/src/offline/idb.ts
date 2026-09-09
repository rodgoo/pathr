/**
 * O pouco de IndexedDB que o app precisa.
 *
 * IndexedDB e não `localStorage` por dois motivos que valem para um app
 * instalado no iPhone: `localStorage` guarda só string e tem cota apertada,
 * e — o que importa mais — o Safari o descarta com mais facilidade quando o
 * aparelho fica sem espaço. O rascunho de uma atividade escrita do zero é o
 * trabalho mais caro do app; perdê-lo por falta de espaço não é aceitável.
 *
 * Cinco funções, sem biblioteca: o que uma (idb, dexie) resolveria — índices
 * compostos, migrações, transações longas — este app não tem. São dois
 * armazéns de chave-valor.
 */

const DB_NAME = "pathr-offline";
const DB_VERSION = 1;

/** Respostas de GET já vistas, para o app abrir sem rede. Chave: o caminho. */
export const STORE_CACHE = "cache";
/** Escritas feitas offline, esperando a rede. Chave: `MÉTODO /caminho`. */
export const STORE_OUTBOX = "outbox";
/** De quem são os dados guardados aqui. Chave fixa, um registro só. */
export const STORE_META = "meta";

let conexao: Promise<IDBDatabase> | null = null;

/**
 * Abre o banco, uma vez.
 *
 * Rejeita quando não há IndexedDB — Safari em navegação privada antiga, um
 * ambiente de teste sem shim. Quem chama trata a rejeição como "sem
 * armazenamento" e segue online-only, porque um app que quebra por não
 * conseguir guardar cache é pior que um app sem cache.
 */
export function openDb(): Promise<IDBDatabase> {
  conexao ??= new Promise<IDBDatabase>((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB indisponível"));
      return;
    }
    const pedido = indexedDB.open(DB_NAME, DB_VERSION);
    pedido.onupgradeneeded = () => {
      const db = pedido.result;
      if (!db.objectStoreNames.contains(STORE_CACHE)) {
        db.createObjectStore(STORE_CACHE, { keyPath: "path" });
      }
      if (!db.objectStoreNames.contains(STORE_OUTBOX)) {
        db.createObjectStore(STORE_OUTBOX, { keyPath: "key" });
      }
      if (!db.objectStoreNames.contains(STORE_META)) {
        db.createObjectStore(STORE_META, { keyPath: "id" });
      }
    };
    pedido.onsuccess = () => resolve(pedido.result);
    pedido.onerror = () => reject(pedido.error ?? new Error("Falha ao abrir o banco"));
  }).catch((erro) => {
    // Uma falha de abertura não deve envenenar as próximas tentativas: sem
    // isto, a promessa rejeitada ficaria memorizada para sempre.
    conexao = null;
    throw erro;
  });
  return conexao;
}

function transacao<T>(
  store: string,
  modo: IDBTransactionMode,
  executa: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const tx = db.transaction(store, modo);
        const pedido = executa(tx.objectStore(store));
        pedido.onsuccess = () => resolve(pedido.result);
        pedido.onerror = () => reject(pedido.error ?? new Error("Falha na transação"));
      }),
  );
}

export const idbGet = <T>(store: string, key: IDBValidKey): Promise<T | undefined> =>
  transacao<T | undefined>(store, "readonly", (s) => s.get(key) as IDBRequest<T | undefined>);

export const idbPut = <T>(store: string, value: T): Promise<IDBValidKey> =>
  transacao(store, "readwrite", (s) => s.put(value));

export const idbDelete = (store: string, key: IDBValidKey): Promise<undefined> =>
  transacao(store, "readwrite", (s) => s.delete(key));

export const idbAll = <T>(store: string): Promise<T[]> =>
  transacao<T[]>(store, "readonly", (s) => s.getAll() as IDBRequest<T[]>);

export const idbClear = (store: string): Promise<undefined> =>
  transacao(store, "readwrite", (s) => s.clear());

/** Só para os testes: força a próxima chamada a reabrir o banco. */
export function resetConnectionForTests(): void {
  conexao = null;
}
