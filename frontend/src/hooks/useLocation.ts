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

export interface Location {
  path: string;
  /** `?token=abc` já lido — é o único parâmetro que o app usa. */
  token: string;
}

function read(): Location {
  const url = new URL(window.location.href);
  return { path: url.pathname.replace(/\/+$/, "") || "/", token: url.searchParams.get("token") ?? "" };
}

export function useLocation(): [Location, (path: string) => void] {
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
    setLocation(read());
  }, []);

  return [location, navigate];
}
