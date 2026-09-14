/**
 * The page frame — in two shapes, chosen by viewport width.
 *
 * **Wide**: navigation rail on the left, the active screen on the right, both
 * floating on the app ground as rounded panels. The rail and the pane are
 * siblings in one wrapping flex row.
 *
 * **Compact (phone)**: a slim header, the screen, and a fixed bottom bar. Not
 * a squeezed version of the wide layout — the rail would eat half the width
 * of a 390px screen, leaving study text in a column too narrow to read.
 *
 * Both shapes pad for the notch and the home indicator via `env(safe-area-*)`.
 * The page declares `viewport-fit=cover`, so without that padding the first
 * line of the header would sit under the iPhone status bar.
 */
import type { ReactNode } from "react";
import { useAppState } from "@/hooks/useAppState";
import { useIsCompact } from "@/hooks/useMediaQuery";
import { BG, PANEL, TEXT } from "@/lib/tokens";
import { MobileHeader } from "./MobileHeader";
import { ALTURA_DA_BARRA, MobileNav } from "./MobileNav";
import { OfflineBar } from "./OfflineBar";
import { ScreenBoundary } from "./ScreenBoundary";
import { Sidebar } from "./Sidebar";
import { AvisosDeAmizade } from "@/components/social/AvisosDeAmizade";

const FUNDO: React.CSSProperties = {
  // 100dvh e não 100vh: no Safari do iPhone, `vh` conta a barra de endereço
  // como se ela nunca recolhesse, e a última linha do app fica sob ela.
  minHeight: "100dvh",
  background: BG,
  color: TEXT.full,
  fontFamily: "Inter, system-ui, sans-serif",
  fontSize: 15,
};

const PAINEL: React.CSSProperties = {
  minWidth: 0,
  display: "flex",
  flexDirection: "column",
  gap: 11.2,
  borderRadius: 14,
  background: PANEL,
  boxShadow: "0 0 0 1px #222228",
};

export function AppShell({ children }: { children: ReactNode }) {
  const compacto = useIsCompact();
  const { state } = useAppState();
  // O limite de erro fica DENTRO da moldura: se uma tela quebrar, a navegação
  // continua desenhada e dá para sair dela.
  const conteudo = <ScreenBoundary resetKey={state.screen}>{children}</ScreenBoundary>;

  // UMA árvore só para as duas formas, com a tela sempre no mesmo lugar dela
  // (raiz → bloco → main → conteúdo). Antes eram dois `return` com estruturas
  // diferentes: cruzar a largura do celular — girar o aparelho, ou o próprio
  // vídeo em tela cheia ficar deitado — fazia o React jogar a tela inteira
  // fora e montar outra. O player do YouTube era destruído no meio da tela
  // cheia e a página recarregava do zero. Agora a troca de forma muda estilo
  // e o que fica EM VOLTA da tela; a tela em si continua montada.
  return (
    <div
      style={
        compacto
          ? {
              ...FUNDO,
              display: "flex",
              flexDirection: "column",
              // Sem recuo lateral nem no topo AQUI: a barra do topo é fixa e
              // precisa pintar de borda a borda, senão o conteúdo aparece
              // rolando pelas frestas ao lado dela. O respiro é do bloco de baixo.
              paddingBottom: `calc(${ALTURA_DA_BARRA}px + 8.4px + var(--safe-bottom))`,
            }
          : { ...FUNDO, display: "flex", flexWrap: "wrap", padding: 11.2, gap: 11.2 }
      }
    >
      {compacto ? <MobileHeader /> : <Sidebar />}
      {/* No largo este bloco some do layout (`display: contents`) e o `main`
          vira item direto da linha, ao lado da barra lateral. */}
      <div
        style={
          compacto
            ? {
                flex: 1,
                display: "flex",
                flexDirection: "column",
                gap: 8.4,
                padding: "8.4px calc(8.4px + var(--safe-right)) 0 calc(8.4px + var(--safe-left))",
              }
            : { display: "contents" }
        }
      >
        {compacto ? <OfflineBar /> : null}
        <main
          className="pathr-tela"
          style={compacto ? { ...PAINEL, flex: 1, padding: 14 } : { ...PAINEL, flex: "1 1 620px", padding: 22.4 }}
        >
          {compacto ? null : <OfflineBar />}
          {conteudo}
        </main>
      </div>
      {compacto ? <MobileNav /> : null}
      <AvisosDeAmizade />
    </div>
  );
}
