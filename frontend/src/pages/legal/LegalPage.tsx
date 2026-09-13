/**
 * As três páginas legais, por endereço: /termos, /privacidade, /seguranca.
 *
 * App.tsx pergunta `ehPaginaLegal(path)` antes de olhar a sessão, então elas
 * abrem igual para visitante e para quem já entrou — e sem esperar a checagem
 * da sessão, que para ler um texto não importa.
 */

import { LegalLayout, type DocumentoLegal, type Navegar } from "./LegalLayout";
import { PRIVACIDADE } from "./Privacidade";
import { SEGURANCA } from "./Seguranca";
import { TERMOS } from "./Termos";

export const DOCUMENTOS_LEGAIS: DocumentoLegal[] = [TERMOS, PRIVACIDADE, SEGURANCA];

export function ehPaginaLegal(path: string): boolean {
  return DOCUMENTOS_LEGAIS.some((documento) => documento.path === path);
}

export function LegalPage({ path, onNavigate }: { path: string; onNavigate: Navegar }) {
  const documento = DOCUMENTOS_LEGAIS.find((item) => item.path === path) ?? TERMOS;
  return <LegalLayout documento={documento} documentos={DOCUMENTOS_LEGAIS} onNavigate={onNavigate} />;
}
