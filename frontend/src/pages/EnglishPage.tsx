/**
 * O módulo de idioma.
 *
 * Opcional de propósito, e diz isso: o interruptor no topo tira 15 minutos
 * por dia do plano em vez de esconder um recurso. É a diferença entre um app
 * que respeita quem já fala inglês e um que empurra prática que ninguém pediu.
 *
 * O nivelamento é adaptativo — a dificuldade do próximo item sai do acerto do
 * anterior — então converge em cerca de 20 itens em vez de precisar de 100.
 */

import { useState } from "react";
import { english as englishApi } from "@/api/endpoints";
import type { EnglishAssessment, LanguageImprovements, PracticeSession } from "@/api/types";
import { useMutation, useQuery } from "@/hooks/useApi";
import { ACC, ACC4, C, HAIRLINE, RING, TEXT } from "@/lib/tokens";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { Placement } from "@/components/english/Placement";
import { QuadroDeHabilidades } from "@/components/english/QuadroDeHabilidades";
import { CartaoDoTreino, TreinoDoDia } from "@/components/english/treino/TreinoDoDia";

const BANDS = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;

export function EnglishPage() {
  // Qual idioma esta tela mostra. Com varios no plano, "o" idioma deixou de
  // existir: a pessoa escolhe entre os que ligou em Configuracoes, e o padrao
  // e o primeiro ligado.
  const meus = useQuery(() => englishApi.profiles(), []);
  const ligados = (meus.data ?? []).filter((item) => item.enabled);
  const [escolhido, setEscolhido] = useState<string | null>(null);
  const idioma = escolhido ?? ligados[0]?.language ?? "en";

  const profile = useQuery(() => englishApi.profile(idioma), [idioma]);
  // O nivelamento aberto vem do SERVIDOR, e não de um estado que morre ao
  // trocar de tela. Era só na memória da tela que o id existia: um F5 ou uma
  // ida ao Roadmap apagavam o caminho de volta e o progresso ficava gravado
  // no banco sem nada que soubesse alcançá-lo.
  const aberto = useQuery(() => englishApi.activeAssessment(idioma), [idioma]);
  // Os pontos de melhora DESTE idioma: sem o filtro, quem estuda dois
  // idiomas via os erros de um na tela do outro.
  const melhoras = useQuery(() => englishApi.improvements(idioma), [idioma]);
  // O nível por habilidade é calculado a cada abertura, a partir de todas as
  // respostas (nivelamento e treino): um número gravado ficaria velho no
  // primeiro exercício seguinte.
  const quadro = useQuery(() => englishApi.skills(idioma), [idioma]);
  // O treino de hoje, se já começou. Não cria nada: abrir a tela não gasta IA.
  const hoje = useQuery(() => englishApi.practiceToday(idioma), [idioma]);
  const [treino, setTreino] = useState<PracticeSession | null>(null);
  const comecar = useMutation(() => englishApi.startPractice(idioma));
  const [assessment, setAssessment] = useState<EnglishAssessment | null>(null);
  const start = useMutation(() => englishApi.startAssessment(idioma));
  const toggle = useMutation((enabled: boolean) => englishApi.update(idioma, { enabled }));

  if (profile.loading) return <Loading label="Carregando o módulo de idioma…" />;
  if (profile.error) return <ErrorState message={profile.error} onRetry={profile.reload} />;
  if (!profile.data) return null;

  const data = profile.data;
  // O nível de agora sai de todas as respostas, e não só do último
  // nivelamento: é assim que o treino diário aparece no número grande. O do
  // nivelamento continua dito embaixo, como referência.
  const nivelAtual = quadro.data?.overall.answered ? quadro.data.overall.level : data.cefr_level;
  const reached = nivelAtual ? BANDS.indexOf(nivelAtual as (typeof BANDS)[number]) + 1 : 0;
  // Um nivelamento aberto só vale como retomada se ainda faltar responder.
  const emAndamento =
    aberto.data && aberto.data.answered_count < aberto.data.item_count ? aberto.data : null;

  function recarregarProgresso() {
    profile.reload();
    quadro.reload();
    melhoras.reload();
    hoje.reload();
  }

  if (treino) {
    return (
      <TreinoDoDia
        inicial={treino}
        idioma={idioma}
        onSair={() => {
          setTreino(null);
          recarregarProgresso();
        }}
      />
    );
  }

  if (assessment) {
    return (
      <Placement
        assessment={assessment}
        onFinished={() => {
          setAssessment(null);
          aberto.reload();
          recarregarProgresso();
        }}
      />
    );
  }

  return (
    <div style={SCREEN_IN}>
      <header
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-end",
          gap: 16.8,
          marginBottom: 16.8,
        }}
      >
        <div style={{ flex: 1, minWidth: 250 }}>
          <div style={{ fontSize: 12.5, color: TEXT.muted }}>Módulo opcional</div>
          <h1 style={{ fontSize: 28, margin: 0 }}>Idioma para o trabalho</h1>
          {/* O seletor só aparece com dois ou mais idiomas ligados: com um só,
              um grupo de um botão é ruído — a tela já é daquele idioma. */}
          {ligados.length > 1 ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginTop: 8.4 }}>
              {ligados.map((item) => {
                const ativo = item.language === idioma;
                return (
                  <button
                    key={item.language}
                    type="button"
                    aria-pressed={ativo}
                    onClick={() => setEscolhido(item.language)}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 6,
                      font: "inherit",
                      fontSize: 12,
                      cursor: "pointer",
                      textTransform: "uppercase",
                      letterSpacing: ".06em",
                      border: `1px solid ${ativo ? ACC : "rgba(233,233,237,.16)"}`,
                      background: ativo ? "rgba(145,132,217,.13)" : "transparent",
                      color: ativo ? ACC : TEXT.muted,
                    }}
                  >
                    {item.language}
                  </button>
                );
              })}
            </div>
          ) : null}
          <p
            style={{
              margin: "5.6px 0 0",
              fontSize: 13.5,
              color: "rgba(233,233,237,.6)",
              maxWidth: "62ch",
            }}
          >
            Roda em paralelo ao roadmap técnico. Nivela por CEFR e treina com o vocabulário de quem
            trabalha com backend em time internacional.
          </p>
        </div>
        <label
          className="seg-opt"
          style={{
            border: "1px solid rgba(233,233,237,.16)",
            borderRadius: 8,
            color: data.enabled ? ACC : TEXT.muted,
            boxShadow: data.enabled ? RING : "none",
          }}
        >
          <input
            type="checkbox"
            checked={data.enabled}
            onChange={async () => {
              profile.set((current) => ({ ...current, enabled: !current.enabled }));
              await toggle.run(!data.enabled);
            }}
          />
          {data.enabled ? "Ativado" : "Desativado"}
        </label>
      </header>

      {!data.enabled ? (
        <p
          style={{
            padding: "44px 22.4px",
            borderRadius: 14,
            border: "1px dashed rgba(233,233,237,.22)",
            textAlign: "center",
            color: "rgba(233,233,237,.6)",
            fontSize: 14,
          }}
        >
          Módulo desativado. Ative acima para incluir {data.daily_goal_min} min de inglês por dia no
          plano.
        </p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))",
            gap: 11.2,
          }}
        >
          <CartaoDoTreino
            hoje={hoje.data}
            carregando={hoje.loading}
            comecando={comecar.pending}
            erro={comecar.error}
            onComecar={async () => {
              const sessao = await comecar.run();
              if (sessao) setTreino(sessao);
            }}
          />

          <Panel tone="section">
            <Kicker tone="section" style={{ display: "block", marginBottom: 8.4 }}>
              Seu nível
            </Kicker>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8.4 }}>
              <span style={{ fontSize: 34, lineHeight: 1 }}>{nivelAtual ?? "—"}</span>
              <span style={{ fontSize: 13, color: "rgba(233,233,237,.75)" }}>
                meta {data.target_level}
              </span>
            </div>
            <div aria-hidden style={{ display: "flex", gap: 4, marginTop: 14 }}>
              {BANDS.map((band, index) => (
                <span
                  key={band}
                  style={{
                    flex: 1,
                    height: 4,
                    borderRadius: 2,
                    background: index < reached ? ACC4 : "rgba(233,233,237,.18)",
                  }}
                />
              ))}
            </div>
            <p style={{ fontSize: 11.5, color: "rgba(233,233,237,.65)", margin: "8.4px 0 14px" }}>
              {data.cefr_level
                ? `Estimado com o nivelamento (${data.cefr_level}) e os treinos. Refaça o nivelamento quando quiser uma medida nova.`
                : "Sem nivelamento ainda. O teste leva cerca de 12 minutos — dá para treinar antes, e o nível se ajusta com as respostas."}
            </p>
            {emAndamento ? (
              <Retomar
                assessment={emAndamento}
                onContinuar={() => setAssessment(emAndamento)}
                onRecomecar={async () => {
                  const created = await start.run();
                  if (created) setAssessment(created);
                }}
                recomecando={start.pending}
              />
            ) : (
              <button
                type="button"
                className="btn btn-primary btn-block"
                disabled={start.pending}
                onClick={async () => {
                  const created = await start.run();
                  if (created) setAssessment(created);
                }}
              >
                {start.pending
                  ? "Preparando o teste…"
                  : data.cefr_level
                    ? "Refazer nivelamento"
                    : "Fazer o nivelamento"}
              </button>
            )}
            {start.error ? (
              <p style={{ fontSize: 12, color: "#cfa25e", marginTop: 8.4 }}>{start.error}</p>
            ) : null}
          </Panel>

          <QuadroDeHabilidades quadro={quadro.data} />

          <Melhoras dados={melhoras.data} />
        </div>
      )}
    </div>
  );
}


