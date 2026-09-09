/**
 * Uma competência do perfil, com nível e origem.
 *
 * A ORIGEM é o que o rótulo carrega além do nível: uma nota vinda do
 * currículo vale menos que uma comprovada em quiz, e mostrar isso evita que a
 * pessoa confie demais numa estimativa que ela mesma poderia corrigir.
 */

import type { UserTag } from "@/api/types";
import { ACC, TEXT } from "@/lib/tokens";

const SOURCE_LABEL: Record<string, string> = {
  cv: "do currículo",
  manual: "definido por você",
  quiz: "comprovado em quiz",
  roadmap: "estudado no plano",
};

export function TagButton({
  tag,
  onToggle,
  dashed = false,
}: {
  tag: UserTag;
  onToggle: () => void;
  /** Tracejado marca o que o plano vai ensinar, não o que já se tem. */
  dashed?: boolean;
}) {
  const source = SOURCE_LABEL[tag.source] ?? tag.source;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={tag.is_target}
      title={`N${tag.proficiency} · ${source} · confiança ${Math.round(tag.confidence * 100)}%`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: "5px 10px",
        borderRadius: 6,
        font: "inherit",
        fontSize: 12.5,
        cursor: "pointer",
        border: `1px ${dashed ? "dashed" : "solid"} ${tag.is_target ? ACC : "rgba(233,233,237,.18)"}`,
        background: tag.is_target ? "rgba(145,132,217,.14)" : "transparent",
        color: tag.is_target ? "#e7e5fe" : TEXT.muted,
      }}
    >
      {tag.name}
      <span
        style={{
          fontSize: 10,
          fontFamily: "ui-monospace, Menlo, monospace",
          padding: "1px 4px",
          borderRadius: 4,
          background: "rgba(233,233,237,.10)",
        }}
      >
        N{tag.proficiency}
      </span>
    </button>
  );
}
