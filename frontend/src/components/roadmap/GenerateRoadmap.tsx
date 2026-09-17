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
import { useT, type Traduzir } from "@/lib/i18n";
import { TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { ProgressoDaTarefa } from "@/components/ui/ProgressoDaTarefa";

const HOURS = [
  { value: "4", label: "4h" },
  { value: "6", label: "6h" },
  { value: "8", label: "8h" },
  { value: "12", label: "12h" },
] as const;

export function GenerateRoadmap({
  onGenerated,
  onCancel,
}: {
  onGenerated: () => void;
  onCancel?: () => void;
}) {
  const t = useT();
  const { dispatch } = useAppState();

  const HORIZONS = [
    { value: "8", label: t("roadmap.gerar.horizontes.s8") },
    { value: "12", label: t("roadmap.gerar.horizontes.s12") },
    { value: "26", label: t("roadmap.gerar.horizontes.s26") },
    { value: "52", label: t("roadmap.gerar.horizontes.ano") },
  ] as const;
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
      <h1 style={{ fontSize: 28, margin: "0 0 5.6px" }}>{t("roadmap.gerar.titulo")}</h1>
      <p style={{ margin: "0 0 16.8px", fontSize: 13.5, color: "rgba(233,233,237,.6)" }}>
        {t("roadmap.gerar.intro", { n: tags.data?.length ?? 0 })}
      </p>

      {generate.error ? <ErrorState message={generate.error} /> : null}

      <form onSubmit={submit}>
        <Panel pad={16.8} style={{ display: "flex", flexDirection: "column", gap: 16.8 }}>
          <div className="field">
            <label htmlFor="objective">{t("roadmap.gerar.objetivoLabel")}</label>
            <input
              id="objective"
              className="input"
              required
              minLength={5}
              placeholder={t("roadmap.gerar.objetivoPlaceholder")}
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
            />
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 22.4 }}>
            <div>
              <Kicker style={{ display: "block", marginBottom: 8.4 }}>{t("roadmap.gerar.prazo")}</Kicker>
              <Segmented
                name="horizon"
                label={t("roadmap.gerar.prazoLabel")}
                value={weeks}
                options={HORIZONS}
                onChange={setWeeks}
              />
            </div>
            <div>
              <Kicker style={{ display: "block", marginBottom: 8.4 }}>{t("roadmap.gerar.horas")}</Kicker>
              <Segmented
                name="weekly-hours"
                label={t("roadmap.gerar.horasLabel")}
                value={hours}
                options={HOURS}
                onChange={setHours}
              />
            </div>
          </div>

          <ContextField value={context} onChange={setContext} t={t} />

          <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "center" }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={generate.pending || objective.trim().length < 5}
            >
              <Icon name="plus" size={15} />
              {generate.pending ? t("roadmap.gerar.montando") : t("roadmap.gerar.gerar")}
            </button>
            {onCancel ? (
              <button type="button" className="btn btn-ghost" onClick={onCancel}>
                <Icon name="x" size={15} />
                {t("roadmap.gerar.cancelar")}
              </button>
            ) : null}
            <span style={{ fontSize: 11.5, color: TEXT.faint }}>
              {generate.pending
                ? t("roadmap.gerar.dicaMontando")
                : t("roadmap.gerar.dica")}
            </span>
          </div>

          <ProgressoDaTarefa
            ativo={generate.pending}
            chave="roadmap-gerar"
            etapas={[
              t("roadmap.gerar.etapas.lendo"),
              t("roadmap.gerar.etapas.fases"),
              t("roadmap.gerar.etapas.modulos"),
              t("roadmap.gerar.etapas.ordem"),
            ]}
            duracaoMs={30_000}
          />
        </Panel>
      </form>
    </div>
  );
}

function NeedsSkills({ dispatch }: { dispatch: ReturnType<typeof useAppState>["dispatch"] }) {
  const t = useT();
  return (
    <div style={SCREEN_IN}>
      <h1 style={{ fontSize: 28, margin: "0 0 16.8px" }}>{t("roadmap.gerar.titulo")}</h1>
      <EmptyState
        title={t("roadmap.gerar.semSkills.titulo")}
        description={t("roadmap.gerar.semSkills.descricao")}
        action={
          <div style={{ display: "flex", gap: 8.4, justifyContent: "center", flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => dispatch({ type: "navigate", screen: "cv" })}
            >
              <Icon name="upload" size={15} />
              {t("roadmap.gerar.semSkills.enviarCv")}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => dispatch({ type: "navigate", screen: "config", settingsTab: "skills" })}
            >
              {t("roadmap.gerar.semSkills.marcar")}
            </button>
          </div>
        }
      />
    </div>
  );
}

function ContextField({
  value,
  onChange,
  t,
}: {
  value: string;
  onChange: (next: string) => void;
  t: Traduzir;
}) {
  const CHIPS = [
    t("roadmap.gerar.chips.entrevistaIngles"),
    t("roadmap.gerar.chips.semIa"),
    t("roadmap.gerar.chips.pratico"),
    t("roadmap.gerar.chips.fimDeSemana"),
  ];
  return (
    <div className="field">
      <label htmlFor="context">{t("roadmap.gerar.contextoLabel")}</label>
      <textarea
        id="context"
        className="input"
        // Sem `fontSize` inline: ele venceria a regra de toque e o Safari do
        // iPhone daria zoom na página ao focar o campo.
        style={{ minHeight: 100 }}
        placeholder={t("roadmap.gerar.contextoPlaceholder")}
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

