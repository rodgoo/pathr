/**
 * O roadmap como linha do tempo vertical — a visão padrão.
 *
 * A ordem é a mensagem: a fase e sua janela de semanas ficam numa coluna
 * fixa à esquerda, e os módulos penduram numa régua à direita, na ordem em
 * que devem ser feitos.
 */

import { useAppState } from "@/hooks/useAppState";
import { useT } from "@/lib/i18n";
import { useIsCompact } from "@/hooks/useMediaQuery";
import { moduleStatusLabel, moduleStatusStyle } from "@/lib/moduleStatus";
import { C, SIZE, TEXT } from "@/lib/tokens";
import type { Roadmap } from "@/api/types";
import { ModuleDot } from "./ModuleDot";

const PHASE_COLORS = [C.verde, "#9184d9", C.teal, C.azul, C.ambar];

export function Timeline({ roadmap }: { roadmap: Roadmap }) {
  const t = useT();
  const { dispatch } = useAppState();
  // No celular a coluna da esquerda comeria um terço da largura para dizer
  // duas linhas. Ela vira um cabeçalho em cima, e os cartões ficam com a
  // tela inteira — que e onde o titulo do modulo precisa caber.
  const compacto = useIsCompact();

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {roadmap.phases.map((phase, index) => {
        const color = PHASE_COLORS[index % PHASE_COLORS.length];
        return (
          <section
            key={phase.id}
            style={{
              display: "grid",
              gridTemplateColumns: compacto ? "minmax(0,1fr)" : "minmax(110px,140px) minmax(0,1fr)",
              gap: compacto ? 8.4 : 16.8,
              paddingBottom: 22.4,
            }}
          >
            <div
              style={
                compacto
                  ? { display: "flex", alignItems: "baseline", gap: 8.4, flexWrap: "wrap" }
                  : { paddingTop: 2 }
              }
            >
              <div
                style={{
                  fontSize: 11,
                  letterSpacing: ".08em",
                  textTransform: "uppercase",
                  color,
                }}
              >
                {t("roadmap.timeline.fase", { n: index + 1 })}
              </div>
              {phase.week_start ? (
                <div
                  style={{ fontSize: 12.5, color: TEXT.muted, marginTop: compacto ? 0 : 2.8 }}
                >
                  {t("roadmap.timeline.semanas", {
                    inicio: phase.week_start,
                    fim: phase.week_end ?? phase.week_start,
                  })}
                </div>
              ) : null}
              {compacto ? null : (
                <div style={{ marginTop: 8.4, width: 28, height: 2, background: color }} />
              )}
            </div>

            <div
              style={{
                borderLeft: `1px solid ${compacto ? color + "55" : "rgba(233,233,237,.14)"}`,
                paddingLeft: compacto ? 11.2 : 16.8,
                display: "flex",
                flexDirection: "column",
                gap: 8.4,
                minWidth: 0,
              }}
            >
              <h2 style={{ fontSize: 18, margin: 0 }}>{phase.title}</h2>
              {phase.description ? (
                <p style={{ fontSize: 12.5, color: TEXT.muted, margin: 0, maxWidth: "62ch" }}>
                  {phase.description}
                </p>
              ) : null}

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
                      display: "flex",
                      flexWrap: "wrap",
                      alignItems: "center",
                      gap: 11.2,
                      textAlign: "left",
                      padding: "11.2px 14px",
                      borderRadius: 8,
                      border: 0,
                      background: style.background,
                      boxShadow: `0 0 0 1px ${style.border}`,
                      color: "inherit",
                      font: "inherit",
                      fontSize: SIZE.corpo,
                      cursor: "pointer",
                    }}
                  >
                    <ModuleDot style={style} />
                    <span style={{ flex: 1, minWidth: 150 }}>
                      <span style={{ display: "block", fontSize: 14, color: style.color }}>
                        {module.title}
                      </span>
                      <span style={{ display: "block", fontSize: 11, color: TEXT.faint }}>
                        {module.kind} · {moduleStatusLabel(module.status, t)}
                        {module.level ? ` · ${module.level}` : ""}
                      </span>
                    </span>
                    {module.estimated_hours ? (
                      <span
                        style={{
                          fontSize: 11,
                          color: TEXT.faint,
                          minWidth: 40,
                          textAlign: "right",
                        }}
                      >
                        {module.estimated_hours}h
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
