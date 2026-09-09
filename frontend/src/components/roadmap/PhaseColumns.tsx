/**
 * O roadmap como colunas paralelas — o escopo inteiro de uma vez.
 *
 * Troca a noção de sequência que a linha do tempo dá por amplitude: serve
 * quando a pergunta é "quanto tem pela frente?" e não "qual é o próximo?".
 */

import { useAppState } from "@/hooks/useAppState";
import { moduleStatusStyle } from "@/lib/moduleStatus";
import { C, SIZE, TEXT } from "@/lib/tokens";
import type { Roadmap } from "@/api/types";
import { Panel } from "@/components/ui/primitives";

const PHASE_COLORS = [C.verde, "#9184d9", C.teal, C.azul, C.ambar];

export function PhaseColumns({ roadmap }: { roadmap: Roadmap }) {
  const { dispatch } = useAppState();

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))",
        gap: 11.2,
        alignItems: "start",
      }}
    >
      {roadmap.phases.map((phase, index) => {
        const color = PHASE_COLORS[index % PHASE_COLORS.length];
        return (
          <Panel key={phase.id} style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8.4 }}>
              <span
                style={{ fontSize: 11, letterSpacing: ".08em", textTransform: "uppercase", color }}
              >
                Fase {index + 1}
              </span>
              {phase.week_start ? (
                <span style={{ marginLeft: "auto", fontSize: 11, color: TEXT.faint }}>
                  sem. {phase.week_start}–{phase.week_end ?? phase.week_start}
                </span>
              ) : null}
            </div>
            <h2 style={{ fontSize: 16, margin: "0 0 2.8px" }}>{phase.title}</h2>

            {phase.modules.map((module) => {
              const style = moduleStatusStyle(module.status);
              return (
                <button
                  key={module.id}
                  type="button"
                  onClick={() =>
                    dispatch({ type: "navigate", screen: "modulo", nodeId: module.id })
                  }
                  style={{
                    textAlign: "left",
                    padding: 11.2,
                    borderRadius: 8,
                    border: 0,
                    background: "#1b1d2b",
                    boxShadow: `0 0 0 1px ${style.border}`,
                    color: "inherit",
                    font: "inherit",
                    fontSize: SIZE.corpo,
                    cursor: "pointer",
                  }}
                >
                  <span
                    style={{ display: "block", fontSize: 13.5, marginBottom: 4, color: style.color }}
                  >
                    {module.title}
                  </span>
                  <span style={{ display: "block", fontSize: 11, color: TEXT.faint }}>
                    {module.kind}
                    {module.estimated_hours ? ` · ${module.estimated_hours}h` : ""}
                  </span>
                </button>
              );
            })}
          </Panel>
        );
      })}
    </div>
  );
}
