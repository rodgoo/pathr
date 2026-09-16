/**
 * Liga o idioma da CONTA ao idioma da tela.
 *
 * Existe para `lib/i18n` não precisar conhecer sessão: ele recebe o idioma
 * pronto e não sabe de onde veio. Sem conta, vale o que o aparelho guardou (ou
 * o idioma do navegador, na primeira visita); com conta, vale o `locale` dela
 * — é isso que faz o idioma acompanhar a pessoa de um aparelho para outro.
 */

import type { ReactNode } from "react";
import { useAuth } from "@/hooks/useAuth";
import { IdiomaProvider, normalizarIdioma } from "@/lib/i18n";

export function IdiomaDoApp({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return <IdiomaProvider idioma={normalizarIdioma(user?.locale)}>{children}</IdiomaProvider>;
}
