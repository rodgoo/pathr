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
import { startAuthentication } from "@simplewebauthn/browser";
import { auth as authApi, passkeys as passkeysApi } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { clearReads } from "@/offline/cache";
import type { User } from "@/api/types";
import { limparEstadoGuardado } from "./useAppState";
import { esquecerVagas } from "@/lib/vagasGuardadas";
import { lembrarChave } from "@/lib/passkeys";

type Status = "checking" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: Status;
  user: User | null;
  login: (email: string, password: string, mfaCode?: string) => Promise<void>;
  signup: (body: {
    name: string;
    email: string;
    password: string;
    birth_date: string;
    city: string;
    state: string;
    username?: string;
  }) => Promise<string>;
  /** Entra pela chave de acesso do aparelho. Não pede e-mail: a chave diz quem é. */
  loginWithPasskey: () => Promise<void>;
  logout: () => Promise<void>;
  /** Recarrega o usuário depois de uma mudança (nome, e-mail confirmado). */
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("checking");
  const [user, setUser] = useState<User | null>(null);

  const load = useCallback(async () => {
    // Só um "não autenticado" do servidor (401/403) desloga. Rede caindo, a
    // máquina da API reiniciando num deploy ou um 5xx passageiro NÃO são
    // logout: antes, qualquer falha aqui mandava a pessoa para a tela de
    // entrar, e um deploy no meio do uso parecia uma sessão encerrada do nada.
    // Tenta de novo algumas vezes antes de desistir.
    const esperas = [0, 1500, 4000, 9000];
    for (let tentativa = 0; tentativa < esperas.length; tentativa += 1) {
      if (esperas[tentativa]) await new Promise((r) => setTimeout(r, esperas[tentativa]));
      try {
        const current = await authApi.me();
        setUser(current);
        setStatus("authenticated");
        return;
      } catch (erro) {
        if (erro instanceof ApiError && (erro.status === 401 || erro.status === 403)) break;
      }
    }
    setUser(null);
    setStatus("anonymous");
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

  const loginWithPasskey = useCallback(async () => {
    const pedido = await passkeysApi.loginOptions();
    const credencial = await startAuthentication({
      optionsJSON: pedido.options as unknown as Parameters<typeof startAuthentication>[0]["optionsJSON"],
    });
    const session = await passkeysApi.loginVerify(pedido.challenge_id, credencial);
    // Deu certo aqui: na próxima vez, a tela de entrada oferece a chave primeiro.
    lembrarChave();
    setUser(session.user);
    setStatus("authenticated");
  }, []);

  // Não muda o estado de sessão: o cadastro não loga mais ninguém. Quem
  // acabou de criar conta segue anônimo até confirmar o e-mail, e a tela de
  // cadastro mostra a mensagem devolvida aqui.
  const signup = useCallback(
    async (body: {
      name: string;
      email: string;
      password: string;
      birth_date: string;
      city: string;
      state: string;
      username?: string;
    }) => {
      const { detail } = await authApi.signup(body);
      return detail;
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      // Mesmo se a chamada falhar, o estado local vira anônimo: o cookie pode
      // já ter expirado, e deixar a pessoa presa numa tela logada sem sessão
      // é pior que um logout local sem confirmação do servidor.
      //
      // A posição guardada sai junto. Num computador compartilhado, abrir o
      // app no módulo de quem saiu já é informação demais — e o proximo login
      // deve começar na tela inicial, não no meio do estudo de outra pessoa.
      limparEstadoGuardado();
      esquecerVagas();
      setUser(null);
      setStatus("anonymous");
      // O conteúdo guardado para uso offline sai do aparelho junto. A FILA de
      // escritas fica: ela é do usuário que a criou e só é enviada quando ele
      // voltar — quem marcou módulos sem rede e emprestou o telefone não deve
      // perder o que fez.
      void clearReads();
    }
  }, []);

  const value = useMemo(
    () => ({ status, user, login, loginWithPasskey, signup, logout, refresh: load }),
    [status, user, login, loginWithPasskey, signup, logout, load],
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

/** O login foi recusado só porque o e-mail ainda não foi confirmado. */
export const isEmailUnverified = (error: unknown): boolean =>
  error instanceof ApiError && error.emailUnverified;

/** Mensagem pronta para exibir a partir de qualquer erro. */
export const errorMessage = (error: unknown): string =>
  error instanceof ApiError
    ? error.message
    : "Não consegui falar com o servidor. Verifique sua conexão.";
