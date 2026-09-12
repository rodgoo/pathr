/**
 * A sincronização, e o que a interface conta sobre ela.
 *
 * Fica num provider e não em cada tela porque a fila é uma só: se cada tela
 * tentasse enviar por conta própria, duas telas abertas ao mesmo tempo
 * mandariam o mesmo item duas vezes, e a ordem — que importa quando dois
 * pedidos tocam o mesmo módulo — deixaria de existir.
 *
 * Quando ele tenta ENVIAR o que está na fila:
 * - ao abrir, se houver fila;
 * - quando o navegador anuncia que a rede voltou;
 * - quando o app volta ao primeiro plano (no iPhone em tela cheia, o evento
 *   `online` é pouco confiável; voltar para o app é o sinal que funciona);
 * - a cada 30 segundos enquanto houver algo na fila.
 *
 * E quando ele RECONFERE com o servidor o que já está na tela: ao voltar ao
 * primeiro plano e ao recuperar a rede, se faz mais de 20 segundos desde a
 * última resposta. É o que faz o que outro aparelho gravou aparecer numa tela
 * que já estava aberta.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { sendPending } from "@/api/client";
import { currentOwner } from "@/offline/cache";
import { flush, pending } from "@/offline/outbox";
import { conectarEventos, desconectarEventos, seguirVisibilidade } from "@/offline/eventos";
import { dataRevision, offlineStatus, type OfflineStatus } from "@/offline/status";
import { applyUpdate, onUpdateReady, updateReady } from "@/pwa/register";
import { useAuth } from "./useAuth";

/** Enquanto houver fila, tenta de novo neste intervalo. */
const RETENTATIVA_MS = 30_000;

/**
 * Quanto tempo sem falar com o servidor já justifica reconferir.
 *
 * A mesma conta vale para os dois casos que importam: voltar ao app depois de
 * um tempo, e a rede voltar. Abaixo disso o que está na tela é recente o
 * bastante, e refazer tudo a cada troca rápida de app só gastaria bateria.
 */
// Cinco minutos, e não vinte segundos como antes.
//
// A reconferência em si ficou invisível — `useQuery` mantém na tela o que já
// está lá enquanto repergunta (ver hooks/useApi.ts), então voltar ao app não
// devolve mais ninguém ao esqueleto de carregamento. O que sobra é o custo de
// rede, e aí vinte segundos é curto demais: quem alterna entre o PathR e o
// editor a cada meio minuto pagava uma rodada de requisições por alternância
// sem que nada pudesse ter mudado do outro lado.
const RECONFERIR_APOS_MS = 300_000;

interface OfflineContextValue extends OfflineStatus {
  /** Uma versão nova do app está instalada e esperando. */
  updateReady: boolean;
  /** Aplica a versão nova. A página recarrega. */
  applyUpdate: () => void;
  /** Tenta esvaziar a fila agora. */
  sync: () => Promise<void>;
}

const OfflineContext = createContext<OfflineContextValue | null>(null);

let sincronizando: Promise<void> | null = null;

/**
 * Esvazia a fila do usuário logado.
 *
 * Compartilhada entre chamadas concorrentes pelo mesmo motivo da renovação de
 * sessão em `api/client`: dois gatilhos que caem juntos — a rede voltando e o
 * app voltando ao primeiro plano — enviariam a fila duas vezes.
 */
async function sincroniza(userId: string): Promise<void> {
  sincronizando ??= (async () => {
    offlineStatus.patch({ syncing: true });
    try {
      const resultado = await flush(userId, sendPending);
      const restante = await pending(userId).catch(() => []);
      offlineStatus.patch({
        pendingCount: restante.length,
        discarded: resultado.dropped,
        // Só volta a se dizer "com dados do servidor" quando a fila esvaziou:
        // com item pendente, o que a tela mostra ainda é projeção local.
        servingCache: restante.length > 0 ? offlineStatus.get().servingCache : false,
      });
      // Recarrega as telas só quando algo de fato subiu — a resposta do
      // servidor é a palavra final sobre o que ficou gravado.
      if (resultado.sent > 0) dataRevision.bump();
    } catch {
      // Rede ainda fora. A fila continua lá; a próxima janela tenta de novo.
    } finally {
      offlineStatus.patch({ syncing: false });
      sincronizando = null;
    }
  })();
  return sincronizando;
}

