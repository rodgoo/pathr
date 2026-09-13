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
import { AuthShell, Field, PasswordField, FormError } from "@/components/auth/AuthShell";
import { Icon } from "@/components/ui/icons";
import { C } from "@/lib/tokens";

export function ForgotPasswordPage({ onNavigate }: { onNavigate: (path: string) => void }) {
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
      title="Recuperar senha"
      icon="lock"
      subtitle={sent ? undefined : "Enviamos um link para você definir uma nova senha."}
      footer={
        <a href="/entrar" onClick={(e) => { e.preventDefault(); onNavigate("/entrar"); }}>
          Voltar para entrar
        </a>
      }
    >
      {sent ? (
        <p style={{ fontSize: 14, color: "rgba(233,233,237,.8)", margin: 0, lineHeight: 1.6 }}>
          Se houver conta com <strong>{email}</strong>, o link de recuperação já está a caminho.
          Ele vale por 1 hora.
        </p>
      ) : (
        <form onSubmit={submit} noValidate>
          <FormError>{error}</FormError>
          <Field
            id="forgot-email"
            label="E-mail da conta"
            icon="mail"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <button type="submit" className="btn btn-primary btn-block" disabled={pending}>
            {pending ? null : <Icon name="send" size={17} />}
            {pending ? "Enviando…" : "Enviar link"}
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
      <AuthShell title="Link inválido" icon="info" subtitle="Este endereço não traz um token de recuperação.">
        <button
          type="button"
          className="btn btn-primary btn-block"
          onClick={() => onNavigate("/recuperar-senha")}
        >
          Pedir um novo link
        </button>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Nova senha" icon="shieldCheck" subtitle={done ? undefined : "Escolha uma senha que você não usa em outro lugar."}>
      {done ? (
        <div>
          <p style={{ fontSize: 14, color: C.verde, margin: "0 0 14px" }}>Senha alterada.</p>
          <p style={{ fontSize: 13, color: "rgba(233,233,237,.7)", margin: "0 0 16.8px" }}>
            Por segurança, todas as sessões abertas foram encerradas.
          </p>
          <button
            type="button"
            className="btn btn-primary btn-block"
            onClick={() => onNavigate("/entrar")}
          >
            Entrar com a nova senha
            <Icon name="seta" size={17} className="auth-seta" />
          </button>
        </div>
      ) : (
        <form onSubmit={submit} noValidate>
          <FormError>{error}</FormError>
          <PasswordField
            id="reset-password"
            label="Nova senha"
            icon="lock"
            autoComplete="new-password"
            hint="Ao menos 10 caracteres, com letra e número."
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <button type="submit" className="btn btn-primary btn-block" disabled={pending}>
            {pending ? "Salvando…" : "Salvar senha"}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
