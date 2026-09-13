/**
 * A troca de tela com transição: a tela que sai desvanece e a que entra sobe
 * de leve, em cruzamento, em vez de a página trocar de uma vez.
 *
 * Usa a View Transitions API do navegador (Chrome, Edge, Safari 18+): ele
 * fotografa a tela antiga, aplica a mudança e anima entre as duas — sem
 * manter as duas telas montadas nem atrasar a tela nova. Onde a API não
 * existe (Firefox, testes), a troca acontece na hora, como antes; a entrada
 * suave de cada tela (`noc-in`) continua valendo.
 *
 * Quem pediu menos movimento no sistema não recebe animação nenhuma.
 */

import { flushSync } from "react-dom";

type DocumentoComTransicao = Document & {
  startViewTransition?: (atualizar: () => void) => unknown;
};

export function comTransicao(atualizar: () => void): void {
  if (typeof document === "undefined") {
    atualizar();
    return;
  }
  const doc = document as DocumentoComTransicao;
  const menosMovimento =
    typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (!doc.startViewTransition || menosMovimento) {
    atualizar();
    return;
  }
  // flushSync: o navegador fotografa a tela nova assim que o callback
  // termina, então o React precisa já ter pintado a mudança ali dentro.
  doc.startViewTransition(() => flushSync(atualizar));
}
