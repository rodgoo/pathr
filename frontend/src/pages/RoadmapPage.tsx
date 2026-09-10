/**
 * O plano, em três formatos.
 *
 * Quando ainda não existe plano, esta tela é o formulário que o gera — em vez
 * de um vazio que manda a pessoa procurar o botão em outro lugar.
 */

import { RouteAdjustments } from "@/components/roadmap/RouteAdjustments";
import { useState } from "react";
import { roadmap as roadmapApi, tags as tagsApi } from "@/api/endpoints";
import { useAppState } from "@/hooks/useAppState";
import { useQuery } from "@/hooks/useApi";
import { SIZE, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import type { RoadmapView } from "@/types";
import { Segmented } from "@/components/ui/Segmented";
import { ErrorState, Loading } from "@/components/ui/States";
import { SCREEN_IN } from "@/components/ui/primitives";
import { CompetenceMatrix } from "@/components/roadmap/CompetenceMatrix";
import { PhaseColumns } from "@/components/roadmap/PhaseColumns";
import { Timeline } from "@/components/roadmap/Timeline";
import { GenerateRoadmap } from "@/components/roadmap/GenerateRoadmap";

const VIEWS: readonly { value: RoadmapView; label: string }[] = [
  { value: "a", label: "Linha do tempo" },
  { value: "b", label: "Fases" },
  { value: "c", label: "Matriz" },
];

const NOTES: Record<RoadmapView, string> = {
  a: "Timeline vertical: a ordem manda, o prazo fica à esquerda.",
  b: "Fases lado a lado, para ver o escopo inteiro de uma vez.",
  c: "Matriz de competência: onde você está e até onde o plano leva.",
};

export function RoadmapPage() {
  const { state, dispatch } = useAppState();
  const [regenerating, setRegenerating] = useState(false);
  const plan = useQuery(() => roadmapApi.current(), []);
  const tags = useQuery(() => tagsApi.mine(), []);

  if (plan.loading) return <Loading label="Carregando seu plano…" />;

  // 404 aqui não é erro: é o estado de quem ainda não gerou nada.
  if (plan.status === 404 || regenerating) {
    return (
      <GenerateRoadmap
        onGenerated={() => {
          setRegenerating(false);
          plan.reload();
        }}
        onCancel={regenerating ? () => setRegenerating(false) : undefined}
      />
    );
  }

  if (plan.error) return <ErrorState message={plan.error} onRetry={plan.reload} />;
  if (!plan.data) return null;

  const view = state.roadmapView;

  return (
    <div style={SCREEN_IN}>
      <header
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-end",
          gap: 16.8,
          marginBottom: 5.6,
        }}
      >
        <div style={{ flex: 1, minWidth: 250 }}>
          <div style={{ fontSize: 12.5, color: TEXT.muted }}>
            {plan.data.horizon_weeks} semanas · {plan.data.weekly_hours}h por semana ·{" "}
            {plan.data.progress_pct}% concluído
          </div>
          <h1 style={{ fontSize: 28, margin: 0 }}>{plan.data.title}</h1>
        </div>
        <Segmented
          name="roadmap-view"
          label="Formato do roadmap"
          value={view}
          options={VIEWS}
          onChange={(next) => dispatch({ type: "setRoadmapView", view: next })}
        />
      </header>

      <p style={{ margin: "0 0 5.6px", fontSize: SIZE.apoio, color: TEXT.faint }}>{NOTES[view]}</p>

      {plan.data.summary ? (
        <p style={{ margin: "0 0 22.4px", fontSize: SIZE.corpo, color: "rgba(233,233,237,.7)", maxWidth: "70ch" }}>
          {plan.data.summary}
        </p>
      ) : (
        <div style={{ height: 16.8 }} />
      )}

      <RouteAdjustments onAjustado={plan.reload} />

      {view === "a" ? <Timeline roadmap={plan.data} /> : null}
      {view === "b" ? <PhaseColumns roadmap={plan.data} /> : null}
      {view === "c" ? <CompetenceMatrix roadmap={plan.data} tags={tags.data ?? []} /> : null}

      {/* Botão e explicação como IRMÃOS numa flex, não texto correndo ao lado
          de um botão inline: no celular o parágrafo se enrolava em volta do
          botão e as duas coisas terminavam desalinhadas. Aqui a nota desce
          inteira para a própria linha quando não cabe. */}
      <div
        style={{
          marginTop: 22.4,
          paddingTop: 14,
          borderTop: "1px solid rgba(233,233,237,.12)",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 11.2,
        }}
      >
        <button
          type="button"
          className="btn btn-secondary"
          style={{ flex: "none" }}
          onClick={() => setRegenerating(true)}
        >
          <Icon name="plus" size={15} />
          Gerar um novo plano
        </button>
        <span style={{ flex: "1 1 240px", fontSize: SIZE.apoio, color: TEXT.faint }}>
          O plano atual fica no histórico — gerar outro não apaga este.
        </span>
      </div>
    </div>
  );
}
