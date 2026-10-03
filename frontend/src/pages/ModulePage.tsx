/**
 * O módulo em andamento: objetivos, material, quiz e atividade.
 *
 * Qual módulo abrir vem do estado de navegação; sem um escolhido, abre o que
 * o servidor marca como em andamento. Isso é o que faz "Retomar estudo" no
 * painel cair no lugar certo sem o painel precisar saber qual é.
 */

import { roadmap as roadmapApi } from "@/api/endpoints";
import type { RoadmapNode } from "@/api/types";
import { useT } from "@/lib/i18n";
import { useAppState } from "@/hooks/useAppState";
import { useIsCompact } from "@/hooks/useMediaQuery";
import { useMutation, useQuery } from "@/hooks/useApi";
import { curarModulo } from "@/lib/curadoria";
import { moduleStatusStyle } from "@/lib/moduleStatus";
import { proximoModulo } from "@/lib/proximoModulo";
import { ACC, ACC4, SIZE, TEXT } from "@/lib/tokens";
import type { ModuleTab } from "@/types";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/icons";
import { ModuleDot } from "@/components/roadmap/ModuleDot";
import { MaterialTab } from "@/components/quiz/MaterialTab";
import { QuizTab } from "@/components/quiz/QuizTab";
import { ActivityPanel } from "@/components/quiz/ActivityPanel";

const TABS: readonly { value: ModuleTab; labelKey: string }[] = [
  { value: "material", labelKey: "modulo.abas.material" },
  { value: "quiz", labelKey: "modulo.abas.quiz" },
  { value: "atividade", labelKey: "modulo.abas.atividade" },
];

export function ModulePage() {
  const t = useT();
  const { state, dispatch } = useAppState();
  const compacto = useIsCompact();
  const plan = useQuery(() => roadmapApi.current(), []);
  const complete = useMutation((nodeId: string) =>
    roadmapApi.patchNode(nodeId, { status: "done", minutes: 30 }),
  );

  if (plan.loading) return <Loading label={t("modulo.pagina.carregandoTrilha")} />;
  if (plan.status === 404) {
    return (
      <EmptyState
        title={t("modulo.pagina.semPlanoTitulo")}
        description={t("modulo.pagina.semPlanoDescricao")}
        action={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => dispatch({ type: "navigate", screen: "roadmap" })}
          >
            <Icon name="plus" size={15} />
            {t("modulo.pagina.gerarPlano")}
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
        title={t("modulo.pagina.planoConcluidoTitulo")}
        description={t("modulo.pagina.planoConcluidoDescricao")}
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
        {phase?.title ?? t("modulo.pagina.trilha")} · {node.kind}
        {node.level ? ` · ${node.level}` : ""}
      </div>
      <h1 style={{ fontSize: 26, margin: "0 0 16.8px" }}>{node.title}</h1>

      {/* Duas linhas de grade, e é isso que alinha os cartões: a linha 1 é o cabeçalho da coluna da esquerda
          (descrição + abas) e a linha 2 é o conteúdo da aba, à esquerda, com os cartões laterais à direita.
          Antes a coluna da direita nascia no TOPO da grade, acima das abas, e o cartão da pergunta só começava
          depois delas: "Ao final você consegue" ficava mais alto que o cartão do quiz, em toda aba.
          No celular tudo empilha numa coluna só (cabeçalho, conteúdo, cartões). */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: compacto ? "minmax(0,1fr)" : "minmax(0,2fr) minmax(260px,1fr)",
          columnGap: compacto ? 0 : 16.8,
          alignItems: "start",
        }}
      >
        <div style={{ minWidth: 0, gridColumn: 1, gridRow: 1 }}>
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
                  {t(tab.labelKey)}
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ minWidth: 0, gridColumn: 1, gridRow: 2 }}>
          {state.moduleTab === "material" ? <MaterialTab node={node} /> : null}
          {state.moduleTab === "quiz" ? <QuizTab node={node} /> : null}
          {state.moduleTab === "atividade" ? <ActivityPanel node={node} /> : null}
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 11.2,
            minWidth: 0,
            gridColumn: compacto ? 1 : 2,
            gridRow: compacto ? 3 : 2,
            marginTop: compacto ? 11.2 : 0,
          }}
        >
          <Objectives node={node} />
          <PhaseModules
            modules={phase?.modules ?? []}
            activeId={node.id}
            onOpen={(id) => dispatch({ type: "openNode", nodeId: id })}
          />
          <Panel>
            <Kicker style={{ display: "block", marginBottom: 8.4 }}>{t("modulo.pagina.concluir")}</Kicker>
            <p style={{ fontSize: 12, color: TEXT.muted, margin: "0 0 11.2px" }}>
              {t("modulo.pagina.concluirDescricao")}
            </p>
            <button
              type="button"
              className="btn btn-primary btn-block"
              disabled={node.status === "done" || complete.pending}
              onClick={async () => {
                const concluido = await complete.run(node.id);
                // Falhou: fica onde está. Avançar para o próximo assunto sem o estudo registrado
                // faria a pessoa achar que concluiu e perder o progresso no próximo recarregamento.
                if (concluido === null) return;
                // O plano de novo, e não o `plan.data` de antes do clique: o servidor acabou de
                // promover o próximo módulo a "em andamento", e é essa resposta que diz qual é.
                const atualizado = await roadmapApi.current().catch(() => null);
                const proximo = atualizado
                  ? proximoModulo(
                      atualizado.phases.flatMap((fase) => fase.modules),
                      node.id,
                    )
                  : null;
                if (proximo) {
                  dispatch({ type: "openNode", nodeId: proximo.id });
                  dispatch({ type: "setModuleTab", tab: "material" });
                  // A busca sai já, em vez de esperar a aba de material montar e perceber que está
                  // vazia. `curarModulo` só busca uma vez por módulo na sessão, então a aba não
                  // repete: quem chegar depois encontra a busca em andamento ou já pronta.
                  void curarModulo(proximo.id);
                }
                // Reaproveita a resposta que já chegou em vez de pedir o MESMO
                // roadmap de novo ao servidor. Só recorre a `reload` quando a
                // busca acima falhou e a tela precisa de uma chance nova de
                // buscar o plano atualizado.
                if (atualizado) plan.set(() => atualizado);
                else plan.reload();
              }}
            >
              {node.status === "done"
                ? t("modulo.pagina.concluido")
                : complete.pending
                  ? t("modulo.pagina.registrando")
                  : t("modulo.pagina.marcarConcluido")}
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
  const t = useT();
  if (node.objectives.length === 0) return null;
  return (
    <Panel>
      <Kicker style={{ display: "block", marginBottom: 11.2 }}>{t("modulo.pagina.aoFinalVoceConsegue")}</Kicker>
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
  const t = useT();
  if (modules.length === 0) return null;
  return (
    <Panel>
      <Kicker style={{ display: "block", marginBottom: 11.2 }}>{t("modulo.pagina.modulosDaFase")}</Kicker>
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
