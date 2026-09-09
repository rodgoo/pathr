/**
 * Moldura das telas de entrada.
 *
 * Um cartão centrado sobre o fundo do app, com a marca em cima. Diferente do
 * AppShell de propósito: aqui não existe navegação, e mostrar uma barra
 * lateral com links que a pessoa ainda não pode abrir só confunde.
 */

import type { ReactNode } from "react";
import { BG, PANEL, TEXT } from "@/lib/tokens";
import { Logo } from "@/components/ui/Logo";

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: BG,
        color: TEXT.full,
        fontFamily: "Inter, system-ui, sans-serif",
        display: "grid",
        placeItems: "center",
        padding: 22.4,
      }}
    >
      <div style={{ width: "min(420px, 100%)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8.4, marginBottom: 22.4 }}>
          <Logo size={32} />
          <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.15 }}>
            <span style={{ fontSize: 16, fontWeight: 500 }}>PathR</span>
            <span style={{ fontSize: 10, letterSpacing: ".06em", color: TEXT.faint }}>
              pathr.notter.com.br
            </span>
          </div>
        </div>

        <div
          style={{
            padding: 22.4,
            borderRadius: 14,
            background: PANEL,
            boxShadow: "0 0 0 1px #2b2e3d",
          }}
        >
          <h1 style={{ fontSize: 24, margin: "0 0 5.6px" }}>{title}</h1>
          {subtitle ? (
            <p style={{ fontSize: 13.5, color: "rgba(233,233,237,.6)", margin: "0 0 16.8px" }}>
              {subtitle}
            </p>
          ) : null}
          {children}
        </div>

        {footer ? (
          <div style={{ marginTop: 14, fontSize: 13, color: TEXT.muted, textAlign: "center" }}>
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/**
 * Aviso de erro do formulário.
 *
 * `role="alert"` para o leitor de tela anunciar sem a pessoa ter que procurar
 * — quem envia um formulário e não vê nada acontecer precisa saber por quê.
 */
export function FormError({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p
      role="alert"
      style={{
        margin: "0 0 11.2px",
        padding: "8.4px 11.2px",
        borderRadius: 8,
        background: "rgba(207,162,94,.12)",
        borderLeft: "2px solid #cfa25e",
        fontSize: 13,
        color: "rgba(233,233,237,.85)",
      }}
    >
      {children}
    </p>
  );
}

export function Field({
  id,
  label,
  hint,
  ...input
}: {
  id: string;
  label: string;
  hint?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="field" style={{ marginBottom: 11.2 }}>
      <label htmlFor={id}>{label}</label>
      <input id={id} className="input" {...input} />
      {hint ? (
        <div style={{ fontSize: 11, color: TEXT.faint, marginTop: 4 }}>{hint}</div>
      ) : null}
    </div>
  );
}
