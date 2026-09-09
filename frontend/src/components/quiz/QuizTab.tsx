/**
 * A aba de quiz do módulo.
 *
 * O quiz é GERADO sob demanda, a partir das tags do módulo aberto — não há
 * banco de questões pronto. É o que permite a pergunta ser sobre o que a
 * pessoa está estudando agora, no nível em que ela está.
 */

import { quizzes as quizzesApi } from "@/api/endpoints";
import type { Quiz, RoadmapNode } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useMutation } from "@/hooks/useApi";
import { TEXT } from "@/lib/tokens";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { Panel } from "@/components/ui/primitives";
import { QuizRunner } from "./QuizRunner";
import { useState } from "react";

export function QuizTab({ node }: { node: RoadmapNode | null }) {
  const { dispatch } = useAppState();
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const generate = useMutation(() =>
    quizzesApi.generate({ node_id: node?.id, question_count: 6, difficulty: "medio" }),
  );

  async function start() {
    const created = await generate.run();
    if (created) {
      setQuiz(created);
      dispatch({ type: "openQuiz", quizId: created.id });
    }
  }

  if (quiz) {
    return (
      <QuizRunner
        quiz={quiz}
        onFinished={() => {
          setQuiz(null);
          dispatch({ type: "openQuiz", quizId: null });
        }}
      />
    );
  }

  if (!node) {
    return (
      <EmptyState
        title="Nenhum módulo aberto"
        description="Abra um módulo do roadmap para gerar um quiz sobre ele."
      />
    );
  }

  return (
    <Panel pad={22.4}>
      <h3 style={{ fontSize: 18, margin: "0 0 8.4px", fontWeight: 500 }}>
        Quiz de {node.title}
      </h3>
      <p style={{ fontSize: 13.5, color: "rgba(233,233,237,.7)", maxWidth: "60ch" }}>
        Seis questões escritas na hora, sobre as tecnologias deste módulo e calibradas pelo seu
        nível atual. O resultado atualiza a proficiência no seu perfil — é a única evidência de
        domínio que o app coleta.
      </p>

      {generate.error ? <ErrorState message={generate.error} onRetry={start} /> : null}

      <div style={{ display: "flex", gap: 8.4, alignItems: "center", marginTop: 14, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary" onClick={start} disabled={generate.pending}>
          {generate.pending ? "Escrevendo as questões…" : "Começar quiz"}
        </button>
        <span style={{ fontSize: 11.5, color: TEXT.faint }}>
          {generate.pending ? "A IA leva alguns segundos." : "Leva cerca de 10 minutos."}
        </span>
      </div>
    </Panel>
  );
}
