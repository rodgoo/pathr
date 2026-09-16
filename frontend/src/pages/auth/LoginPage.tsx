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
import { Icon } from "@/components/ui/icons";
import { useT } from "@/lib/i18n";
import { chaveSuportada, mensagemDeErroDaChave, temChaveNesteAparelho } from "@/lib/passkeys";

export function LoginPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  const t = useT();
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
      className={principal ? "btn btn-primary btn-block" : "btn btn-chave btn-block"}
      disabled={passkeyPending || pending}
      onClick={() => void entrarComChave()}
    >
      <Icon name="fingerprint" size={18} />
      {passkeyPending ? t("auth.login.aguardandoAparelho") : t("auth.login.entrarComChave")}
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
      title={t("auth.login.titulo")}
      icon="logIn"
      subtitle={t("auth.login.sub")}
      footer={
        <>
          {t("auth.login.semConta")}{" "}
          <a href="/cadastro" onClick={(e) => { e.preventDefault(); onNavigate("/cadastro"); }}>
            {t("auth.login.criarConta")}
          </a>
        </>
      }
    >
      {lembrada ? (
        <>
          {botaoDeChave(true)}
          <div className="auth-divisor" style={{ margin: "16px 0 14px" }}>{t("auth.login.ouSenha")}</div>
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
                {t("auth.login.semLink")}{" "}
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ fontSize: 12, padding: "2px 8px" }}
                  onClick={resendVerification}
                >
                  {t("auth.login.reenviar")}
                </button>
              </>
            )}
          </div>
        ) : null}

        <Field
          id="login-email"
          label={t("auth.campos.email")}
          icon="mail"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={needsMfa}
        />
        <PasswordField
          id="login-password"
          label={t("auth.campos.senha")}
          icon="lock"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={needsMfa}
        />

        {needsMfa ? (
          <Field
            id="login-mfa"
            label={t("auth.login.codigo")}
            hint={t("auth.login.codigoDica")}
            inputMode="numeric"
            autoComplete="one-time-code"
            autoFocus
            required
            value={mfaCode}
            onChange={(event) => setMfaCode(event.target.value)}
          />
        ) : null}

        <button
          type="submit"
          // Quem já usa a chave neste aparelho tem a chave como ação cheia;
          // a senha vira a alternativa, e dois botões cheios competiriam.
          className={lembrada ? "btn btn-secondary btn-block" : "btn btn-primary btn-block"}
          disabled={pending}
        >
          {pending ? t("auth.login.entrando") : needsMfa ? t("auth.login.confirmarCodigo") : t("auth.login.titulo")}
          {pending ? null : <Icon name="seta" size={17} className="auth-seta" />}
        </button>

        <div style={{ marginTop: 12, textAlign: "center" }}>
          <a
            href="/recuperar-senha"
            className="auth-link-menor"
            onClick={(e) => { e.preventDefault(); onNavigate("/recuperar-senha"); }}
          >
            {t("auth.login.esqueci")}
          </a>
        </div>
      </form>
      {suportada && !lembrada ? (
        <>
          <div className="auth-divisor" aria-hidden="true">{t("auth.login.ou")}</div>
          {botaoDeChave(false)}
        </>
      ) : null}
    </AuthShell>
  );
}
