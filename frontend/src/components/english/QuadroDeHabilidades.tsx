/**
 * O nível de cada habilidade e como a pessoa vai em cada tópico dela.
 *
 * Substitui a lista de porcentagens que ficava aqui. Aquela mostrava "100%"
 * para duas perguntas certas e "33%" para uma de três — acerto num sorteio
 * pequeno desenhado como se fosse medida. Agora cada habilidade mostra:
 *
 * - o NÍVEL CEFR estimado, considerando a dificuldade de cada item e o chute;
 * - quanto já andou dentro da banda (a barra), que é onde o treino diário
 *   aparece dia a dia antes de o nível mudar de letra;
 * - a CONFIANÇA, em palavras: com três respostas a tela diz "estimativa
 *   inicial", em vez de afirmar com a firmeza de um teste de cem;
 * - os TÓPICOS, do que precisa de reforço ao que já está dominado.
 *
 * O cálculo mora no servidor (services/proficiencia_idioma.py) e foi conferido
 * contra alunos simulados de nível conhecido.
 */

import { useState } from "react";
import type { SkillBoard, SkillLevel, SkillTopic } from "@/api/types";
import { ACC4, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { Kicker, Panel } from "@/components/ui/primitives";

export const NOME_DA_HABILIDADE: Record<string, string> = {
  grammar: "Gramática",
  vocabulary: "Vocabulário",
  reading: "Leitura",
  listening: "Escuta",
  writing: "Escrita",
  speaking: "Fala",
  business: "Corporativo",
};

const CONFIANCA: Record<SkillLevel["confidence"], string> = {
  alta: "estimativa firme",
  media: "estimativa razoável",
  inicial: "estimativa inicial — treine mais para firmar",
  sem_dados: "sem respostas ainda",
};

const SITUACAO: Record<SkillTopic["status"], { rotulo: string; cor: string }> = {
  reforcar: { rotulo: "a reforçar", cor: C.ambar },
  progredindo: { rotulo: "progredindo", cor: ACC4 },
  dominado: { rotulo: "dominado", cor: C.verde },
  poucos_dados: { rotulo: "poucos dados", cor: TEXT.faint },
};

export function QuadroDeHabilidades({ quadro }: { quadro: SkillBoard | null }) {
  const habilidades = quadro?.skills ?? [];
  const algumaComDados = habilidades.some((h) => h.answered > 0);

  return (
    <Panel>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8.4, marginBottom: 11.2 }}>
        <Kicker>Por habilidade</Kicker>
        {quadro?.overall.level ? (
          <span style={{ fontSize: 11.5, color: TEXT.faint, marginLeft: "auto" }}>
            geral {quadro.overall.level}
          </span>
        ) : null}
      </div>

      {!algumaComDados ? (
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: 0 }}>
          Faça o nivelamento ou o treino de hoje para ver seu nível em cada habilidade.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {habilidades.map((habilidade) => (
            <LinhaDaHabilidade key={habilidade.skill} habilidade={habilidade} />
          ))}
        </div>
      )}
    </Panel>
  );
}

function LinhaDaHabilidade({ habilidade }: { habilidade: SkillLevel }) {
  const [aberta, setAberta] = useState(false);
  const nome = NOME_DA_HABILIDADE[habilidade.skill] ?? habilidade.skill;
  const aReforcar = habilidade.topics.filter((t) => t.status === "reforcar").length;
  const semDados = habilidade.answered === 0;

  return (
    <div style={{ padding: "9.8px 0", borderTop: `1px solid ${HAIRLINE}` }}>
      <button
        type="button"
        onClick={() => setAberta((atual) => !atual)}
        aria-expanded={aberta}
        disabled={semDados}
        style={{
          width: "100%",
          border: 0,
          background: "transparent",
          padding: 0,
          font: "inherit",
          color: "inherit",
          textAlign: "left",
          cursor: semDados ? "default" : "pointer",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8.4 }}>
          <span style={{ fontSize: 13 }}>{nome}</span>
          {aReforcar > 0 ? (
            <span style={{ fontSize: 11, color: C.ambar }}>
              {aReforcar} {aReforcar === 1 ? "tópico" : "tópicos"} a reforçar
            </span>
          ) : null}
          <span
            style={{
              marginLeft: "auto",
              fontSize: 12.5,
              fontWeight: 600,
              color: semDados ? TEXT.faint : TEXT.full,
              minWidth: 26,
              textAlign: "right",
            }}
          >
            {habilidade.level ?? "—"}
          </span>
        </div>

        {!semDados ? (
          <>
            <div
              aria-hidden
              style={{
                height: 3,
                borderRadius: 2,
                background: "rgba(233,233,237,.12)",
                overflow: "hidden",
                margin: "6px 0 4px",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${Math.round(habilidade.progress_in_band * 100)}%`,
                  background: ACC4,
                  opacity: habilidade.confidence === "inicial" ? 0.5 : 1,
                }}
              />
            </div>
            <div style={{ fontSize: 11, color: TEXT.faint }}>
              {CONFIANCA[habilidade.confidence]} · {habilidade.answered}{" "}
              {habilidade.answered === 1 ? "resposta" : "respostas"}
            </div>
          </>
        ) : (
          <div style={{ fontSize: 11, color: TEXT.faint, marginTop: 4 }}>{CONFIANCA.sem_dados}</div>
        )}
      </button>

      {aberta && habilidade.topics.length > 0 ? (
        <ul style={{ listStyle: "none", margin: "8.4px 0 0", padding: 0 }}>
          {habilidade.topics.map((topico) => (
            <li
              key={topico.topic}
              style={{ display: "flex", alignItems: "baseline", gap: 8.4, fontSize: 12, padding: "3.5px 0" }}
            >
              <span style={{ color: "rgba(233,233,237,.82)" }}>{topico.topic}</span>
              <span style={{ fontSize: 11, color: SITUACAO[topico.status].cor }}>
                {SITUACAO[topico.status].rotulo}
              </span>
              <span style={{ marginLeft: "auto", color: TEXT.faint, whiteSpace: "nowrap" }}>
                {topico.correct} de {topico.answered}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
