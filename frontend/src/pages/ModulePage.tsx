/**
 * O módulo em andamento: objetivos, material, quiz e atividade.
 *
 * Qual módulo abrir vem do estado de navegação; sem um escolhido, abre o que
 * o servidor marca como em andamento. Isso é o que faz "Retomar estudo" no
 * painel cair no lugar certo sem o painel precisar saber qual é.
 */

import { roadmap as roadmapApi } from "@/api/endpoints";
import type { RoadmapNode } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useIsCompact } from "@/hooks/useMediaQuery";
import { useMutation, useQuery } from "@/hooks/useApi";
import { moduleStatusStyle } from "@/lib/moduleStatus";
import { ACC, ACC4, SIZE, TEXT } from "@/lib/tokens";
import type { ModuleTab } from "@/types";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/icons";
import { ModuleDot } from "@/components/roadmap/ModuleDot";
import { MaterialTab } from "@/components/quiz/MaterialTab";
import { QuizTab } from "@/components/quiz/QuizTab";
import { ActivityPanel } from "@/components/quiz/ActivityPanel";

const TABS: readonly { value: ModuleTab; label: string }[] = [
  { value: "material", label: "Material" },
  { value: "quiz", label: "Quiz" },
  { value: "atividade", label: "Atividade" },
];

export function ModulePage() {
  const { state, dispatch } = useAppState();
  const compacto = useIsCompact();
  const plan = useQuery(() => roadmapApi.current(), []);
  const complete = useMutation((nodeId: string) =>
    roadmapApi.patchNode(nodeId, { status: "done", minutes: 30 }),
  );

  if (plan.loading) return <Loading label="Carregando a trilha…" />;
  if (plan.status === 404) {
    return (
      <EmptyState
        title="Você ainda não tem um plano"
        description="Gere o roadmap para ter uma trilha em andamento."
        action={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => dispatch({ type: "navigate", screen: "roadmap" })}
          >
            <Icon name="plus" size={15} />
            Gerar plano
          </button>
        }
      />
    );
  }
  if (plan.error) return <ErrorState message={plan.error} onRetry={plan.reload} />;
  if (!plan.data) return null;

  const modules = plan.data.phases.flatMap((phase) => phase.modules);
  const node =
    modules.find((module) => module.id === state.activeNodeId) ??
    modules.find((module) => module.status === "doing") ??
    modules.find((module) => module.status !== "done") ??
    null;

  if (!node) {
    return (
      <EmptyState
        title="Plano concluído"
        description="Todos os módulos foram entregues. Gere um novo objetivo para continuar."
      />
    );
  }

  const phase = plan.data.phases.find((candidate) =>
    candidate.modules.some((module) => module.id === node.id),
  );

  return (
    <div style={SCREEN_IN}>
      {/* Sem botão "‹ Roadmap" aqui. Trilha e Roadmap são telas irmãs, cada
          uma com a própria entrada no menu — um "voltar" sugeria que a Trilha
          mora dentro do Roadmap, e duplicava o que o menu já faz. */}
      <div style={{ fontSize: 12.5, color: TEXT.muted }}>
        {phase?.title ?? "Trilha"} · {node.kind}
        {node.level ? ` · ${node.level}` : ""}
      </div>
      <h1 style={{ fontSize: 26, margin: "0 0 16.8px" }}>{node.title}</h1>

      {/* Uma coluna no celular, três no desktop (o conteúdo ocupa duas).
          O `span 2` NÃO pode sobrar na versão estreita: ele obriga a grade a
          ter duas colunas mesmo quando só cabe uma, e aí o conteúdo fica com
          a largura inteira enquanto os painéis de baixo ficam com metade —
          era isso que deixava os cartões desalinhados. */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: compacto ? "minmax(0,1fr)" : "repeat(auto-fit,minmax(290px,1fr))",
          gap: compacto ? 11.2 : 16.8,
          alignItems: "start",
        }}
      >
        <div style={{ minWidth: 0, gridColumn: compacto ? "auto" : "span 2" }}>
          {node.description ? (
            <p style={{ fontSize: 14, color: "rgba(233,233,237,.75)", maxWidth: "68ch" }}>
              {node.description}
            </p>
          ) : null}

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: 22.4,
              margin: "16.8px 0 14px",
              borderBottom: "1px solid rgba(233,233,237,.12)",
            }}
          >
            {TABS.map((tab) => {
              const active = state.moduleTab === tab.value;
              return (
                <button
                  key={tab.value}
                  type="button"
                  className="toque"
                  aria-current={active ? "true" : undefined}
                  onClick={() => dispatch({ type: "setModuleTab", tab: tab.value })}
                  style={{
                    padding: "0 0 8.4px",
                    border: 0,
                    background: "none",
                    font: "inherit",
                    fontSize: SIZE.corpo,
                    cursor: "pointer",
                    color: active ? ACC4 : "rgba(233,233,237,.55)",
                    boxShadow: active ? `inset 0 -2px 0 0 ${ACC}` : "none",
                  }}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          {state.moduleTab === "material" ? <MaterialTab node={node} /> : null}
          {state.moduleTab === "quiz" ? <QuizTab node={node} /> : null}
          {state.moduleTab === "atividade" ? <ActivityPanel node={node} /> : null}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 11.2, minWidth: 0 }}>
          <Objectives node={node} />
          <PhaseModules
            modules={phase?.modules ?? []}
            activeId={node.id}
            onOpen={(id) => dispatch({ type: "openNode", nodeId: id })}
          />
          <Panel>
            <Kicker style={{ display: "block", marginBottom: 8.4 }}>Concluir</Kicker>
            <p style={{ fontSize: 12, color: TEXT.muted, margin: "0 0 11.2px" }}>
              Marcar como concluído registra o estudo e sobe a proficiência das tecnologias deste
              módulo.
            </p>
            <button
              type="button"
              className="btn btn-primary btn-block"
              disabled={node.status === "done" || complete.pending}
              onClick={async () => {
                await complete.run(node.id);
                plan.reload();
              }}
            >
              {node.status === "done"
                ? "Concluído"
                : complete.pending
                  ? "Registrando…"
                  : "Marcar como concluído"}
            </button>
          </Panel>
        </div>
      </div>
    </div>
  );
}


