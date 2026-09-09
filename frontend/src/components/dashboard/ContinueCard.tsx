/**
 * O controle mais importante do painel: retomar o módulo em andamento.
 *
 * Fica sobre o fundo de seção — o único campo saturado que o sistema permite
 * — porque tudo mais nesta tela é relatório e este é a ação.
 */

import { useAppState } from "@/hooks/useAppState";
import { ACC4, TEXT } from "@/lib/tokens";
import type { RoadmapSummary } from "@/api/types";
import { Kicker, Meter, Panel } from "@/components/ui/primitives";

export function ContinueCard({ roadmap }: { roadmap: RoadmapSummary }) {
  const { dispatch } = useAppState();
  const node = roadmap.current_node;

  const open = () =>
    dispatch({ type: "navigate", screen: "modulo", nodeId: node ? node.id : null });

  return (
    <Panel tone="section" style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8.4 }}>
        <Kicker tone="section">Continue</Kicker>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "rgba(233,233,237,.6)" }}>
          {roadmap.done_nodes} de {roadmap.total_nodes} módulos
        </span>
      </div>

      <div>
        <div style={{ fontSize: 20, marginBottom: 5.6 }}>
          {node ? node.title : "Plano concluído"}
        </div>
        <div style={{ fontSize: 13, color: "rgba(233,233,237,.75)", maxWidth: "48ch" }}>
          {node?.description ??
            "Todos os módulos deste plano foram concluídos. Gere um novo objetivo para continuar."}
        </div>
      </div>

      {node ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6 }}>
          <span className="tag tag-accent">{node.kind}</span>
          {node.estimated_hours ? (
            <span className="tag tag-neutral">{node.estimated_hours}h</span>
          ) : null}
          {node.level ? <span className="tag tag-outline">{node.level}</span> : null}
        </div>
      ) : null}

      <div style={{ marginTop: "auto" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: 11,
            color: "rgba(233,233,237,.6)",
            marginBottom: 5.6,
          }}
        >
          <span>Progresso do plano</span>
          <span>{roadmap.progress_pct}%</span>
        </div>
        <Meter pct={roadmap.progress_pct} color={ACC4} label="Progresso do plano" />
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8.4 }}>
        <button type="button" className="btn btn-primary" onClick={open}>
          {node ? "Retomar" : "Ver roadmap"}
        </button>
        {node?.week_start ? (
          <span style={{ fontSize: 11.5, color: TEXT.muted }}>
            Semana {node.week_start}
            {node.week_end && node.week_end !== node.week_start ? `–${node.week_end}` : ""}
          </span>
        ) : null}
      </div>
    </Panel>
  );
}
