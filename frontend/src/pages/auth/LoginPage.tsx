/**
 * Entrada.
 *
 * O segundo fator não é uma tela separada: o backend responde 401 com o
 * cabeçalho `X-Pathr-Mfa: required`, e o formulário revela o campo do código
 * mantendo e-mail e senha preenchidos. Uma segunda tela obrigaria a repetir o
 * login se o código fosse digitado errado.
 */

import { useState, type FormEvent } from "react";
import { errorMessage, isMfaRequired, useAuth } from "@/hooks/useAuth";
import { AuthShell, Field, FormError } from "@/components/auth/AuthShell";

export function LoginPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [needsMfa, setNeedsMfa] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await login(email, password, needsMfa ? mfaCode : undefined);
    } catch (caught) {
      if (isMfaRequired(caught)) {
        setNeedsMfa(true);
        setError(null);
      } else {
        setError(errorMessage(caught));
        setMfaCode("");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthShell
      title="Entrar"
      subtitle="Seu plano de estudos continua de onde parou."
      footer={
        <>
          Ainda não tem conta?{" "}
          <a href="/cadastro" onClick={(e) => { e.preventDefault(); onNavigate("/cadastro"); }}>
            Criar conta
          </a>
        </>
      }
    >
      <form onSubmit={submit} noValidate>
        <FormError>{error}</FormError>

        <Field
          id="login-email"
          label="E-mail"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={needsMfa}
        />
        <Field
          id="login-password"
          label="Senha"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={needsMfa}
        />

        {needsMfa ? (
          <Field
            id="login-mfa"
            label="Código do autenticador"
            hint="Seis dígitos do app, ou um código de backup."
            inputMode="numeric"
            autoComplete="one-time-code"
            autoFocus
            required
            value={mfaCode}
            onChange={(event) => setMfaCode(event.target.value)}
          />
        ) : null}

        <button type="submit" className="btn btn-primary btn-block" disabled={pending}>
          {pending ? "Entrando…" : needsMfa ? "Confirmar código" : "Entrar"}
        </button>

        <div style={{ marginTop: 11.2, textAlign: "center" }}>
          <a
            href="/recuperar-senha"
            style={{ fontSize: 12.5 }}
            onClick={(e) => { e.preventDefault(); onNavigate("/recuperar-senha"); }}
          >
            Esqueci minha senha
          </a>
        </div>
      </form>
    </AuthShell>
  );
}