/**
 * A ponte de volta para um nivelamento que ficou pela metade.
 *
 * Antes, sair da tela abandonava o teste na prática: o progresso continuava
 * gravado, mas a única porta de entrada criava um teste NOVO — as respostas já
 * dadas viravam trabalho perdido sem que nada avisasse. O card diz quanto já
 * foi feito e deixa as duas saídas explícitas, em vez de escolher por conta
 * própria qual delas a pessoa queria.
 */
function Retomar({
  assessment,
  onContinuar,
  onRecomecar,
  recomecando,
}: {
  assessment: EnglishAssessment;
  onContinuar: () => void;
  onRecomecar: () => void;
  recomecando: boolean;
}) {
  const feito = Math.round((assessment.answered_count / assessment.item_count) * 100);
  return (
    <div>
      <div
        style={{
          padding: 11.2,
          borderRadius: 8,
          marginBottom: 8.4,
          border: `1px solid ${ACC}`,
          background: "rgba(145,132,217,.10)",
        }}
      >
        <div style={{ fontSize: 12.5, color: TEXT.full }}>Nivelamento em andamento</div>
        <div style={{ fontSize: 11.5, color: "rgba(233,233,237,.65)", margin: "4px 0 8.4px" }}>
          {assessment.answered_count} de {assessment.item_count} respondidas · {feito}%
        </div>
        <div
          aria-hidden
          style={{
            height: 4,
            borderRadius: 2,
            background: "rgba(233,233,237,.18)",
            overflow: "hidden",
          }}
        >
          <div style={{ width: `${feito}%`, height: "100%", background: ACC4 }} />
        </div>
      </div>
      <button type="button" className="btn btn-primary btn-block" onClick={onContinuar}>
        Continuar de onde parei
      </button>
      <button
        type="button"
        className="btn btn-ghost btn-block"
        style={{ marginTop: 5.6 }}
        disabled={recomecando}
        onClick={onRecomecar}
      >
        {recomecando ? "Preparando o teste…" : "Recomeçar do zero"}
      </button>
    </div>
  );
}

