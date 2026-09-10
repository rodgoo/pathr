import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

/**
 * Cada teste começa com o armazenamento vazio.
 *
 * O jsdom mantém UM `localStorage` para o arquivo inteiro. Desde que o estado
 * de interface passou a persistir (hooks/useAppState.tsx), um teste que
 * navegasse até a tela de currículo deixava o app apontado para lá, e o teste
 * seguinte montava já naquela tela em vez de na inicial — falhando por um
 * motivo que não tem nada a ver com o que ele verifica.
 *
 * Limpar aqui, e não em cada arquivo, porque a regra vale para todos: um teste
 * não deve herdar a posição deixada pelo anterior.
 */
beforeEach(() => {
  try {
    window.localStorage.clear();
  } catch {
    // Ambiente sem storage: nada a limpar.
  }
});
