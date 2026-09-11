/**
 * Entrada.
 *
 * O segundo fator não é uma tela separada: o backend responde 401 com o
 * cabeçalho `X-Pathr-Mfa: required`, e o formulário revela o campo do código
 * mantendo e-mail e senha preenchidos. Uma segunda tela obrigaria a repetir o
 * login se o código fosse digitado errado.
 *
 * O e-mail não confirmado é o outro caso especial: vem como 403 com
 * `X-Pathr-Unverified`, e a tela oferece reenviar o link em vez de deixar a
 * pessoa tentando a senha de novo — a senha estava certa.
 */

import { useState, type FormEvent } from "react";
import { auth as authApi } from "@/api/endpoints";
import { errorMessage, isEmailUnverified, isMfaRequired, useAuth } from "@/hooks/useAuth";
import { AuthShell, Field, PasswordField, FormError } from "@/components/auth/AuthShell";
import { chaveSuportada, mensagemDeErroDaChave, temChaveNesteAparelho } from "@/lib/passkeys";

export function LoginPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  const { login, loginWithPasskey } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [needsMfa, setNeedsMfa] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [unverified, setUnverified] = useState(false);
  const [resent, setResent] = useState<string | null>(null);
  const [passkeyPending, setPasskeyPending] = useState(false);
  // Quem já usou a chave neste aparelho vê a chave primeiro; quem nunca usou
  // vê a senha primeiro e a chave como alternativa. Decidido no aparelho
  // porque, antes do login, o servidor não pode dizer de quem é a conta.
  const suportada = chaveSuportada();
  const lembrada = suportada && temChaveNesteAparelho();

  async function resendVerification() {
    setResent(null);
    const { detail } = await authApi.resendVerificationPublic(email.trim());
    setResent(detail);
  }

  async function entrarComChave() {
    setPasskeyPending(true);
    setError(null);
    try {
      await loginWithPasskey();
    } catch (caught) {
      // Cancelar o pedido do Face ID ou da digital não é erro: fica quieto.
      setError(mensagemDeErroDaChave(caught));
    } finally {
      setPasskeyPending(false);
    }
  }

  const botaoDeChave = (principal: boolean) => (
    <button
      type="button"
      className={principal ? "btn btn-primary btn-block" : "btn btn-secondary btn-block"}
      style={principal ? undefined : { marginTop: 11.2 }}
      disabled={passkeyPending || pending}
      onClick={() => void entrarComChave()}
    >
      {passkeyPending ? "Aguardando o aparelho…" : "Entrar com chave de acesso"}
    </button>
  );

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setUnverified(false);
    setResent(null);
    try {
      await login(email, password, needsMfa ? mfaCode : undefined);
    } catch (caught) {
      if (isMfaRequired(caught)) {
        setNeedsMfa(true);
        setError(null);
      } else if (isEmailUnverified(caught)) {
        setUnverified(true);
        setError(errorMessage(caught));
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
      {lembrada ? (
        <>
          {botaoDeChave(true)}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8.4,
              margin: "14px 0",
              fontSize: 12,
              color: "rgba(233,233,237,.45)",
            }}
          >
            <span style={{ flex: 1, height: 1, background: "rgba(233,233,237,.14)" }} />
            ou entre com a senha
            <span style={{ flex: 1, height: 1, background: "rgba(233,233,237,.14)" }} />
          </div>
        </>
      ) : null}
      <form onSubmit={submit} noValidate>
        <FormError>{error}</FormError>

        {unverified ? (
          <div
            role="status"
            style={{
              margin: "0 0 11.2px",
              padding: "8.4px 11.2px",
              borderRadius: 8,
              background: "rgba(207,162,94,.12)",
              boxShadow: "inset 0 0 0 1px rgba(207,162,94,.35)",
              fontSize: 12.5,
            }}
          >
            {resent ? (
              resent
            ) : (
              <>
                Não recebeu o link?{" "}
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ fontSize: 12, padding: "2px 8px" }}
                  onClick={resendVerification}
                >
                  Reenviar confirmação
                </button>
              </>
            )}
          </div>
        ) : null}

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
        <PasswordField
          id="login-password"
          label="Senha"
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
      {suportada && !lembrada ? botaoDeChave(false) : null}
    </AuthShell>
  );
}
