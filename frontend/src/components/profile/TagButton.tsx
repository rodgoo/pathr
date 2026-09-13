/**
 * Uma competência do perfil, com nível e origem.
 *
 * A ORIGEM é o que o rótulo carrega além do nível: uma nota vinda do
 * currículo vale menos que uma comprovada em quiz, e mostrar isso evita que a
 * pessoa confie demais numa estimativa que ela mesma poderia corrigir.
 */

import type { UserTag } from "@/api/types";
import { MarcaDaTecnologia, identidade } from "@/lib/tecnologias";
import { TEXT, tint } from "@/lib/tokens";

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
  // A cor é da tecnologia (Java laranja, React ciano): marcada, ela preenche;
  // desmarcada, fica só no contorno — a diferença entre "está no plano" e
  // "não está" continua sendo de intensidade, como antes, só que colorida.
  const { cor } = identidade(tag.name);
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
        border: `1px ${dashed ? "dashed" : "solid"} ${tint(cor, tag.is_target ? 62 : 30)}`,
        background: tag.is_target ? tint(cor, 15) : tint(cor, 4),
        color: tag.is_target ? TEXT.full : TEXT.muted,
      }}
    >
      <MarcaDaTecnologia nome={tag.name} />
      {tag.name}
      <span
        style={{
          fontSize: 10,
          fontFamily: "ui-monospace, Menlo, monospace",
          padding: "1px 4px",
          borderRadius: 4,
          background: tint(cor, tag.is_target ? 26 : 12),
        }}
      >
        N{tag.proficiency}
      </span>
    </button>
  );
}
