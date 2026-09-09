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
import type { EnglishAssessment } from "@/api/types";
import { useMutation, useQuery } from "@/hooks/useApi";
import { ACC, ACC4, RING, TEXT } from "@/lib/tokens";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { Placement } from "@/components/english/Placement";

const BANDS = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;

export function EnglishPage() {
  const profile = useQuery(() => englishApi.profile(), []);
  const [assessment, setAssessment] = useState<EnglishAssessment | null>(null);
  const start = useMutation(() => englishApi.startAssessment());
  const toggle = useMutation((enabled: boolean) => englishApi.update({ enabled }));

  if (profile.loading) return <Loading label="Carregando o módulo de idioma…" />;
  if (profile.error) return <ErrorState message={profile.error} onRetry={profile.reload} />;
  if (!profile.data) return null;

  const data = profile.data;
  const reached = data.cefr_level ? BANDS.indexOf(data.cefr_level as (typeof BANDS)[number]) + 1 : 0;

  if (assessment) {
    return (
      <Placement
        assessment={assessment}
        onFinished={() => {
          setAssessment(null);
          profile.reload();
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
          <h1 style={{ fontSize: 28, margin: 0 }}>Inglês corporativo</h1>
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
          <Panel tone="section">
            <Kicker tone="section" style={{ display: "block", marginBottom: 8.4 }}>
              Seu nível
            </Kicker>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8.4 }}>
              <span style={{ fontSize: 34, lineHeight: 1 }}>{data.cefr_level ?? "—"}</span>
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
                ? "Nivelamento feito. Refaça quando sentir que evoluiu."
                : "Sem nivelamento ainda. O teste leva cerca de 12 minutos e destrava a prática."}
            </p>
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
            {start.error ? (
              <p style={{ fontSize: 12, color: "#cfa25e", marginTop: 8.4 }}>{start.error}</p>
            ) : null}
          </Panel>

          <SubScores scores={data.sub_scores} />
        </div>
      )}
    </div>
  );
}


/**
 * O detalhamento por habilidade do último nivelamento.
 *
 * Mostra o número por habilidade porque é ele que diz onde praticar — um
 * "B1" único esconde que a leitura vai bem e a escrita não.
 */
function SubScores({ scores }: { scores: Record<string, number> }) {
  const LABEL: Record<string, string> = {
    grammar: "Gramática",
    vocabulary: "Vocabulário",
    reading: "Leitura",
    listening: "Escuta",
    writing: "Escrita",
    speaking: "Fala",
    business: "Corporativo",
  };
  const entries = Object.entries(scores);

  return (
    <Panel>
      <Kicker style={{ display: "block", marginBottom: 11.2 }}>Por habilidade</Kicker>
      {entries.length === 0 ? (
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: 0 }}>
          Faça o nivelamento para ver onde está mais forte e onde praticar.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
          {entries.map(([skill, score]) => (
            <div key={skill}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 12,
                  marginBottom: 4,
                }}
              >
                <span>{LABEL[skill] ?? skill}</span>
                <span style={{ color: TEXT.faint }}>{score}%</span>
              </div>
              <div
                style={{
                  height: 3,
                  borderRadius: 2,
                  background: "rgba(233,233,237,.12)",
                  overflow: "hidden",
                }}
              >
                <div style={{ height: "100%", width: `${score}%`, background: ACC4 }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
