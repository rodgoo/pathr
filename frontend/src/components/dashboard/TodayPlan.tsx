/**
 * O que fazer agora: os próximos módulos do plano, em ordem.
 *
 * Curto de propósito. Uma lista maior que o tempo disponível é uma lista que
 * ninguém começa — mostra três, que é o que cabe numa sessão de estudo.
 */

import { useAppState } from "@/hooks/useAppState";
import { ACC, ACC4, C, TEXT, tint } from "@/lib/tokens";
import type { Roadmap, RoadmapNode } from "@/api/types";
import { Icon, type IconName } from "@/components/ui/icons";
import { EmptyState } from "@/components/ui/States";
import { Panel } from "@/components/ui/primitives";

const ICON_BY_KIND: Record<string, IconName> = {
  skill: "book",
  project: "code",
  checkpoint: "quiz",
  reading: "article",
};

const COLOR_BY_KIND: Record<string, string> = {
  skill: ACC,
  project: C.verde,
  checkpoint: C.azul,
  reading: C.rosa,
};

/** Os próximos módulos ainda não concluídos, na ordem do plano. */
function upcoming(roadmap: Roadmap, limit = 4): RoadmapNode[] {
  return roadmap.phases
    .flatMap((phase) => phase.modules)
    .filter((module) => module.status !== "done" && module.status !== "skipped")
    .slice(0, limit);
}

export function TodayPlan({ roadmap }: { roadmap: Roadmap }) {
  const { dispatch } = useAppState();
  const modules = upcoming(roadmap);

  return (
    <Panel>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8.4, marginBottom: 11.2 }}>
        <span style={{ fontSize: 14 }}>A seguir</span>
        <span style={{ marginLeft: "auto", fontSize: 11.5, color: TEXT.faint }}>
          {modules.length} {modules.length === 1 ? "módulo" : "módulos"}
        </span>
      </div>

      {modules.length === 0 ? (
        <EmptyState title="Nada pendente" description="Você concluiu todos os módulos do plano." />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 5.6 }}>
          {modules.map((module) => {
            const color = COLOR_BY_KIND[module.kind] ?? ACC;
            return (
              <button
                key={module.id}
                type="button"
                onClick={() =>
                  dispatch({ type: "navigate", screen: "modulo", nodeId: module.id })
                }
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 9,
                  textAlign: "left",
                  padding: "8.4px 11.2px",
                  borderRadius: 8,
                  border: 0,
                  background: "#1b1d2b",
                  boxShadow: `0 0 0 1px ${
                    module.status === "doing" ? "rgba(145,132,217,.35)" : "rgba(233,233,237,.08)"
                  }`,
                  color: "inherit",
                  font: "inherit",
                  cursor: "pointer",
                }}
              >
                <span
                  style={{
                    width: 26,
                    height: 26,
                    flex: "none",
                    borderRadius: 6,
                    display: "grid",
                    placeItems: "center",
                    background: tint(color, 16),
                    color,
                  }}
                >
                  <Icon name={ICON_BY_KIND[module.kind] ?? "book"} />
                </span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span
                    style={{
                      display: "block",
                      fontSize: 13.5,
                      color: module.status === "doing" ? ACC4 : TEXT.full,
                    }}
                  >
                    {module.title}
                  </span>
                  <span style={{ display: "block", fontSize: 11, color: TEXT.faint }}>
                    {module.status === "doing" ? "em andamento" : "a fazer"}
                    {module.level ? ` · ${module.level}` : ""}
                  </span>
                </span>
                {module.estimated_hours ? (
                  <span style={{ fontSize: 11, color: TEXT.faint }}>
                    {module.estimated_hours}h
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      )}
    </Panel>
  );
}
