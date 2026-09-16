/**
 * As três métricas de topo, agora com números reais.
 *
 * A minissérie embaixo de cada número são os últimos 22 dias de atividade —
 * a mesma fonte do heatmap. Um número sem a forma atrás dele não diz se a
 * semana está se recuperando ou escorregando.
 *
 * Passar o mouse sobre uma barra diz qual dia ela é, o que foi feito e por
 * quanto tempo. Sem isso as barras eram decoração: dava para ver que um dia
 * foi mais alto, não o que aconteceu nele.
 */

import { humanMinutes, recentDays, type DayDetail } from "@/lib/dashboard";
import { C, TEXT } from "@/lib/tokens";
import { useT, type Traduzir } from "@/lib/i18n";
import type { Overview } from "@/api/types";
import { Icon, type IconName } from "@/components/ui/icons";
import { Panel } from "@/components/ui/primitives";
import { useDicaDoDia } from "./DicaDoDia";

interface Kpi {
  label: string;
  value: string;
  support: { label: string; value: string }[];
  color: string;
  icon: IconName;
  series: Barra[];
}

interface Barra extends DayDetail {
  /** Altura relativa, 0..100. */
  altura: number;
}

/**
 * Os últimos 22 dias, normalizados pela maior barra da própria janela.
 *
 * Dia com atividade mas sem minutos (marcar um material, criar o plano) ganha
 * altura de meio caminho: no piso, ele sumia entre os dias vazios, e o balão
 * dele — que é justamente o que diz o que foi feito — ficava sem onde mirar.
 */
function recentSeries(overview: Overview): Barra[] {
  const days = recentDays(overview.activity);
  const peak = Math.max(30, ...days.map((day) => day.minutes));
  return days.map((day) => ({
    ...day,
    altura:
      day.minutes > 0
        ? Math.max(12, Math.round((day.minutes / peak) * 100))
        : day.count > 0
          ? 30
          : 6,
  }));
}

function build(overview: Overview, t: Traduzir): Kpi[] {
  const series = recentSeries(overview);
  const { streak, roadmap, activity, english } = overview;

  return [
    {
      label: t("kpi.sequencia"),
      value: t(streak.current === 1 ? "kpi.umDia" : "kpi.dias", { n: streak.current }),
      support: [
        { label: t("kpi.recorde"), value: t("kpi.dias", { n: streak.longest }) },
        { label: t("kpi.diasAtivos"), value: String(activity.active_days) },
      ],
      color: C.ambar,
      icon: "flame",
      series,
    },
    {
      label: t("kpi.progresso"),
      value: roadmap ? `${roadmap.progress_pct}%` : "—",
      support: [
        { label: t("kpi.concluidos"), value: roadmap ? String(roadmap.done_nodes) : "0" },
        { label: t("kpi.noPlano"), value: roadmap ? String(roadmap.total_nodes) : "0" },
      ],
      color: "#b5afe8",
      icon: "trend",
      series,
    },
    {
      label: t("kpi.tempo"),
      value: humanMinutes(activity.total_minutes),
      support: [
        { label: "XP", value: String(streak.total_xp) },
        { label: t("kpi.ingles"), value: english.cefr_level ?? "—" },
      ],
      color: C.teal,
      icon: "clock",
      series,
    },
  ];
}

export function KpiCards({ overview }: { overview: Overview }) {
  const t = useT();
  const { gatilho, dica } = useDicaDoDia();
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit,minmax(232px,1fr))",
        gap: 11.2,
      }}
    >
      {build(overview, t).map((kpi) => (
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

          <div
            role="img"
            aria-label={`Últimos ${kpi.series.length} dias`}
            style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 24 }}
          >
            {kpi.series.map((barra, index) => (
              // A barra inteira responde ao mouse, não só a parte pintada: um
              // dia vazio tem 6% de altura, e mirar nisso seria impossível.
              <span
                key={barra.date}
                {...gatilho(barra)}
                style={{
                  flex: 1,
                  height: "100%",
                  display: "flex",
                  alignItems: "flex-end",
                  cursor: "pointer",
                }}
              >
                <span
                  style={{
                    width: "100%",
                    borderRadius: 1,
                    background: kpi.color,
                    // Hoje aceso; o resto a meia-luz. Antes eram as quatro
                    // últimas barras, o que não correspondia a nada.
                    opacity: index === kpi.series.length - 1 ? 1 : 0.42,
                    height: `${barra.altura}%`,
                  }}
                />
              </span>
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
      {dica}
    </div>
  );
}