export function OfflineProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const status = useSyncExternalStore(
    offlineStatus.subscribe,
    offlineStatus.get,
    offlineStatus.get,
  );
  const [temAtualizacao, setTemAtualizacao] = useState(updateReady);

  const sync = useCallback(async () => {
    const dono = user?.id ?? (await currentOwner());
    if (dono) await sincroniza(dono);
  }, [user?.id]);

  // A contagem inicial: quem fechou o app com fila pendente precisa ver isso
  // na primeira tela, não depois da primeira tentativa de escrita.
  useEffect(() => {
    let vivo = true;
    void (async () => {
      const dono = user?.id ?? (await currentOwner());
      if (!dono || !vivo) return;
      const fila = await pending(dono).catch(() => []);
      if (!vivo) return;
      offlineStatus.patch({ pendingCount: fila.length });
      if (fila.length > 0) void sincroniza(dono);
    })();
    return () => {
      vivo = false;
    };
  }, [user?.id]);

  useEffect(() => {
    /**
     * O que o outro aparelho mudou só chega se alguém perguntar.
     *
     * Os dados do PathR são todos do servidor — nada de conta mora só no
     * navegador — então "sincronizado entre dispositivos" já vale para quem
     * ABRE uma tela agora. O buraco é a tela que já estava aberta: marcar um
     * módulo no celular não mexe no notebook que ficou no ar a manhã inteira.
     *
     * Reconferir ao voltar ao primeiro plano fecha esse buraco sem servidor
     * de eventos: é o momento em que a pessoa vai olhar, e é quando importa
     * que o que ela vê seja o que está gravado.
     */
    const reconferir = () => {
      const desde = offlineStatus.get().lastSyncAt;
      if (desde === null || Date.now() - desde > RECONFERIR_APOS_MS) dataRevision.bump();
    };

    const aoVoltar = () => {
      offlineStatus.patch({ online: true });
      void sync();
      reconferir();
    };
    const aoCair = () => offlineStatus.patch({ online: false });
    const aoPrimeiroPlano = () => {
      if (document.visibilityState !== "visible") return;
      void sync();
      reconferir();
    };
    window.addEventListener("online", aoVoltar);
    window.addEventListener("offline", aoCair);
    document.addEventListener("visibilitychange", aoPrimeiroPlano);
    // `focus` cobre o que `visibilitychange` não vê: no desktop, voltar para
    // a janela sem que a aba nunca tenha ficado escondida.
    window.addEventListener("focus", aoPrimeiroPlano);
    return () => {
      window.removeEventListener("online", aoVoltar);
      window.removeEventListener("offline", aoCair);
      document.removeEventListener("visibilitychange", aoPrimeiroPlano);
      window.removeEventListener("focus", aoPrimeiroPlano);
    };
  }, [sync]);

  // O temporizador só existe enquanto há fila: um intervalo permanente
  // acordaria o app de minuto em minuto sem ter o que fazer.
  useEffect(() => {
    if (status.pendingCount === 0) return undefined;
    const timer = window.setInterval(() => void sync(), RETENTATIVA_MS);
    return () => window.clearInterval(timer);
  }, [status.pendingCount, sync]);

  // O canal de avisos só existe com sessão: sem usuário o servidor responde
  // 401 e o navegador tentaria reconectar em laço.
  useEffect(() => {
    if (!user) return undefined;
    conectarEventos();
    const pararDeSeguir = seguirVisibilidade();
    return () => {
      pararDeSeguir();
      desconectarEventos();
    };
  }, [user]);

  useEffect(() => onUpdateReady(() => setTemAtualizacao(true)), []);

  const value = useMemo<OfflineContextValue>(
    () => ({ ...status, updateReady: temAtualizacao, applyUpdate, sync }),
    [status, temAtualizacao, sync],
  );

  return <OfflineContext.Provider value={value}>{children}</OfflineContext.Provider>;
}

export function useOffline(): OfflineContextValue {
  const value = useContext(OfflineContext);
  if (!value) throw new Error("useOffline precisa estar dentro de OfflineProvider");
  return value;
}
