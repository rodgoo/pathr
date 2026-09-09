/**
 * O vídeo tocando DENTRO do PathR, marcando progresso sozinho.
 *
 * Antes o material abria noutra aba: para assistir, a pessoa saía do app — e o
 * progresso só existia se ela voltasse e marcasse à mão. Agora o player mora
 * aqui, e a posição vem dele.
 *
 * Por que a IFrame API e não um `<iframe>` simples: um iframe comum toca o
 * vídeo e não conta nada. A API do YouTube dá `getCurrentTime()` e
 * `getDuration()`, que é o que permite retomar no segundo exato e contabilizar
 * a fração assistida sem pedir nada a quem está assistindo.
 *
 * O script é carregado uma vez e compartilhado: `onYouTubeIframeAPIReady` é um
 * gancho GLOBAL e único, então dois players na mesma tela com dois scripts
 * fariam o segundo sobrescrever o gancho do primeiro.
 */

import { useEffect, useRef, useState } from "react";
import { ACC, TEXT } from "@/lib/tokens";

/** De quanto em quanto tempo a posição é gravada no servidor. Curto o
 * bastante para não perder minutos assistidos, longo o bastante para não
 * mandar uma requisição por segundo. */
const INTERVALO_GRAVACAO_MS = 15_000;

/** A partir daqui o vídeo conta como visto. Não são 100% de propósito:
 * créditos finais e encerramento fazem quase todo mundo sair antes do fim, e
 * exigir o último segundo deixaria "concluído" quase inalcançável. */
const FRACAO_CONCLUIDO = 0.9;

interface YTPlayer {
  getCurrentTime: () => number;
  getDuration: () => number;
  destroy: () => void;
}

declare global {
  interface Window {
    YT?: {
      Player: new (el: HTMLElement, opts: unknown) => YTPlayer;
      PlayerState: { ENDED: number; PLAYING: number; PAUSED: number };
    };
    onYouTubeIframeAPIReady?: () => void;
  }
}

/** O id do vídeo, das várias formas que uma URL do YouTube aparece. */
export function idDoYoutube(url: string): string | null {
  try {
    const endereco = new URL(url);
    const host = endereco.hostname.replace("www.", "");
    if (host === "youtu.be") return endereco.pathname.slice(1) || null;
    if (!host.endsWith("youtube.com")) return null;
    if (endereco.pathname.startsWith("/embed/")) return endereco.pathname.slice(7) || null;
    if (endereco.pathname.startsWith("/shorts/")) return endereco.pathname.slice(8) || null;
    return endereco.searchParams.get("v");
  } catch {
    return null;
  }
}

/** Carrega o script da API uma única vez para a página inteira. */
let apiCarregando: Promise<void> | null = null;

function carregarApi(): Promise<void> {
  if (window.YT?.Player) return Promise.resolve();
  apiCarregando ??= new Promise<void>((resolve) => {
    const anterior = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      anterior?.();
      resolve();
    };
    const script = document.createElement("script");
    script.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(script);
  });
  return apiCarregando;
}

export function VideoPlayer({
  videoId,
  comecarEm,
  onProgresso,
}: {
  videoId: string;
  /** Segundo em que a pessoa parou da última vez. */
  comecarEm: number;
  /** Chamado com a posição e a fração assistida. Quem recebe decide o que
   * gravar — este componente não fala com a API. */
  onProgresso: (segundos: number, fracao: number) => void;
}) {
  const caixa = useRef<HTMLDivElement | null>(null);
  const player = useRef<YTPlayer | null>(null);
  const [pronto, setPronto] = useState(false);

  // Numa ref, e não em estado: o timer abaixo é criado uma vez e leria para
  // sempre o `onProgresso` do primeiro render se fechasse sobre ele.
  const reportar = useRef(onProgresso);
  reportar.current = onProgresso;

  useEffect(() => {
    let vivo = true;
    let timer: number | undefined;

    const enviar = () => {
      const p = player.current;
      if (!p) return;
      const posicao = p.getCurrentTime?.() ?? 0;
      const total = p.getDuration?.() ?? 0;
      if (!total) return;
      reportar.current(Math.floor(posicao), Math.min(1, posicao / total));
    };

    void carregarApi().then(() => {
      if (!vivo || !caixa.current || !window.YT) return;
      player.current = new window.YT.Player(caixa.current, {
        videoId,
        playerVars: {
          start: Math.max(0, Math.floor(comecarEm)),
          rel: 0,
          modestbranding: 1,
          // `origin` é exigido pela API quando ela roda dentro de outro site.
          origin: window.location.origin,
        },
        events: {
          onReady: () => vivo && setPronto(true),
          // Pausar e terminar gravam na hora: são os dois momentos em que a
          // pessoa provavelmente vai embora, e esperar o próximo tique
          // perderia o que ela acabou de assistir.
          onStateChange: () => enviar(),
        },
      });
      timer = window.setInterval(enviar, INTERVALO_GRAVACAO_MS);
    });

    return () => {
      vivo = false;
      window.clearInterval(timer);
      // Uma última leitura antes de desmontar: fechar o material é o momento
      // mais comum de sair, e sem isto o trecho desde o último tique sumiria.
      enviar();
      player.current?.destroy?.();
      player.current = null;
    };
  }, [videoId, comecarEm]);

  return (
    <div>
      <div
        style={{
          position: "relative",
          width: "100%",
          aspectRatio: "16 / 9",
          borderRadius: 10,
          overflow: "hidden",
          background: "#000",
        }}
      >
        <div ref={caixa} style={{ width: "100%", height: "100%" }} />
        {!pronto ? (
          <span
            style={{
              position: "absolute",
              inset: 0,
              display: "grid",
              placeItems: "center",
              color: TEXT.faint,
              fontSize: 12.5,
            }}
          >
            Carregando o vídeo…
          </span>
        ) : null}
      </div>
      {comecarEm > 0 ? (
        <p style={{ fontSize: 11.5, color: ACC, margin: "8.4px 0 0" }}>
          Retomando de {formatarTempo(comecarEm)}.
        </p>
      ) : null}
    </div>
  );
}

/** 754 -> "12:34". Também usado pela linha da biblioteca. */
export function formatarTempo(segundos: number): string {
  const total = Math.max(0, Math.floor(segundos));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const doisDigitos = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${doisDigitos(m)}:${doisDigitos(s)}` : `${m}:${doisDigitos(s)}`;
}

export const CONCLUIDO_A_PARTIR_DE = FRACAO_CONCLUIDO;
