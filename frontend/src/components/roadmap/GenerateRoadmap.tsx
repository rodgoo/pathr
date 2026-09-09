/**
 * O formulário que gera o plano.
 *
 * Três perguntas, e as três mudam o resultado: para onde ir, em quanto tempo,
 * e com quantas horas por semana. O texto livre existe porque nenhum campo
 * estruturado captura "não posso estudar de manhã" ou "a entrevista é em
 * junho" — e é exatamente isso que faz um plano ser cumprível.
 *
 * A geração é uma chamada de IA de verdade: leva de 5 a 20 segundos, e a tela
 * diz isso em vez de fingir que é instantânea.
 */

import { useState, type FormEvent } from "react";
import { roadmap as roadmapApi, tags as tagsApi } from "@/api/endpoints";
import { useAppState } from "@/hooks/useAppState";
import { curarModulo } from "@/lib/curadoria";
import { useMutation, useQuery } from "@/hooks/useApi";
import { ACC, TEXT } from "@/lib/tokens";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";

const HORIZONS = [
  { value: "8", label: "8 semanas" },
  { value: "12", label: "12 semanas" },
  { value: "26", label: "26 semanas" },
  { value: "52", label: "1 ano" },
] as const;

const HOURS = [
  { value: "4", label: "4h" },
  { value: "6", label: "6h" },
  { value: "8", label: "8h" },
  { value: "12", label: "12h" },
] as const;

const CHIPS = [
  "Quero entrevista em inglês",
  "Sem depender de IA para codar",
  "Prefiro projeto prático a leitura",
  "Tenho o fim de semana livre",
];

export function GenerateRoadmap({
  onGenerated,
  onCancel,
}: {
  onGenerated: () => void;
  onCancel?: () => void;
}) {
  const { dispatch } = useAppState();
  const tags = useQuery(() => tagsApi.mine(), []);
  const [objective, setObjective] = useState("");
  const [weeks, setWeeks] = useState<string>("12");
  const [hours, setHours] = useState<string>("8");
  const [context, setContext] = useState("");

  const generate = useMutation(() =>
    roadmapApi.generate({
      objective: objective.trim(),
      horizon_weeks: Number(weeks),
      weekly_hours: Number(hours),
      context: context.trim(),
    }),
  );

  async function submit(event: FormEvent) {
    event.preventDefault();
    const result = await generate.run();
    if (!result) return;

    // A busca de material começa junto com o plano, para o módulo atual, e
    // NÃO é esperada: ela leva segundos (duas APIs externas mais a
    // verificação de cada link) e segurar a navegação por ela deixaria a
    // pessoa olhando um formulário parado depois de o plano já existir.
    const atual = result.phases
      .flatMap((fase) => fase.modules)
      .find((modulo) => modulo.status !== "done");
    if (atual) void curarModulo(atual.id);

    onGenerated();
  }

  // Sem competências não há lacuna a cobrir, e o backend recusaria — dizer
  // isso aqui evita um erro que a pessoa não teria como interpretar.
  if (tags.data && tags.data.length === 0) {
    return <NeedsSkills dispatch={dispatch} />;
  }

  return (
    <div style={{ maxWidth: 720, ...SCREEN_IN }}>
      <h1 style={{ fontSize: 28, margin: "0 0 5.6px" }}>Gerar seu plano</h1>
      <p style={{ margin: "0 0 16.8px", fontSize: 13.5, color: "rgba(233,233,237,.6)" }}>
        Monto as fases a partir das {tags.data?.length ?? 0} competências do seu perfil e do
        objetivo abaixo.
      </p>

      {generate.error ? <ErrorState message={generate.error} /> : null}

      <form onSubmit={submit}>
        <Panel pad={16.8} style={{ display: "flex", flexDirection: "column", gap: 16.8 }}>
          <div className="field">
            <label htmlFor="objective">Onde você quer chegar</label>
            <input
              id="objective"
              className="input"
              required
              minLength={5}
              placeholder="ex: fullstack Java pleno, com foco em vagas internacionais"
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
            />
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 22.4 }}>
            <div>
              <Kicker style={{ display: "block", marginBottom: 8.4 }}>Prazo</Kicker>
              <Segmented
                name="horizon"
                label="Prazo do plano"
                value={weeks}
                options={HORIZONS}
                onChange={setWeeks}
              />
            </div>
            <div>
              <Kicker style={{ display: "block", marginBottom: 8.4 }}>Horas por semana</Kicker>
              <Segmented
                name="weekly-hours"
                label="Horas por semana"
                value={hours}
                options={HOURS}
                onChange={setHours}
              />
            </div>
          </div>

          <ContextField value={context} onChange={setContext} />

          <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "center" }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={generate.pending || objective.trim().length < 5}
            >
              {generate.pending ? "Montando o plano…" : "Gerar plano"}
            </button>
            {onCancel ? (
              <button type="button" className="btn btn-ghost" onClick={onCancel}>
                Cancelar
              </button>
            ) : null}
            <span style={{ fontSize: 11.5, color: TEXT.faint }}>
              {generate.pending
                ? "A IA está escrevendo as fases — costuma levar menos de 20 segundos."
                : "Leva alguns segundos: o plano é escrito sob medida."}
            </span>
          </div>

          {generate.pending ? <Sweep /> : null}
        </Panel>
      </form>
    </div>
  );
}

function NeedsSkills({ dispatch }: { dispatch: ReturnType<typeof useAppState>["dispatch"] }) {
  return (
    <div style={SCREEN_IN}>
      <h1 style={{ fontSize: 28, margin: "0 0 16.8px" }}>Gerar seu plano</h1>
      <EmptyState
        title="Antes, preciso saber o que você já sabe"
        description="O plano cobre a distância entre o que você domina e onde quer chegar. Envie seu currículo, que eu leio e extraio as tecnologias, ou marque suas competências à mão."
        action={
          <div style={{ display: "flex", gap: 8.4, justifyContent: "center", flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => dispatch({ type: "navigate", screen: "cv" })}
            >
              Enviar currículo
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => dispatch({ type: "navigate", screen: "config", settingsTab: "skills" })}
            >
              Marcar competências
            </button>
          </div>
        }
      />
    </div>
  );
}

function ContextField({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  return (
    <div className="field">
      <label htmlFor="context">O que mais eu deveria saber (opcional)</label>
      <textarea
        id="context"
        className="input"
        // Sem `fontSize` inline: ele venceria a regra de toque e o Safari do
        // iPhone daria zoom na página ao focar o campo.
        style={{ minHeight: 100 }}
        placeholder="ex: sou frontend há 3 anos, quero virar fullstack Java, e a entrevista é em junho"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginTop: 8.4 }}>
        {CHIPS.map((chip) => (
          <button
            key={chip}
            type="button"
            onClick={() => onChange(value ? `${value.trim()}. ${chip}` : chip)}
            style={{
              padding: "5px 10px",
              borderRadius: 6,
              font: "inherit",
              fontSize: 12,
              cursor: "pointer",
              border: "1px dashed rgba(233,233,237,.22)",
              background: "transparent",
              color: TEXT.muted,
            }}
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}

/** A barra que varre enquanto a IA responde. Puramente decorativa. */
function Sweep() {
  return (
    <div
      aria-hidden
      style={{
        height: 3,
        borderRadius: 2,
        background: "rgba(233,233,237,.12)",
        overflow: "hidden",
        position: "relative",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(90deg,transparent,${ACC},transparent)`,
          animation: "noc-sweep 1.1s linear infinite",
        }}
      />
    </div>
  );
}
