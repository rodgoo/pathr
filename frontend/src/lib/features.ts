/**
 * Quais telas dependem de um feature flag para aparecer.
 *
 * O servidor resolve, por usuário, o mapa `{recurso: ligado}` (`GET /features`,
 * ligado em Todos / Admin / Ninguém na tela de Recursos). Aqui só se diz QUAL
 * recurso cada tela exige; a barra lateral, a navegação do celular e a guarda
 * de rota usam `telaLiberada` para esconder o que está desligado.
 *
 * Recurso novo com uma tela própria entra numa linha só aqui. A decisão de
 * acesso continua no backend — esconder na tela é conforto, não segurança: a
 * rota da API tem a sua própria checagem.
 */

import type { Screen } from "@/types";

const RECURSO_DA_TELA: Partial<Record<Screen, string>> = {
  candidaturas: "candidaturas",
};

export function telaLiberada(screen: Screen, features?: Record<string, boolean>): boolean {
  const recurso = RECURSO_DA_TELA[screen];
  return !recurso || Boolean(features?.[recurso]);
}
