/**
 * Progresso por fase do plano, cada linha um atalho para o roadmap.
 *
 * O anel é um arco em stroke-dasharray, não uma pizza: a 34px uma pizza não
 * consegue mostrar uma porcentagem pequena, e no começo do plano quase todas
 * são pequenas.
 */

import { useAppState } from "@/hooks/useAppState";
import { C, SIZE, TEXT, tint } from "@/lib/tokens";
import type { Roadmap } from "@/api/types";
import { Panel } from "@/components/ui/primitives";

const CIRCUMFERENCE = 88;
/** Uma cor por fase, na ordem. Estável entre renders porque o índice é. */
const PHASE_COLORS = [C.verde, "#9184d9", C.teal, C.azul, C.ambar];

export function TrackProgress({ roadmap }: { roadmap: Roadmap }) {
  const { dispatch } = useAppState();

  const phases = roadmap.phases.map((phase, index) => {
    const done = phase.modules.filter((module) => module.status === "done").length;
    return {
      id: phase.id,
      order: index + 1,
      title: phase.title,
      meta: `${done} de ${phase.modules.length} módulos`,
      pct: phase.modules.length ? Math.round((100 * done) / phase.modules.length) : 0,
      color: PHASE_COLORS[index % PHASE_COLORS.length],
    };
  });

  return (
    <Panel style={{ display: "flex", flexDirection: "column" }}>
      <div style={{ fontSize: 14, marginBottom: 14 }}>Progresso por fase</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
        {phases.map((phase) => (
          <button
            key={phase.id}
            type="button"
            className="toque"
            onClick={() => dispatch({ type: "navigate", screen: "roadmap" })}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 11.2,
              textAlign: "left",
              border: 0,
              background: "none",
              padding: 0,
              color: "inherit",
              font: "inherit",
              fontSize: SIZE.corpo,
              cursor: "pointer",
            }}
          >
            <span
              aria-hidden
              style={{
                width: 30,
                height: 30,
                flex: "none",
                borderRadius: 8,
                display: "grid",
                placeItems: "center",
                fontSize: 12.5,
                fontWeight: 600,
                lineHeight: 1,
                background: tint(phase.color, 16),
                color: phase.color,
              }}
            >
              {phase.order}
            </span>
            <span style={{ flex: 1, minWidth: 0 }}>
              <span style={{ display: "block", fontSize: 13.5 }}>{phase.title}</span>
              <span style={{ display: "block", fontSize: 11, color: TEXT.faint }}>
                {phase.meta}
              </span>
            </span>
            <span style={{ position: "relative", width: 34, height: 34, flex: "none" }}>
              <svg
                width="34"
                height="34"
                viewBox="0 0 34 34"
                style={{ transform: "rotate(-90deg)" }}
                aria-hidden
              >
                <circle cx="17" cy="17" r="14" fill="none" stroke="rgba(233,233,237,.12)" strokeWidth="3" />
                <circle
                  cx="17"
                  cy="17"
                  r="14"
                  fill="none"
                  stroke={phase.color}
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeDasharray={`${(phase.pct / 100) * CIRCUMFERENCE} 100`}
                />
              </svg>
              <span
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "grid",
                  placeItems: "center",
                  fontSize: 9.5,
                  lineHeight: 1,
                  whiteSpace: "nowrap",
                  color: "rgba(233,233,237,.7)",
                }}
              >
                {phase.pct}%
              </span>
            </span>
          </button>
        ))}
      </div>
    </Panel>
  );
}
