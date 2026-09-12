/**
 * Contexto do estado de interface, que sobrevive a recarregar a página.
 *
 * O estado era React puro: sair de um módulo e voltar — ou só apertar F5 —
 * devolvia tudo ao `INITIAL_STATE`. A pessoa perdia a tela em que estava, o
 * módulo aberto, o quiz em andamento e os filtros da biblioteca de uma vez, o
 * que num app de estudo é o mesmo que mandá-la recomeçar.
 *
 * Agora o reducer grava no `localStorage` a cada mudança e relê na abertura.
 * `localStorage` e não `sessionStorage` de propósito: quem fecha o navegador à
 * noite e volta no dia seguinte quer continuar de onde parou, e é justamente
 * essa a promessa do produto.
 *
 * Três cuidados que não são opcionais aqui:
 *
 * 1. **A chave é versionada.** O estado guardado tem a forma de HOJE; quando
 *    um campo mudar de tipo, `_VERSAO` sobe e o que está gravado é descartado
 *    em vez de hidratar a interface com dado que ela não entende mais.
 * 2. **O que voltar é MESCLADO ao padrão.** Um campo novo no código não existe
 *    no que foi gravado ontem, e ler `undefined` num `state.libraryFilter`
 *    quebraria a tela — o padrão preenche a lacuna.
 * 3. **Tudo em try/catch.** Navegador em janela anônima, ou com armazenamento
 *    bloqueado, lança na primeira leitura. Perder a posição é um incômodo;
 *    não abrir o app é um defeito.
 */

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from "react";
import { INITIAL_STATE, reducer, type Action, type AppState } from "./appState";
import type { Screen } from "@/types";

const _VERSAO = 1;
const CHAVE = `pathr:ui:v${_VERSAO}`;

interface AppContextValue {
  state: AppState;
  dispatch: Dispatch<Action>;
}

const AppContext = createContext<AppContextValue | null>(null);

/**
 * Destinos que não existem mais, e para onde o que estava neles vai.
 *
 * A Biblioteca era uma tela do menu e virou a aba de material do módulo. Quem
 * fechou o app nela tem `screen: "biblioteca"` gravado — um destino que o
 * roteador não conhece mais, e que abriria o app numa tela em branco.
 *
 * Mapear é melhor do que subir a versão da chave e descartar tudo: o que se
 * perderia junto seria o módulo aberto, os filtros e a posição de quem não
 * tem nada a ver com esta mudança.
 */
const APOSENTADOS: Record<string, Screen> = { biblioteca: "modulo" };

function destinoValido(screen: unknown): Screen | null {
  return typeof screen === "string" && screen in APOSENTADOS ? APOSENTADOS[screen] : null;
}

/** O que está gravado, mesclado ao padrão. O padrão sozinho se não der. */
function hidratar(padrao: AppState): AppState {
  try {
    const bruto = window.localStorage.getItem(CHAVE);
    if (!bruto) return padrao;
    const guardado = JSON.parse(bruto) as Partial<AppState>;
    const estado = { ...padrao, ...guardado };
    return {
      ...estado,
      screen: destinoValido(estado.screen) ?? estado.screen,
      resourceReturn: destinoValido(estado.resourceReturn) ?? estado.resourceReturn,
    };
  } catch {
    return padrao;
  }
}

export function AppStateProvider({
  children,
  initialState = INITIAL_STATE,
}: {
  children: ReactNode;
  initialState?: AppState;
}) {
  // Inicializador preguiçoso: a leitura do storage acontece uma vez, na
  // montagem, e não a cada render.
  const [state, dispatch] = useReducer(reducer, initialState, hidratar);

  useEffect(() => {
    try {
      window.localStorage.setItem(CHAVE, JSON.stringify(state));
    } catch {
      // Armazenamento cheio ou bloqueado. O app segue funcionando em memória.
    }
  }, [state]);

  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppState(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("useAppState must be used inside an AppStateProvider");
  return value;
}

/**
 * Apaga a posição guardada.
 *
 * Chamado ao sair da conta: a próxima pessoa a usar este navegador não deve
 * abrir o app no módulo de quem estava antes — e, num computador
 * compartilhado, o título do módulo já é informação demais.
 */
export function limparEstadoGuardado(): void {
  try {
    window.localStorage.removeItem(CHAVE);
    // O progresso de quiz e o rascunho de atividade vivem em chaves próprias,
    // pelo mesmo motivo: são de quem estava logado, não do navegador.
    for (let i = window.localStorage.length - 1; i >= 0; i -= 1) {
      const chave = window.localStorage.key(i);
      if (chave && chave.startsWith("pathr:")) window.localStorage.removeItem(chave);
    }
  } catch {
    // Nada a fazer, e nada que justifique interromper o logout.
  }
}
