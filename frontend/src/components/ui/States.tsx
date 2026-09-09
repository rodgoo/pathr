/**
 * Os três estados que toda tela ligada ao servidor precisa desenhar.
 *
 * Existem como componentes porque o contrário — cada tela inventando seu
 * "carregando" — é como um app passa a ter cinco vazios diferentes dizendo a
 * mesma coisa de jeitos diferentes.
 */

import type { ReactNode } from "react";
import { TEXT } from "@/lib/tokens";
import { Panel } from "./primitives";

const BOX: React.CSSProperties = {
  padding: "44px 22.4px",
  borderRadius: 14,
  textAlign: "center",
  fontSize: 13.5,
};

/** Enquanto carrega. `aria-busy` para o leitor de tela não anunciar vazio. */
export function Loading({ label = "Carregando…" }: { label?: string }) {
  return (
    <div aria-busy="true" aria-live="polite" style={{ ...BOX, color: TEXT.faint }}>
      {label}
    </div>
  );
}

/**
 * Quando a requisição falhou.
 *
 * Sempre com o botão de tentar de novo: a causa mais comum é rede
 * intermitente, e obrigar a pessoa a recarregar a página inteira por isso é
 * desproporcional.
 */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      style={{
        ...BOX,
        color: "rgba(233,233,237,.8)",
        border: "1px solid rgba(207,162,94,.35)",
        background: "rgba(207,162,94,.08)",
      }}
    >
      <p style={{ margin: "0 0 14px" }}>{message}</p>
      {onRetry ? (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Tentar de novo
        </button>
      ) : null}
    </div>
  );
}

/** Quando não há nada — e o que fazer a respeito. */
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div style={{ ...BOX, border: "1px dashed rgba(233,233,237,.22)", color: TEXT.muted }}>
      <div style={{ fontSize: 16, color: TEXT.full, marginBottom: 5.6 }}>{title}</div>
      {description ? (
        <p style={{ margin: "0 auto 16.8px", maxWidth: "48ch", lineHeight: 1.6 }}>{description}</p>
      ) : null}
      {action}
    </div>
  );
}

/** Espaço reservado com a altura do conteúdo, para o layout não pular. */
export function PanelSkeleton({ height = 120 }: { height?: number }) {
  return (
    <Panel>
      <div
        aria-hidden
        style={{
          height,
          borderRadius: 8,
          background: "rgba(233,233,237,.05)",
          animation: "noc-pulse 1.6s ease-in-out infinite",
        }}
      />
    </Panel>
  );
}
