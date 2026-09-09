/**
 * Confirmação de e-mail, alcançada pelo link enviado no cadastro.
 *
 * Confirma assim que abre, sem botão: a pessoa já demonstrou intenção ao
 * clicar no link do próprio e-mail, e pedir mais um clique só adia.
 */

import { useEffect, useState } from "react";
import { auth as authApi } from "@/api/endpoints";
import { errorMessage, useAuth } from "@/hooks/useAuth";
import { AuthShell } from "@/components/auth/AuthShell";
import { C } from "@/lib/tokens";

type State = "verifying" | "ok" | "failed";

export function VerifyEmailPage({
  token,
  onNavigate,
}: {
  token: string;
  onNavigate: (path: string) => void;
}) {
  const { status, refresh } = useAuth();
  const [state, setState] = useState<State>(token ? "verifying" : "failed");
  const [message, setMessage] = useState("Este endereço não traz um token de confirmação.");

  useEffect(() => {
    if (!token) return;
    let alive = true;
    authApi
      .verifyEmail(token)
      .then(async () => {
        if (!alive) return;
        setState("ok");
        // Recarrega quem está logado: `email_verified` acabou de mudar, e as
        // telas que dependem dele precisam saber.
        if (status === "authenticated") await refresh();
      })
      .catch((caught) => {
        if (!alive) return;
        setState("failed");
        setMessage(errorMessage(caught));
      });
    return () => {
      alive = false;
    };
  }, [token, status, refresh]);

  if (state === "verifying") {
    return (
      <AuthShell title="Confirmando…">
        <p style={{ fontSize: 14, color: "rgba(233,233,237,.7)", margin: 0 }} aria-live="polite">
          Um instante.
        </p>
      </AuthShell>
    );
  }

  if (state === "ok") {
    return (
      <AuthShell title="E-mail confirmado" subtitle="Tudo pronto para começar.">
        <p style={{ fontSize: 14, color: C.verde, margin: "0 0 16.8px" }}>
          Sua conta está ativa.
        </p>
        <button
          type="button"
          className="btn btn-primary btn-block"
          onClick={() => onNavigate(status === "authenticated" ? "/" : "/entrar")}
        >
          {status === "authenticated" ? "Ir para o app" : "Entrar"}
        </button>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Não deu para confirmar" subtitle={message}>
      <button
        type="button"
        className="btn btn-secondary btn-block"
        onClick={() => onNavigate(status === "authenticated" ? "/" : "/entrar")}
      >
        {status === "authenticated" ? "Voltar ao app" : "Ir para entrar"}
      </button>
    </AuthShell>
  );
}

/**
 * Faixa de aviso para quem entrou mas ainda não confirmou o e-mail.
 *
 * Aparece dentro do app, não no lugar dele: a pessoa pode olhar em volta e
 * decidir se vale a pena confirmar — bloquear tudo antes disso é o caminho
 * mais curto para o abandono.
 */
export function UnverifiedBanner() {
  const { user, refresh } = useAuth();
  const [sent, setSent] = useState(false);
  const [pending, setPending] = useState(false);

  if (!user || user.email_verified) return null;

  async function resend() {
    setPending(true);
    try {
      await authApi.resendVerification();
      setSent(true);
      await refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <div
      role="status"
      style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: 11.2,
        padding: "8.4px 14px",
        borderRadius: 8,
        background: "rgba(207,162,94,.12)",
        boxShadow: "inset 0 0 0 1px rgba(207,162,94,.35)",
        fontSize: 12.5,
      }}
    >
      <span style={{ flex: 1, minWidth: 220 }}>
        {sent
          ? `Reenviamos o link de confirmação para ${user.email}.`
          : `Confirme ${user.email} para liberar o plano completo.`}
      </span>
      {!sent ? (
        <button type="button" className="btn btn-ghost" style={{ fontSize: 12 }} onClick={resend} disabled={pending}>
          {pending ? "Enviando…" : "Reenviar e-mail"}
        </button>
      ) : null}
    </div>
  );
}
