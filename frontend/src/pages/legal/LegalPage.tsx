/**
 * As três páginas legais, por endereço: /termos, /privacidade, /seguranca.
 *
 * App.tsx pergunta `ehPaginaLegal(path)` antes de olhar a sessão, então elas
 * abrem igual para visitante e para quem já entrou — e sem esperar a checagem
 * da sessão, que para ler um texto não importa.
 *
 * Os documentos são montados a cada desenho, com o `t` do idioma em vigor:
 * trocar de idioma no seletor reescreve os três na hora. O `ehPaginaLegal`, que
 * roda fora de qualquer componente, olha só os endereços — que não mudam com o
 * idioma.
 */

import { useMemo } from "react";
import { useT } from "@/lib/i18n";
import { LegalLayout, type DocumentoLegal, type Navegar } from "./LegalLayout";
import { CAMINHO_PRIVACIDADE, privacidade } from "./Privacidade";
import { CAMINHO_SEGURANCA, seguranca } from "./Seguranca";
import { CAMINHO_TERMOS, termos } from "./Termos";

export const CAMINHOS_LEGAIS = [CAMINHO_TERMOS, CAMINHO_PRIVACIDADE, CAMINHO_SEGURANCA];

export function ehPaginaLegal(path: string): boolean {
  return CAMINHOS_LEGAIS.includes(path);
}

export function LegalPage({ path, onNavigate }: { path: string; onNavigate: Navegar }) {
  const t = useT();
  const documentos = useMemo<DocumentoLegal[]>(() => [termos(t), privacidade(t), seguranca(t)], [t]);
  const documento = documentos.find((item) => item.path === path) ?? documentos[0];
  return <LegalLayout documento={documento} documentos={documentos} onNavigate={onNavigate} />;
}
