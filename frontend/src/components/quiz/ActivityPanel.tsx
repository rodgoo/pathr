/**
 * A atividade prática do módulo.
 *
 * Escrever a solução do zero é o ponto: o modo "sem IA" existe porque a
 * pessoa que pediu este produto queria parar de depender de assistente para
 * codar. O que fica registrado é o texto dela, e a correção compara — não
 * completa.
 *
 * A correção automática ainda não tem endpoint. O rascunho, sim: ele mora no
 * SERVIDOR (`PUT /roadmap/nodes/{id}/draft`), e não mais no `localStorage`.
 * Preso a um navegador, a solução escrita do zero — o trabalho mais caro
 * desta tela — se perdia ao trocar de máquina, que é justamente quando alguém
 * mais precisa dela de volta.
 *
 * Grava sozinho, com uma pausa depois da última tecla: um botão "salvar" num
 * campo desses é uma chance a mais de sair da página sem apertar.
 */

import { useEffect, useRef, useState } from "react";
import { roadmap as roadmapApi } from "@/api/endpoints";
import type { RoadmapNode } from "@/api/types";
import { ACC3, C, TEXT } from "@/lib/tokens";
import { Kicker, Panel } from "@/components/ui/primitives";

/** Quanto tempo sem digitar antes de gravar. Curto o bastante para não perder
 * trabalho, longo o bastante para não mandar uma requisição por tecla. */
const PAUSA_MS = 900;

type Estado = "carregando" | "ocioso" | "gravando" | "salvo" | "erro";

export function ActivityPanel({ node }: { node: RoadmapNode }) {
  const [answer, setAnswer] = useState("");
  const [estado, setEstado] = useState<Estado>("carregando");
  // O que o servidor já tem. Sem isto, a gravação automática dispararia uma
  // vez logo após a carga, gravando exatamente o que acabou de ser lido.
  const gravado = useRef<string | null>(null);

  useEffect(() => {
    let vivo = true;
    setEstado("carregando");
    gravado.current = null;
    void roadmapApi
      .draft(node.id)
      .then((resposta) => {
        if (!vivo) return;
        setAnswer(resposta.content);
        gravado.current = resposta.content;
        setEstado("ocioso");
      })
      .catch(() => {
        if (!vivo) return;
        // Campo vazio e editável é melhor que uma tela de erro: o que a
        // pessoa escrever a partir daqui ainda será gravado.
        gravado.current = "";
        setEstado("erro");
      });
    return () => {
      vivo = false;
    };
  }, [node.id]);

  useEffect(() => {
    if (gravado.current === null || answer === gravado.current) return;
    const timer = window.setTimeout(async () => {
      setEstado("gravando");
      try {
        await roadmapApi.saveDraft(node.id, answer);
        gravado.current = answer;
        setEstado("salvo");
      } catch {
        setEstado("erro");
      }
    }, PAUSA_MS);
    return () => window.clearTimeout(timer);
  }, [node.id, answer]);

  const objective = node.objectives[0];

  return (
    <Panel pad={22.4}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 8.4,
          alignItems: "center",
          marginBottom: 14,
        }}
      >
        <Kicker>Atividade prática</Kicker>
        <span className="tag tag-outline">sem IA</span>
      </div>

      <h3 style={{ fontSize: 18, marginBottom: 8.4, fontWeight: 500 }}>{node.title}</h3>
      <p style={{ fontSize: 13.5, color: "rgba(233,233,237,.7)", maxWidth: "62ch" }}>
        {objective ? (
          <>
            Entregue o que o módulo pede:{" "}
            <span style={{ color: ACC3 }}>{objective.toLowerCase()}</span>. Escreva a solução
            inteira — a correção compara com a referência e aponta o que difere.
          </>
        ) : (
          "Escreva sua solução para este módulo. A correção compara com a referência e aponta o que difere."
        )}
      </p>

      <div className="field" style={{ marginTop: 14 }}>
        <label htmlFor="activity-answer">Sua resposta</label>
        <textarea
          id="activity-answer"
          className="input"
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          placeholder="Escreva aqui, do zero."
          style={{ minHeight: 200, fontFamily: "ui-monospace, Menlo, monospace", fontSize: 13 }}
        />
      </div>

      <div
        style={{
          marginTop: 11.2,
          padding: "11.2px 14px",
          borderRadius: 8,
          background: "#1b1d2b",
          borderLeft: `2px solid ${C.ambar}`,
          fontSize: 12.5,
          color: "rgba(233,233,237,.75)",
        }}
      >
        A correção automática ainda não está no ar. Seu rascunho fica salvo na sua conta e
        acompanha você em qualquer dispositivo; quando o endpoint existir, o envio aparece aqui.
      </div>

      <div
        style={{
          marginTop: 11.2,
          display: "flex",
          gap: 8.4,
          fontSize: 11.5,
          color: TEXT.faint,
        }}
      >
        <span>{answer.trim().length} caracteres escritos</span>
        <span role="status" style={{ color: estado === "erro" ? C.ambar : TEXT.faint }}>
          {estado === "carregando" ? "carregando o rascunho…" : null}
          {estado === "gravando" ? "gravando…" : null}
          {estado === "salvo" ? "gravado na sua conta" : null}
          {estado === "erro" ? "não consegui gravar — o texto continua aqui" : null}
        </span>
      </div>
    </Panel>
  );
}
