/**
 * A barra até 100% para as esperas longas: a etapa em texto, a porcentagem, e
 * a barra enchendo. Substitui o "Escrevendo…" parado e a faixa que só varria.
 *
 * O cálculo (estimado, aprende com as últimas durações, só chega a 100% quando
 * a resposta chega) mora em `lib/progresso.ts`.
 */

import { etapaDe, useProgressoEstimado } from "@/lib/progresso";
import { ACC, ACC4, C, TEXT } from "@/lib/tokens";

interface Props {
  /** Liga enquanto a tarefa roda. */
  ativo: boolean;
  /** Identifica a tarefa para a estimativa aprender ("quiz", "roadmap"…). */
  chave: string;
  /** O que acontece, em ordem. A barra mostra a etapa da fração em que está. */
  etapas: readonly string[];
  /** Quanto costuma levar, até haver medição própria. */
  duracaoMs?: number;
  style?: React.CSSProperties;
}

export function ProgressoDaTarefa({ ativo, chave, etapas, duracaoMs = 15_000, style }: Props) {
  const { pct, visivel, terminou } = useProgressoEstimado(ativo, chave, duracaoMs);
  if (!visivel) return null;

  const etapa = terminou ? "Pronto" : etapaDe(pct, etapas);
  const inteiro = Math.round(pct);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, ...style }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8.4, fontSize: 12.5 }}>
        <span aria-live="polite" style={{ color: terminou ? C.verde : TEXT.strong, flex: 1, minWidth: 0 }}>
          {etapa}
          {terminou ? "" : "…"}
        </span>
        <span style={{ color: TEXT.faint, fontVariantNumeric: "tabular-nums" }}>{inteiro}%</span>
      </div>
      <div
        role="progressbar"
        aria-label={etapa}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={inteiro}
        style={{ height: 6, borderRadius: 3, background: "rgba(233,233,237,.1)", overflow: "hidden" }}
      >
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            borderRadius: 3,
            background: terminou ? C.verde : `linear-gradient(90deg, ${ACC}, ${ACC4})`,
            transition: "width .25s ease-out, background .2s",
          }}
        />
      </div>
    </div>
  );
}
