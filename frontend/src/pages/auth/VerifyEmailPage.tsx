/**
 * Confirmação de e-mail, alcançada pelo link enviado no cadastro.
 *
 * Confirma assim que abre, sem botão: a pessoa já demonstrou intenção ao
 * clicar no link do próprio e-mail, e pedir mais um clique só adia.
 */

import { useEffect, useRef, useState } from "react";
import { auth as authApi } from "@/api/endpoints";
import { errorMessage, useAuth } from "@/hooks/useAuth";
import { AuthShell } from "@/components/auth/AuthShell";
import { Icon } from "@/components/ui/icons";
import { useT } from "@/lib/i18n";
import { C } from "@/lib/tokens";

type State = "verifying" | "ok" | "failed";

export function VerifyEmailPage({
  token,
  onNavigate,
}: {
  token: string;
  onNavigate: (path: string) => void;
}) {
  const t = useT();
  const { status, refresh } = useAuth();
  const [state, setState] = useState<State>(token ? "verifying" : "failed");
  const [message, setMessage] = useState("");

  // O token é de uso único: a primeira chamada o queima no banco. Sem esta
  // trava o efeito rodava duas vezes — `status` está nas dependências e vai
  // de "checking" para "anonymous" logo após a montagem —, e a segunda
  // chamada recebia "link inválido ou expirado" sobre o token que ela mesma
  // acabara de gastar. O e-mail era confirmado e a tela dizia que não.
  const jaTentado = useRef("");

  useEffect(() => {
    if (!token || jaTentado.current === token) return;
    jaTentado.current = token;
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
      <AuthShell title={t("auth.confirmacao.confirmando")} icon="mail">
        <p style={{ fontSize: 14, color: "rgba(233,233,237,.7)", margin: 0 }} aria-live="polite">
          {t("auth.confirmacao.umInstante")}
        </p>
      </AuthShell>
    );
  }

  if (state === "ok") {
    return (
      <AuthShell title={t("auth.confirmacao.confirmado")} icon="shieldCheck" subtitle={t("auth.confirmacao.tudoPronto")}>
        <p style={{ fontSize: 14, color: C.verde, margin: "0 0 16.8px" }}>
          {t("auth.confirmacao.contaAtiva")}
        </p>
        <button
          type="button"
          className="btn btn-primary btn-block"
          onClick={() => onNavigate(status === "authenticated" ? "/" : "/entrar")}
        >
          {status === "authenticated" ? t("auth.confirmacao.irParaOApp") : t("auth.login.titulo")}
          <Icon name="seta" size={17} className="auth-seta" />
        </button>
      </AuthShell>
    );
  }

  return (
    <AuthShell title={t("auth.confirmacao.naoDeu")} icon="info" subtitle={message || t("auth.confirmacao.semToken")}>
      <button
        type="button"
        className="btn btn-secondary btn-block"
        onClick={() => onNavigate(status === "authenticated" ? "/" : "/entrar")}
      >
        {status === "authenticated" ? t("auth.confirmacao.voltarAoApp") : t("auth.cadastro.irParaEntrar")}
      </button>
    </AuthShell>
  );
}
