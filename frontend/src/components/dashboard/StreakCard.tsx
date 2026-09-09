/**
 * A semana e a sequência.
 *
 * Os círculos são os sete dias; preenchido é dia com estudo. Sequência e
 * recorde ficam embaixo porque a sequência é o número que as pessoas
 * realmente protegem.
 */

import { streakDays } from "@/lib/dashboard";
import { ACC, ACC4, TEXT } from "@/lib/tokens";
import type { ActivitySummary, Streak } from "@/api/types";
import { Panel } from "@/components/ui/primitives";

export function StreakCard({
  streak,
  activity,
}: {
  streak: Streak;
  activity: ActivitySummary;
}) {
  const days = streakDays(activity);
  const done = days.filter((day) => day.done).length;

  return (
    <Panel style={{ display: "flex", flexDirection: "column" }}>
      <div style={{ fontSize: 14, marginBottom: 5.6 }}>Semana atual</div>
      <div style={{ fontSize: 28, lineHeight: 1.1, marginBottom: 14 }}>
        {done} {done === 1 ? "dia" : "dias"}
      </div>

      <ul
        aria-label="Dias estudados nesta semana"
        style={{ display: "flex", gap: 5, margin: 0, padding: 0, listStyle: "none" }}
      >
        {days.map((day) => (
          <li
            key={day.label}
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 6,
              minWidth: 0,
            }}
          >
            <span style={{ fontSize: 10.5, color: TEXT.faint }}>{day.label}</span>
            <span
              title={day.done ? `${day.label}: estudado` : `${day.label}: sem estudo`}
              style={{
                width: "100%",
                maxWidth: 26,
                aspectRatio: "1",
                borderRadius: "50%",
                display: "grid",
                placeItems: "center",
                border: `1px solid ${day.done ? ACC : day.today ? ACC4 : "rgba(233,233,237,.14)"}`,
                background: day.done ? "rgba(145,132,217,.22)" : "transparent",
                color: day.done ? "#e7e5fe" : "rgba(233,233,237,.4)",
                fontSize: 11,
              }}
            >
              {day.done ? "✓" : ""}
            </span>
          </li>
        ))}
      </ul>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 14,
          marginTop: "auto",
          paddingTop: 11.2,
          borderTop: "1px solid rgba(233,233,237,.10)",
          fontSize: 11.5,
          color: TEXT.muted,
        }}
      >
        <span>Sequência {streak.current} {streak.current === 1 ? "dia" : "dias"}</span>
        <span>Recorde {streak.longest} {streak.longest === 1 ? "dia" : "dias"}</span>
      </div>
    </Panel>
  );
}
