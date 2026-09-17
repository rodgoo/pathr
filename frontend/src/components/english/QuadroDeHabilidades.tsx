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
import { useT, type Traduzir } from "@/lib/i18n";
import { ACC4, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { Kicker, Panel } from "@/components/ui/primitives";

/** skill -> chave i18n do rótulo da habilidade. */
export const NOME_DA_HABILIDADE: Record<string, string> = {
  grammar: "idiomas.habilidades.grammar",
  vocabulary: "idiomas.habilidades.vocabulary",
  reading: "idiomas.habilidades.reading",
  listening: "idiomas.habilidades.listening",
  writing: "idiomas.habilidades.writing",
  speaking: "idiomas.habilidades.speaking",
  business: "idiomas.habilidades.business",
};

/** O rótulo traduzido da habilidade, ou o próprio código quando desconhecido. */
export function nomeDaHabilidade(skill: string, t: Traduzir): string {
  const chave = NOME_DA_HABILIDADE[skill];
  return chave ? t(chave) : skill;
}

const CONFIANCA: Record<SkillLevel["confidence"], string> = {
  alta: "idiomas.confianca.alta",
  media: "idiomas.confianca.media",
  inicial: "idiomas.confianca.inicial",
  sem_dados: "idiomas.confianca.semDados",
};

const SITUACAO: Record<SkillTopic["status"], { rotulo: string; cor: string }> = {
  reforcar: { rotulo: "idiomas.situacao.reforcar", cor: C.ambar },
  progredindo: { rotulo: "idiomas.situacao.progredindo", cor: ACC4 },
  dominado: { rotulo: "idiomas.situacao.dominado", cor: C.verde },
  poucos_dados: { rotulo: "idiomas.situacao.poucosDados", cor: TEXT.faint },
};

export function QuadroDeHabilidades({ quadro }: { quadro: SkillBoard | null }) {
  const t = useT();
  const habilidades = quadro?.skills ?? [];
  const algumaComDados = habilidades.some((h) => h.answered > 0);

  return (
    <Panel>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8.4, marginBottom: 11.2 }}>
        <Kicker>{t("idiomas.quadro.porHabilidade")}</Kicker>
        {quadro?.overall.level ? (
          <span style={{ fontSize: 11.5, color: TEXT.faint, marginLeft: "auto" }}>
            {t("idiomas.quadro.nosTreinos", { nivel: quadro.overall.level })}
          </span>
        ) : null}
      </div>

      {!algumaComDados ? (
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: 0 }}>
          {t("idiomas.quadro.semDados")}
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
  const t = useT();
  const [aberta, setAberta] = useState(false);
  const nome = nomeDaHabilidade(habilidade.skill, t);
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
              {aReforcar === 1
                ? t("idiomas.quadro.topicoReforcar", { n: aReforcar })
                : t("idiomas.quadro.topicosReforcar", { n: aReforcar })}
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
              {t(CONFIANCA[habilidade.confidence])} ·{" "}
              {habilidade.answered === 1
                ? t("idiomas.quadro.respostaUm", { n: habilidade.answered })
                : t("idiomas.quadro.respostaVarias", { n: habilidade.answered })}
            </div>
          </>
        ) : (
          <div style={{ fontSize: 11, color: TEXT.faint, marginTop: 4 }}>{t(CONFIANCA.sem_dados)}</div>
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
                {t(SITUACAO[topico.status].rotulo)}
              </span>
              <span style={{ marginLeft: "auto", color: TEXT.faint, whiteSpace: "nowrap" }}>
                {t("idiomas.quadro.correctDe", { correct: topico.correct, total: topico.answered })}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
