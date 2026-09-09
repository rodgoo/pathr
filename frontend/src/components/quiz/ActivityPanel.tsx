/**
 * A atividade prática do módulo.
 *
 * Escrever a solução do zero é o ponto: o modo "sem IA" existe porque a
 * pessoa que pediu este produto queria parar de depender de assistente para
 * codar. O que fica registrado é o texto dela, e a correção compara — não
 * completa.
 *
 * O envio ainda não tem endpoint: `POST /activities` não existe no backend, e
 * a tela diz isso em vez de fingir que enviou. O rascunho fica no navegador
 * para não se perder enquanto isso.
 */

import { useEffect, useState } from "react";
import type { RoadmapNode } from "@/api/types";
import { ACC3, C, TEXT } from "@/lib/tokens";
import { Kicker, Panel } from "@/components/ui/primitives";

/** Chave do rascunho no navegador, por módulo. */
const draftKey = (nodeId: string) => `pathr:atividade:${nodeId}`;

function readDraft(nodeId: string): string {
  try {
    return window.localStorage.getItem(draftKey(nodeId)) ?? "";
  } catch {
    // Navegador com armazenamento bloqueado. O campo simplesmente começa
    // vazio — perder o rascunho é ruim, quebrar a tela é pior.
    return "";
  }
}

export function ActivityPanel({ node }: { node: RoadmapNode }) {
  const [answer, setAnswer] = useState(() => readDraft(node.id));

  useEffect(() => setAnswer(readDraft(node.id)), [node.id]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        window.localStorage.setItem(draftKey(node.id), answer);
      } catch {
        // idem: sem armazenamento, o rascunho só não persiste.
      }
    }, 400);
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
        A correção automática ainda não está no ar. Seu rascunho fica salvo neste navegador; quando
        o endpoint existir, o envio aparece aqui.
      </div>

      <div style={{ marginTop: 11.2, fontSize: 11.5, color: TEXT.faint }}>
        {answer.trim().length} caracteres escritos
      </div>
    </Panel>
  );
}
