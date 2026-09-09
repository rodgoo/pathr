/**
 * Contexto do estado de interface.
 *
 * Ficou fino depois que os dados saíram para o servidor: é o reducer, e só.
 * Os temporizadores que simulavam leitura de currículo e geração de plano
 * foram embora junto com os dados de exemplo — agora essas duas coisas são
 * requisições de verdade, e quem espera por elas é o `useMutation` da tela.
 */

import { createContext, useContext, useMemo, useReducer, type Dispatch, type ReactNode } from "react";
import { INITIAL_STATE, reducer, type Action, type AppState } from "./appState";

interface AppContextValue {
  state: AppState;
  dispatch: Dispatch<Action>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppStateProvider({
  children,
  initialState = INITIAL_STATE,
}: {
  children: ReactNode;
  initialState?: AppState;
}) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppState(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("useAppState must be used inside an AppStateProvider");
  return value;
}
