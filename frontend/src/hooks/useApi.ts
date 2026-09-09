/**
 * Busca de dados do servidor.
 *
 * Deliberadamente pequeno em vez de uma biblioteca de cache: o app tem oito
 * telas, cada uma carrega o que precisa quando abre, e não há duas telas
 * disputando a mesma chave de cache. O que uma biblioteca resolveria aqui —
 * invalidação cruzada, dedupe entre componentes — não é problema que este app
 * tenha.
 *
 * O que ele resolve, e que toda tela precisaria repetir: os quatro estados
 * (carregando, erro, vazio, pronto), o cancelamento ao desmontar, e um
 * `reload` para depois de uma escrita.
 */

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ApiError } from "@/api/client";
import { dataRevision } from "@/offline/status";

export interface Query<T> {
  data: T | null;
  loading: boolean;
  /** Mensagem pronta para exibir, em português. */
  error: string | null;
  /** Status HTTP, quando o erro veio da API. 404 costuma ser "ainda não existe". */
  status: number | null;
  reload: () => void;
  /** Atualiza o dado local sem ir ao servidor — para escritas otimistas. */
  set: (updater: (current: T) => T) => void;
}

export function messageFor(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Não consegui falar com o servidor. Verifique sua conexão.";
}

/**
 * Executa `fetcher` na montagem e sempre que `deps` mudar.
 *
 * `enabled: false` mantém a consulta parada — usado quando a tela depende de
 * um id que ainda não existe, e disparar levaria a um 404 previsível.
 */
export function useQuery<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
  options: { enabled?: boolean } = {},
): Query<T> {
  const enabled = options.enabled ?? true;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  const [tick, setTick] = useState(0);

  // Depois que a fila offline esvazia, o servidor tem a palavra final sobre o
  // que foi gravado. Sem observar isto, a tela ficaria mostrando a projecao
  // local ate o proximo F5 — e a primeira divergencia com o servidor so
  // apareceria tarde demais para ser entendida.
  const revisao = useSyncExternalStore(dataRevision.subscribe, dataRevision.get, dataRevision.get);

  // A função muda de identidade a cada render das telas (é uma seta inline);
  // guardá-la numa ref evita que isso sozinho dispare o efeito de novo.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }
    const controller = new AbortController();
    let alive = true;

    setLoading(true);
    setError(null);
    setStatus(null);

    fetcherRef
      .current(controller.signal)
      .then((result) => {
        if (alive) setData(result);
      })
      .catch((caught) => {
        // Requisição cancelada no desmonte não é erro para mostrar.
        if (!alive || controller.signal.aborted) return;
        setError(messageFor(caught));
        setStatus(caught instanceof ApiError ? caught.status : null);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, tick, revisao, ...deps]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  const set = useCallback(
    (updater: (current: T) => T) => setData((current) => (current === null ? current : updater(current))),
    [],
  );

  return { data, loading, error, status, reload, set };
}

/**
 * Uma escrita (POST/PATCH/DELETE) com estado de envio e erro.
 *
 * Separado de `useQuery` porque uma escrita não roda sozinha na montagem, e
 * misturar as duas coisas num hook só faria toda tela ter que dizer "não
 * execute ainda".
 */
export function useMutation<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (...args: TArgs): Promise<TResult | null> => {
      setPending(true);
      setError(null);
      try {
        return await action(...args);
      } catch (caught) {
        setError(messageFor(caught));
        return null;
      } finally {
        setPending(false);
      }
    },
    [action],
  );

  return { run, pending, error, clearError: () => setError(null) };
}
