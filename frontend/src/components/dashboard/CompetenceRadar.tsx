/**
 * Where the learner is against where the plan takes them.
 *
 * The solid polygon is today, the dashed one the 26-week target. A radar is
 * the right shape here precisely because it is bad at exact values and good
 * at showing lopsidedness — the point is that the frontend axis is long and
 * the backend axes are short.
 */
import { useT } from "@/lib/i18n";
import { Panel } from "@/components/ui/primitives";

/** Axis labels, clockwise from the top. Java/Spring/Front/Infra são marcas e
 * ficam cravadas; Dados/Testes vêm do dicionário (chave preenchida). */
const AXES = [
  { label: "Java", x: 110, y: 12, anchor: "middle" },
  { label: "Spring", x: 196, y: 64, anchor: "start" },
  { label: "Dados", chave: "radar.eixoDados", x: 196, y: 158, anchor: "start" },
  { label: "Testes", chave: "radar.eixoTestes", x: 110, y: 188, anchor: "middle" },
  { label: "Infra", x: 24, y: 158, anchor: "end" },
  { label: "Front", x: 24, y: 64, anchor: "end" },
] as const;

export function CompetenceRadar() {
  const t = useT();
  return (
    <Panel style={{ display: "flex", flexDirection: "column" }}>
      <div style={{ fontSize: 14, marginBottom: 5.6 }}>{t("radar.titulo")}</div>
      <div style={{ fontSize: 11.5, color: "rgba(233,233,237,.45)", marginBottom: 8.4 }}>
        {t("radar.legenda")}
      </div>
      <div style={{ display: "grid", placeItems: "center", flex: 1, minHeight: 0 }}>
        <svg
          viewBox="0 0 220 190"
          role="img"
          aria-label={t("radar.aria")}
          style={{ width: "100%", maxWidth: 220, height: "auto" }}
        >
          <g fill="none" stroke="rgba(233,233,237,.12)">
            <polygon points="110,20 188,66 188,152 110,178 32,152 32,66" />
            <polygon points="110,49 163,80 163,138 110,155 57,138 57,80" />
            <polygon points="110,78 137,94 137,124 110,133 83,124 83,94" />
            <path d="M110 20V104M188 66l-78 38M188 152l-78-48M110 178v-74M32 152l78-48M32 66l78 38" />
          </g>
          <polygon
            points="110,44 170,78 154,144 110,150 62,132 46,80"
            fill="rgba(145,132,217,.18)"
            stroke="#9184d9"
            strokeWidth="1.5"
          />
          <polygon
            points="110,24 185,66 182,148 110,172 38,146 36,70"
            fill="none"
            stroke="#b5abfc"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
          <g fill="rgba(233,233,237,.55)" fontSize="9" fontFamily="Inter,sans-serif">
            {AXES.map((axis) => (
              <text key={axis.label} x={axis.x} y={axis.y} textAnchor={axis.anchor}>
                {"chave" in axis ? t(axis.chave) : axis.label}
              </text>
            ))}
          </g>
        </svg>
      </div>
    </Panel>
  );
}
