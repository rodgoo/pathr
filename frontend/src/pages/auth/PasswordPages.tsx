/**
 * Recuperação de senha, em duas telas.
 *
 * A primeira responde SEMPRE a mesma coisa, exista a conta ou não — a
 * resposta não pode virar uma forma de descobrir quem tem cadastro. A
 * segunda recebe o token pela URL do e-mail.
 */

import { useState, type FormEvent } from "react";
import { auth as authApi } from "@/api/endpoints";
import { errorMessage } from "@/hooks/useAuth";
import { useT } from "@/lib/i18n";
import { AuthShell, Field, PasswordField, FormError } from "@/components/auth/AuthShell";
import { Icon } from "@/components/ui/icons";
import { C } from "@/lib/tokens";

export function ForgotPasswordPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  const t = useT();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await authApi.forgotPassword(email.trim());
      setSent(true);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthShell
      title={t("auth.recuperar.titulo")}
      icon="lock"
      subtitle={sent ? undefined : t("auth.recuperar.sub")}
      footer={
        <a href="/entrar" onClick={(e) => { e.preventDefault(); onNavigate("/entrar"); }}>
          {t("auth.recuperar.voltar")}
        </a>
      }
    >
      {sent ? (
        <p style={{ fontSize: 14, color: "rgba(233,233,237,.8)", margin: 0, lineHeight: 1.6 }}>
          {t("auth.recuperar.seHouver")} <strong>{email}</strong>{t("auth.recuperar.aCaminho")}
        </p>
      ) : (
        <form onSubmit={submit} noValidate>
          <FormError>{error}</FormError>
          <Field
            id="forgot-email"
            label={t("auth.recuperar.emailDaConta")}
            icon="mail"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <button type="submit" className="btn btn-primary btn-block" disabled={pending}>
            {pending ? null : <Icon name="send" size={17} />}
            {pending ? t("auth.recuperar.enviando") : t("auth.recuperar.enviarLink")}
          </button>
        </form>
      )}
    </AuthShell>
  );
}

export function ResetPasswordPage({
  token,
  onNavigate,
}: {
  token: string;
  onNavigate: (path: string) => void;
}) {
  const [password, setPassword] = useState("");
  const t = useT();
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await authApi.resetPassword(token, password);
      setDone(true);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setPending(false);
    }
  }

  if (!token) {
    return (
      <AuthShell title={t("auth.novaSenha.linkInvalido")} icon="info" subtitle={t("auth.novaSenha.semToken")}>
        <button
          type="button"
          className="btn btn-primary btn-block"
          onClick={() => onNavigate("/recuperar-senha")}
        >
          {t("auth.novaSenha.pedirNovoLink")}
        </button>
      </AuthShell>
    );
  }

  return (
    <AuthShell title={t("auth.novaSenha.titulo")} icon="shieldCheck" subtitle={done ? undefined : t("auth.novaSenha.sub")}>
      {done ? (
        <div>
          <p style={{ fontSize: 14, color: C.verde, margin: "0 0 14px" }}>{t("auth.novaSenha.senhaAlterada")}</p>
          <p style={{ fontSize: 13, color: "rgba(233,233,237,.7)", margin: "0 0 16.8px" }}>
            {t("auth.novaSenha.sessoesEncerradas")}
          </p>
          <button
            type="button"
            className="btn btn-primary btn-block"
            onClick={() => onNavigate("/entrar")}
          >
            {t("auth.novaSenha.entrarComNova")}
            <Icon name="seta" size={17} className="auth-seta" />
          </button>
        </div>
      ) : (
        <form onSubmit={submit} noValidate>
          <FormError>{error}</FormError>
          <PasswordField
            id="reset-password"
            label={t("auth.novaSenha.titulo")}
            icon="lock"
            autoComplete="new-password"
            hint={t("auth.novaSenha.dica")}
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <button type="submit" className="btn btn-primary btn-block" disabled={pending}>
            {pending ? t("auth.novaSenha.salvando") : t("auth.novaSenha.salvar")}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
