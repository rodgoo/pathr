/**
 * A busca de material, disparada pelo app em vez de por um botão.
 *
 * O produto promete um roadmap COM material. Um plano recém-gerado cujos
 * módulos abrem vazios, com um botão dizendo "procure você", entrega metade
 * do que prometeu — e a pessoa que acabou de descrever o objetivo dela é
 * justamente quem menos deveria ter que caçar links.
 *
 * Então a curadoria roda sozinha em dois momentos: assim que um plano é
 * gerado (para o módulo atual) e ao abrir um módulo que ainda não tem nada.
 *
 * **Uma vez por módulo, por sessão.** A chamada custa caro do outro lado —
 * são duas APIs externas mais a verificação de cada link — e o backend já
 * responde "buscamos há pouco" quando insistem. Repetir a cada render, ou a
 * cada ida e volta entre abas, gastaria cota para receber a mesma recusa.
 */

import { library as libraryApi } from "@/api/endpoints";
import { isNetworkError } from "@/api/errors";

/** Módulos já tentados nesta sessão. Zera ao recarregar a página. */
const tentados = new Set<string>();

/**
 * Procura material para `nodeId`. Devolve `true` quando algo novo entrou.
 *
 * Nunca lança: é uma melhoria de fundo, e uma falha aqui não pode derrubar a
 * tela que a disparou. Quem precisar do erro visível usa o botão manual, que
 * continua existindo em `CurateButton`.
 */
export async function curarModulo(nodeId: string): Promise<boolean> {
  if (tentados.has(nodeId)) return false;
  tentados.add(nodeId);
  try {
    const { novos } = await libraryApi.curate(nodeId);
    return novos > 0;
  } catch (erro) {
    // Falta de rede merece outra chance quando ela voltar. Uma recusa do
    // servidor (cota, "buscamos há pouco") não merece: insistir só repetiria
    // a mesma resposta.
    if (isNetworkError(erro)) tentados.delete(nodeId);
    return false;
  }
}

/** Só para os testes: esquece o que já foi tentado. */
export function resetCuradoriaForTests(): void {
  tentados.clear();
}
