/**
 * "Tem novidade em Amigos": o item da navegação pisca até a pessoa abrir a tela.
 *
 * Liga quando chega um convite ou um aceite (components/social/AvisosDeAmizade)
 * e desliga quando a tela Amigos abre. Fica no navegador para sobreviver a um
 * F5 — o pop-up já sumiu, e sem isso a novidade se perderia.
 */

import { useSyncExternalStore } from "react";

const CHAVE = "pathr:amigos:novidade";
const ouvintes = new Set<() => void>();

function ler(): boolean {
  try {
    return window.localStorage.getItem(CHAVE) === "1";
  } catch {
    return false;
  }
}

let memoria = typeof window === "undefined" ? false : ler();

function gravar(valor: boolean): void {
  try {
    if (valor) window.localStorage.setItem(CHAVE, "1");
    else window.localStorage.removeItem(CHAVE);
  } catch {
    // Armazenamento bloqueado: pisca só nesta aba.
  }
  memoria = valor;
  ouvintes.forEach((ouvir) => ouvir());
}

export const avisoAmigos = {
  ligar: () => gravar(true),
  desligar: () => {
    if (memoria) gravar(false);
  },
  get: () => memoria,
  subscribe: (ouvir: () => void) => {
    ouvintes.add(ouvir);
    return () => {
      ouvintes.delete(ouvir);
    };
  },
};

export function useAmigosPiscando(): boolean {
  return useSyncExternalStore(avisoAmigos.subscribe, avisoAmigos.get, () => false);
}
