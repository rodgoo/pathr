/**
 * Sessão do usuário.
 *
 * Separado do estado da aplicação (useAppState) de propósito: a sessão decide
 * SE o app é renderizado, e o estado do app descreve o que ele mostra. Juntar
 * os dois faria toda tela ter que lidar com "e se não houver usuário".
 *
 * O token não é guardado aqui nem em lugar nenhum acessível ao JavaScript —
 * ele vive no cookie HttpOnly. O que este contexto guarda é só quem é a
 * pessoa, e isso vem de `GET /auth/me`.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { auth as authApi } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type { User } from "@/api/types";

type Status = "checking" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: Status;
  user: User | null;
  login: (email: string, password: string, mfaCode?: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Recarrega o usuário depois de uma mudança (nome, e-mail confirmado). */
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("checking");
  const [user, setUser] = useState<User | null>(null);

  const load = useCallback(async () => {
    try {
      const current = await authApi.me();
      setUser(current);
      setStatus("authenticated");
    } catch {
      // Qualquer falha aqui — 401, rede fora — significa "não logado" para o
      // app. Um erro de rede mostra a tela de entrada, e tentar de novo é o
      // próprio botão de entrar.
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  // Na montagem: há sessão viva no cookie? O cliente tenta renovar sozinho
  // antes de desistir, então um access token expirado não desloga ninguém.
  useEffect(() => {
    void load();
  }, [load]);

  const login = useCallback(async (email: string, password: string, mfaCode?: string) => {
    const session = await authApi.login({ email, password, mfa_code: mfaCode });
    setUser(session.user);
    setStatus("authenticated");
  }, []);

  const signup = useCallback(async (name: string, email: string, password: string) => {
    const session = await authApi.signup({ name, email, password });
    setUser(session.user);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      // Mesmo se a chamada falhar, o estado local vira anônimo: o cookie pode
      // já ter expirado, e deixar a pessoa presa numa tela logada sem sessão
      // é pior que um logout local sem confirmação do servidor.
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  const value = useMemo(
    () => ({ status, user, login, signup, logout, refresh: load }),
    [status, user, login, signup, logout, load],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth precisa estar dentro de AuthProvider");
  return value;
}

/** `true` quando o erro é o backend pedindo o segundo fator. */
export const isMfaRequired = (error: unknown): boolean =>
  error instanceof ApiError && error.mfaRequired;

/** Mensagem pronta para exibir a partir de qualquer erro. */
export const errorMessage = (error: unknown): string =>
  error instanceof ApiError
    ? error.message
    : "Não consegui falar com o servidor. Verifique sua conexão.";
