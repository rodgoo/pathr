/**
 * Consultas de mídia lidas do JavaScript.
 *
 * O PathR estiliza quase tudo com estilo inline — é o que `lib/tokens` existe
 * para servir. Isso significa que uma `@media` no CSS não alcança a maior
 * parte da interface, e a diferença entre o app no desktop e no iPhone não é
 * de tamanho: é de FORMA. No celular a barra lateral vira uma barra inferior,
 * com outros itens e outro comportamento. Isso é uma decisão de render, não
 * de folha de estilo.
 *
 * `useSyncExternalStore` e não `useState` + `useEffect`: girar o telefone
 * muda a resposta entre a renderização e o efeito, e o React precisa poder
 * ler o valor atual no momento em que renderiza.
 */

import { useSyncExternalStore } from "react";

/** Acima disto cabe a barra lateral. Abaixo, ela ocuparia metade da tela. */
const LARGURA_COMPACTA = 720;

function assina(query: string) {
  return (aoMudar: () => void) => {
    if (typeof window === "undefined" || !window.matchMedia) return () => {};
    const lista = window.matchMedia(query);
    lista.addEventListener("change", aoMudar);
    return () => lista.removeEventListener("change", aoMudar);
  };
}

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    assina(query),
    () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(query).matches : false),
    // No servidor e no jsdom sem matchMedia: assume tela larga, que é o
    // layout que os testes existentes descrevem.
    () => false,
  );
}

/** `true` num celular em pé — a forma para a qual a barra inferior existe. */
export const useIsCompact = (): boolean =>
  useMediaQuery(`(max-width: ${LARGURA_COMPACTA}px)`);
