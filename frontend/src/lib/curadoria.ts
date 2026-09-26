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

/**
 * As buscas desta sessão, por módulo — em andamento OU já terminadas. Zera ao recarregar a página.
 *
 * Guarda a PROMESSA, e não só "já tentei": quem chega depois precisa do resultado, não de um "false"
 * imediato. Ao concluir um módulo o app dispara a busca do próximo NA HORA e, um instante depois, a aba de
 * material do próximo monta e pergunta de novo. Com um `Set`, a segunda pergunta voltava `false` de
 * imediato: o indicador de "procurando" sumia e, quando a primeira busca terminava, ninguém recarregava a
 * lista — o material chegava e não aparecia. Devolvendo a mesma promessa, as duas esperam a mesma busca.
 */
const buscas = new Map<string, Promise<boolean>>();

/**
 * Procura material para `nodeId`. Devolve `true` quando algo novo entrou.
 *
 * Nunca lança: é uma melhoria de fundo, e uma falha aqui não pode derrubar a
 * tela que a disparou. Quem precisar do erro visível usa o botão manual, que
 * continua existindo em `CurateButton`.
 */
export function curarModulo(nodeId: string): Promise<boolean> {
  const existente = buscas.get(nodeId);
  if (existente) return existente;
  const busca = (async () => {
    try {
      const { novos } = await libraryApi.curate(nodeId);
      return novos > 0;
    } catch (erro) {
      // Falta de rede merece outra chance quando ela voltar. Uma recusa do
      // servidor (cota, "buscamos há pouco") não merece: insistir só repetiria
      // a mesma resposta.
      if (isNetworkError(erro)) buscas.delete(nodeId);
      return false;
    }
  })();
  buscas.set(nodeId, busca);
  return busca;
}

/** Só para os testes: esquece o que já foi tentado. */
export function resetCuradoriaForTests(): void {
  buscas.clear();
}
