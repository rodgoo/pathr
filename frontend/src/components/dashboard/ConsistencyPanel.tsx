/**
 * Constância em três recortes: ano, mês e semana.
 *
 * Cada recorte ganha a forma que lê melhor na própria densidade — mapa de
 * calor para o ano, calendário para o mês, barras para a semana — em vez de
 * um gráfico só esticado para os três.
 */

import {
  WEEKDAYS,
  monthGrid,
  rangeSummary,
  weekBars,
  yearHeat,
  yearMonths,
} from "@/lib/dashboard";
import { useDicaDoDia } from "./DicaDoDia";
import { useAppState } from "@/hooks/useAppState";
import { HEAT, TEXT } from "@/lib/tokens";
import type { ActivitySummary } from "@/api/types";
import type { ConstancyView } from "@/types";
import { Segmented } from "@/components/ui/Segmented";
import { Panel } from "@/components/ui/primitives";

const VIEWS: readonly { value: ConstancyView; label: string }[] = [
  { value: "ano", label: "Ano" },
  { value: "mes", label: "Mês" },
  { value: "semana", label: "Semana" },
];

export function ConsistencyPanel({ activity }: { activity: ActivitySummary }) {
  const { state, dispatch } = useAppState();
  const view = state.constancyView;
  const summary = rangeSummary(activity, view);

  return (
    <Panel>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 8.4,
          marginBottom: 14,
        }}
      >
        <span style={{ fontSize: 14 }}>{summary.title}</span>
        <span style={{ fontSize: 11.5, color: TEXT.faint }}>{summary.headline}</span>
        <Segmented
          name="constancy-view"
          label="Intervalo da constância"
          value={view}
          options={VIEWS}
          onChange={(next) => dispatch({ type: "setConstancyView", view: next })}
          style={{ marginLeft: "auto" }}
        />
      </div>

      {view === "ano" ? <YearHeatmap activity={activity} /> : null}
      {view === "mes" ? <MonthCalendar activity={activity} /> : null}
      {view === "semana" ? <WeekChart activity={activity} /> : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit,minmax(104px,1fr))",
          gap: 14,
          marginTop: 16.8,
          paddingTop: 14,
          borderTop: "1px solid rgba(233,233,237,.10)",
        }}
      >
        {summary.stats.map((stat) => (
          <div key={stat.label} style={{ minWidth: 0 }}>
            <div style={{ fontSize: 20, lineHeight: 1.1 }}>{stat.value}</div>
            <div style={{ fontSize: 11, color: TEXT.muted, marginTop: 2.8 }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {view !== "semana" ? <HeatLegend /> : null}
    </Panel>
  );
}

function YearHeatmap({ activity }: { activity: ActivitySummary }) {
  const cells = yearHeat(activity);
  const { gatilho, dica } = useDicaDoDia();
  return (
    <div style={{ overflowX: "auto", paddingBottom: 5.6 }}>
      <div style={{ minWidth: 790, display: "flex", gap: 8 }}>
        <div
          aria-hidden
          style={{
            flex: "none",
            display: "grid",
            gridTemplateRows: "repeat(7,12px)",
            gap: 2,
            paddingTop: 18,
          }}
        >
          {WEEKDAYS.map((day) => (
            <span
              key={day}
              style={{
                fontSize: 9,
                lineHeight: "12px",
                color: TEXT.faint,
                textAlign: "right",
                width: 22,
              }}
            >
              {day}
            </span>
          ))}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Cada mês sobre a coluna da semana em que ele começa. Antes os
              doze rótulos dividiam a largura em partes iguais, e a posição
              deles não tinha relação nenhuma com os quadrados embaixo. */}
          <div
            aria-hidden
            style={{
              display: "grid",
              gridAutoColumns: "12px",
              columnGap: 2,
              marginBottom: 6,
              height: 12,
            }}
          >
            {yearMonths().map((month) => (
              <span
                key={month.label}
                style={{
                  gridRow: 1,
                  gridColumn: month.column + 1,
                  fontSize: 10,
                  lineHeight: "12px",
                  color: TEXT.faint,
                  whiteSpace: "nowrap",
                }}
              >
                {month.label}
              </span>
            ))}
          </div>
          <ul
            aria-label="Atividade diária no ano"
            style={{
              display: "grid",
              gridAutoFlow: "column",
              gridTemplateRows: "repeat(7,12px)",
              gridAutoColumns: "12px",
              gap: 2,
              lineHeight: 0,
              margin: 0,
              padding: 0,
              listStyle: "none",
            }}
          >
            {cells.map((cell) => (
              <li
                key={cell.date}
                aria-label={cell.title || undefined}
                {...(cell.outside || cell.future ? {} : gatilho(cell))}
                style={{
                  display: "block",
                  width: 12,
                  height: 12,
                  borderRadius: 3,
                  background: cell.background,
                  visibility: cell.outside ? "hidden" : "visible",
                  cursor: cell.outside || cell.future ? "default" : "pointer",
                }}
              />
            ))}
          </ul>
        </div>
      </div>
      {dica}
    </div>
  );
}

function MonthCalendar({ activity }: { activity: ActivitySummary }) {
  const { gatilho, dica } = useDicaDoDia();
  return (
    <div>
      <div
        aria-hidden
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(7,minmax(34px,1fr))",
          gap: 4,
          marginBottom: 6,
          maxWidth: 320,
        }}
      >
        {WEEKDAYS.map((day) => (
          <span key={day} style={{ fontSize: 9.5, color: TEXT.faint, textAlign: "center" }}>
            {day}
          </span>
        ))}
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(7,minmax(34px,1fr))",
          gap: 4,
          maxWidth: 320,
        }}
      >
        {monthGrid(activity).map((cell, index) => (
          <div
            key={cell.date || `vazio-${index}`}
            aria-label={cell.title || undefined}
            {...(cell.outside || cell.future ? {} : gatilho(cell))}
            style={{
              height: 34,
              borderRadius: 5,
              background: cell.background,
              boxShadow: cell.ring,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              padding: "3px 4px",
              minWidth: 0,
            }}
          >
            <span style={{ fontSize: 9.5, lineHeight: 1, color: cell.dayColor }}>{cell.day}</span>
            <span style={{ fontSize: 9, lineHeight: 1, color: cell.minutesColor }}>
              {cell.minutesLabel}
            </span>
          </div>
        ))}
      </div>
      {dica}
    </div>
  );
}

function WeekChart({ activity }: { activity: ActivitySummary }) {
  const { gatilho, dica } = useDicaDoDia();
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 120 }}>
      {dica}
      {weekBars(activity).map((bar) => (
        <div
          key={bar.date}
          aria-label={bar.title}
          {...(bar.future ? {} : gatilho(bar))}
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: 6,
            height: "100%",
            minWidth: 0,
          }}
        >
          <span style={{ fontSize: 10.5, color: bar.valueColor }}>{bar.value}</span>
          <div
            style={{
              width: "100%",
              maxWidth: 44,
              borderRadius: "5px 5px 0 0",
              background: bar.color,
              height: `${bar.height}%`,
            }}
          />
          <span style={{ fontSize: 10.5, color: TEXT.faint }}>{bar.label}</span>
        </div>
      ))}
    </div>
  );
}

function HeatLegend() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        marginTop: 14,
        fontSize: 10.5,
        color: TEXT.faint,
      }}
    >
      <span>menos</span>
      {HEAT.map((background) => (
        <span key={background} style={{ width: 10, height: 10, borderRadius: 2, background }} />
      ))}
      <span>mais</span>
    </div>
  );
}
