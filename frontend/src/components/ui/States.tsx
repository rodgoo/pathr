/**
 * Os três estados que toda tela ligada ao servidor precisa desenhar.
 *
 * Existem como componentes porque o contrário — cada tela inventando seu
 * "carregando" — é como um app passa a ter cinco vazios diferentes dizendo a
 * mesma coisa de jeitos diferentes.
 */

import type { ReactNode } from "react";
import { useT } from "@/lib/i18n";
import { SIZE, TEXT } from "@/lib/tokens";
import { Icon } from "./icons";
import { MarcaCarregando } from "./MarcaCarregando";
import { Panel } from "./primitives";

const BOX: React.CSSProperties = {
  padding: "44px 22.4px",
  borderRadius: 14,
  textAlign: "center",
  fontSize: SIZE.corpo,
};

/**
 * Enquanto carrega.
 *
 * A marca animada, e não a palavra "Carregando…" parada: um texto imóvel não
 * distingue "está vindo" de "travou", e é essa dúvida que faz alguém
 * recarregar a página no meio de uma requisição que ia dar certo.
 */
export function Loading({ label }: { label?: string }) {
  const t = useT();
  return <MarcaCarregando label={label ?? t("comum.carregando")} />;
}

/**
 * Quando a requisição falhou.
 *
 * Sempre com o botão de tentar de novo: a causa mais comum é rede
 * intermitente, e obrigar a pessoa a recarregar a página inteira por isso é
 * desproporcional.
 */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const t = useT();
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
          <Icon name="refresh" size={15} />
          {t("comum.tentarDeNovo")}
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