/**
 * O que a pessoa errou e ainda não recuperou.
 *
 * Errar era o único desfecho que o nivelamento jogava fora: o acerto virava
 * nota, o erro não virava nada. Mas o erro é a única coisa que o teste prova
 * de verdade sobre uma lacuna — e é o que precisa voltar. Cada item errado
 * entra na mesma fila de repetição espaçada que o quiz técnico usa.
 */
function Melhoras({ dados }: { dados: LanguageImprovements | null }) {
  const itens = dados?.items ?? [];

  return (
    <Panel>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8.4, marginBottom: 11.2 }}>
        <Kicker>Pontos de melhora</Kicker>
        {dados && dados.due_count > 0 ? (
          <span style={{ fontSize: 11.5, color: C.ambar }}>{dados.due_count} para rever</span>
        ) : null}
      </div>
      {itens.length === 0 ? (
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: 0 }}>
          Nada pendente. O que você errar no nivelamento ou no treino aparece aqui e volta no
          treino diário, com outras palavras.
        </p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {itens.slice(0, 6).map((item) => (
            <li
              key={item.id}
              style={{
                fontSize: 12.5,
                lineHeight: 1.45,
                padding: "8.4px 0",
                borderTop: `1px solid ${HAIRLINE}`,
              }}
            >
              <div style={{ color: "rgba(233,233,237,.8)" }}>{item.front}</div>
              <div style={{ color: TEXT.faint, marginTop: 4 }}>{item.back}</div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
