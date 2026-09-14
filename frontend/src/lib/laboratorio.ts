/**
 * Abrir um exemplo no depurador do Laboratório, de qualquer tela.
 *
 * O Laboratório lembra o exemplo aberto em `localStorage` (a mesma chave que
 * ele sempre usou). Gravar ali e navegar para a tela basta quando ela ainda
 * não está montada; o evento cobre o caso de já estar — a tela troca o
 * exemplo aberto sem recarregar.
 */

export const CHAVE_DO_LABORATORIO = "pathr:codigo";
export const EVENTO_ABRIR_EXEMPLO = "pathr:abrir-exemplo";

export function abrirExemploNoLaboratorio(id: string): void {
  try {
    window.localStorage.setItem(CHAVE_DO_LABORATORIO, JSON.stringify({ id, passo: 0 }));
  } catch {
    // Sem armazenamento: o evento ainda abre, se a tela estiver montada.
  }
  window.dispatchEvent(new CustomEvent<string>(EVENTO_ABRIR_EXEMPLO, { detail: id }));
}
