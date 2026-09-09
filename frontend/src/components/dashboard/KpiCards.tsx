/**
 * As três métricas de topo, agora com números reais.
 *
 * A minissérie embaixo de cada número são os últimos 22 dias de atividade —
 * a mesma fonte do heatmap. Um número sem a forma atrás dele não diz se a
 * semana está se recuperando ou escorregando.
 */

import { humanMinutes, yearHeat } from "@/lib/dashboard";
import { C, TEXT } from "@/lib/tokens";
import type { Overview } from "@/api/types";
import { Icon, type IconName } from "@/components/ui/icons";
import { Panel } from "@/components/ui/primitives";

interface Kpi {
  label: string;
  value: string;
  support: { label: string; value: string }[];
  color: string;
  icon: IconName;
  /** Altura relativa de cada barra, 0..100. */
  series: number[];
}

/** Os últimos 22 dias, normalizados pela maior barra da própria janela. */
function recentSeries(overview: Overview): number[] {
  const days = yearHeat(overview.activity).slice(-22);
  const peak = Math.max(30, ...days.map((day) => day.minutes));
  return days.map((day) => Math.max(6, Math.round((day.minutes / peak) * 100)));
}

function build(overview: Overview): Kpi[] {
  const series = recentSeries(overview);
  const { streak, roadmap, activity, english } = overview;

  return [
    {
      label: "Sequência de estudo",
      value: streak.current === 1 ? "1 dia" : `${streak.current} dias`,
      support: [
        { label: "Recorde", value: `${streak.longest} dias` },
        { label: "Dias ativos", value: String(activity.active_days) },
      ],
      color: C.ambar,
      icon: "flame",
      series,
    },
    {
      label: "Progresso do roadmap",
      value: roadmap ? `${roadmap.progress_pct}%` : "—",
      support: [
        { label: "Concluídos", value: roadmap ? String(roadmap.done_nodes) : "0" },
        { label: "No plano", value: roadmap ? String(roadmap.total_nodes) : "0" },
      ],
      color: "#b5afe8",
      icon: "trend",
      series,
    },
    {
      label: "Tempo de estudo",
      value: humanMinutes(activity.total_minutes),
      support: [
        { label: "XP", value: String(streak.total_xp) },
        { label: "Inglês", value: english.cefr_level ?? "—" },
      ],
      color: C.teal,
      icon: "clock",
      series,
    },
  ];
}

export function KpiCards({ overview }: { overview: Overview }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit,minmax(232px,1fr))",
        gap: 11.2,
      }}
    >
      {build(overview).map((kpi) => (
        <Panel key={kpi.label} style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8.4 }}>
            <span
              style={{
                width: 16,
                height: 16,
                flex: "none",
                display: "grid",
                placeItems: "center",
                color: kpi.color,
              }}
            >
              <Icon name={kpi.icon} />
            </span>
            <span style={{ fontSize: 12.5, color: "rgba(233,233,237,.62)" }}>{kpi.label}</span>
          </div>

          <div style={{ fontSize: 30, lineHeight: 1 }}>{kpi.value}</div>

          <div aria-hidden style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 24 }}>
            {kpi.series.map((height, index) => (
              <span
                key={index}
                style={{
                  flex: 1,
                  borderRadius: 1,
                  background: kpi.color,
                  opacity: index > 17 ? 1 : 0.42,
                  height: `${height}%`,
                }}
              />
            ))}
          </div>

          <div
            style={{
              display: "flex",
              gap: 14,
              paddingTop: 8.4,
              borderTop: "1px solid rgba(233,233,237,.10)",
            }}
          >
            {kpi.support.map((entry) => (
              <div key={entry.label} style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: 10.5, color: TEXT.faint }}>{entry.label}</div>
                <div style={{ fontSize: 14 }}>{entry.value}</div>
              </div>
            ))}
          </div>
        </Panel>
      ))}
    </div>
  );
}