/**
 * O que este módulo deve deixar a pessoa capaz de fazer.
 *
 * O prompt do backend exige objetivos verificáveis, começando com verbo — é
 * o que separa "Entender JPA" de "Escrever uma query com JOIN FETCH que
 * elimina o N+1". Mostrá-los aqui é o que permite alguém julgar se concluiu.
 */
function Objectives({ node }: { node: RoadmapNode }) {
  if (node.objectives.length === 0) return null;
  return (
    <Panel>
      <Kicker style={{ display: "block", marginBottom: 11.2 }}>Ao final você consegue</Kicker>
      <ul style={{ margin: 0, paddingLeft: 16, display: "flex", flexDirection: "column", gap: 5.6 }}>
        {node.objectives.map((objective) => (
          <li key={objective} style={{ fontSize: 13, lineHeight: 1.45 }}>
            {objective}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function PhaseModules({
  modules,
  activeId,
  onOpen,
}: {
  modules: RoadmapNode[];
  activeId: string;
  onOpen: (id: string) => void;
}) {
  if (modules.length === 0) return null;
  return (
    <Panel>
      <Kicker style={{ display: "block", marginBottom: 11.2 }}>Módulos da fase</Kicker>
      <div style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
        {modules.map((module) => {
          const style = moduleStatusStyle(module.status);
          const active = module.id === activeId;
          return (
            <button
              key={module.id}
              type="button"
              className="toque"
              onClick={() => onOpen(module.id)}
              aria-current={active ? "true" : undefined}
              style={{
                display: "flex",
                gap: 8.4,
                alignItems: "center",
                // `font: inherit` ANTES do tamanho: é um atalho, e depois
                // dele o `fontSize` acima seria zerado — a lista saía com os
                // 15px da moldura em vez dos 12.5 pedidos aqui.
                font: "inherit",
                fontSize: SIZE.apoio,
                textAlign: "left",
                border: 0,
                background: "none",
                padding: 0,
                cursor: "pointer",
                color: active ? ACC4 : style.color,
              }}
            >
              <ModuleDot style={style} size={15} />
              {module.title}
            </button>
          );
        })}
      </div>
    </Panel>
  );
}
