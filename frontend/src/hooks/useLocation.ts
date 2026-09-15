/**
 * Roteamento por caminho, mínimo.
 *
 * Existe por um motivo só: os links dos e-mails apontam para
 * `/confirmar-email?token=…` e `/nova-senha?token=…`, e esses endereços
 * precisam abrir a tela certa numa aba nova, sem sessão.
 *
 * Dentro do app a navegação continua sendo troca de tela em memória (ver
 * hooks/appState.ts) — nenhuma tela interna tem URL própria hoje, e inventar
 * rotas para todas significaria manter títulos, histórico e deep links que
 * ninguém pediu. Quando isso for preciso, este arquivo é o lugar de trocar
 * por um router de verdade.
 */

import { useCallback, useEffect, useState } from "react";
import { comTransicao } from "@/lib/transicao";

export interface Location {
  path: string;
  /** `?token=abc` já lido — é o único parâmetro que o app usa. */
  token: string;
}

function read(): Location {
  const url = new URL(window.location.href);
  return { path: url.pathname.replace(/\/+$/, "") || "/", token: url.searchParams.get("token") ?? "" };
}

export function useLocation(): [Location, (path: string) => void, (path: string) => void] {
  const [location, setLocation] = useState<Location>(read);

  // O botão voltar do navegador continua funcionando entre as telas de
  // autenticação, que são as únicas com endereço próprio.
  useEffect(() => {
    const onPop = () => setLocation(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((path: string) => {
    window.history.pushState({}, "", path);
    comTransicao(() => setLocation(read()));
  }, []);

  /** Troca o endereço sem criar passo no histórico, e sem transição.
   *
   * É para corrigir um endereço que deixou de ser verdade — não para navegar.
   * Com `pushState`, o botão voltar levaria de volta ao endereço errado; e a
   * transição de tela existe para acompanhar quem pediu para ir a outro
   * lugar, o que aqui não aconteceu: a tela é a mesma, só a barra de
   * endereços é que estava desatualizada. */
  const replace = useCallback((path: string) => {
    window.history.replaceState({}, "", path);
    setLocation(read());
  }, []);

  return [location, navigate, replace];
}
