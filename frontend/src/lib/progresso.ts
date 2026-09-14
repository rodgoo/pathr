/**
 * O progresso de uma tarefa demorada (a IA escrevendo um quiz, lendo um
 * currículo, corrigindo uma atividade).
 *
 * O servidor não conta por onde anda — a resposta chega inteira no fim. Então
 * a barra ESTIMA: anda depressa no começo e desacelera, sem nunca chegar a
 * 100% sozinha (para em 95%). Os 100% só aparecem quando a resposta chega.
 * Uma barra que enche e fica parada em 100% esperando é pior que nenhuma: diz
 * "acabou" quando não acabou.
 *
 * A estimativa aprende: cada tarefa guarda quanto demorou nas últimas vezes
 * (`localStorage`, por chave), e a barra seguinte usa a média. Um quiz que
 * costuma levar 25 s não enche em 8 s e fica parado; um que leva 6 s não se
 * arrasta.
 */

import { useEffect, useRef, useState } from "react";

const TETO = 95;
const GUARDADAS = 5;

/** Quanto da barra está cheio depois de `decorridoMs`, para uma tarefa que costuma levar `estimadoMs`. */
export function estimarPct(decorridoMs: number, estimadoMs: number): number {
  if (decorridoMs <= 0) return 0;
  // No tempo estimado a barra está em ~84%; passado dele, continua subindo
  // devagar em direção a 95%, e nunca para de se mexer por completo.
  return Math.min(TETO, TETO * (1 - Math.exp((-2.2 * decorridoMs) / Math.max(1000, estimadoMs))));
}

/** A etapa que o texto mostra, pela fração da barra. */
export function etapaDe(pct: number, etapas: readonly string[]): string {
  if (!etapas.length) return "";
  const indice = Math.min(etapas.length - 1, Math.floor((pct / 100) * etapas.length));
  return etapas[indice];
}

function chaveDe(chave: string) {
  return `pathr:duracao:${chave}`;
}

export function duracaoEstimada(chave: string, padraoMs: number): number {
  try {
    const guardadas = JSON.parse(window.localStorage.getItem(chaveDe(chave)) || "[]") as unknown;
    const validas = Array.isArray(guardadas)
      ? guardadas.filter((ms): ms is number => typeof ms === "number" && ms > 300 && ms < 600_000)
      : [];
    if (!validas.length) return padraoMs;
    return validas.reduce((soma, ms) => soma + ms, 0) / validas.length;
  } catch {
    return padraoMs;
  }
}

export function lembrarDuracao(chave: string, ms: number): void {
  try {
    const atuais = JSON.parse(window.localStorage.getItem(chaveDe(chave)) || "[]") as unknown;
    const lista = (Array.isArray(atuais) ? atuais : []).filter((v): v is number => typeof v === "number");
    window.localStorage.setItem(chaveDe(chave), JSON.stringify([...lista, Math.round(ms)].slice(-GUARDADAS)));
  } catch {
    // Sem armazenamento: a próxima estimativa usa o padrão.
  }
}

export interface Progresso {
  /** 0 a 100. */
  pct: number;
  /** A barra está na tela (inclui o instante em 100% depois de terminar). */
  visivel: boolean;
  terminou: boolean;
}

/**
 * Liga com `ativo` e acompanha até ele desligar. Ao desligar, mostra 100% por
 * um instante e some.
 */
export function useProgressoEstimado(ativo: boolean, chave: string, padraoMs: number): Progresso {
  const [estado, setEstado] = useState<Progresso>({ pct: 0, visivel: ativo, terminou: false });
  const inicio = useRef<number | null>(null);

  useEffect(() => {
    if (ativo) {
      inicio.current = Date.now();
      const estimado = duracaoEstimada(chave, padraoMs);
      setEstado({ pct: 0, visivel: true, terminou: false });
      const timer = window.setInterval(() => {
        const decorrido = Date.now() - (inicio.current ?? Date.now());
        setEstado({ pct: estimarPct(decorrido, estimado), visivel: true, terminou: false });
      }, 150);
      return () => window.clearInterval(timer);
    }
    if (inicio.current === null) return;
    // Terminou: guarda quanto levou, enche a barra e some logo depois.
    lembrarDuracao(chave, Date.now() - inicio.current);
    inicio.current = null;
    setEstado({ pct: 100, visivel: true, terminou: true });
    const some = window.setTimeout(() => setEstado((atual) => ({ ...atual, visivel: false })), 500);
    return () => window.clearTimeout(some);
  }, [ativo, chave, padraoMs]);

  return estado;
}
