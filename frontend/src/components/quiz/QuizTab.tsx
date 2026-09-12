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
import { useEffect, useState } from "react";

/**
 * O quiz gerado, guardado no aparelho.
 *
 * As questões são escritas pela IA na hora e não existem em lugar nenhum
 * depois disso: se a tela cai antes do envio — F5, o sistema recolhendo a
 * memória do app no celular, o navegador fechado sem querer — a tentativa
 * some junto, e a pessoa volta ao botão "começar quiz" com o progresso das
 * respostas gravado para um quiz que já não existe.
 *
 * Guardar o enunciado ao lado das respostas (que moram em `pathr:quiz:<id>`,
 * dentro do QuizRunner) é o que faz "continue de onde parou" valer também
 * para o quiz. A chave é por módulo: cada módulo tem o seu.
 */
const chaveDoQuiz = (nodeId: string) => `pathr:quiz-aberto:${nodeId}`;

function lerQuizAberto(nodeId: string | undefined): Quiz | null {
  if (!nodeId) return null;
  try {
    const bruto = window.localStorage.getItem(chaveDoQuiz(nodeId));
    if (!bruto) return null;
    const guardado = JSON.parse(bruto) as Quiz;
    // Um quiz sem questões é lixo de uma versão anterior do formato; tratar
    // como ausente é melhor do que renderizar uma tela vazia sem saída.
    return guardado?.questions?.length ? guardado : null;
  } catch {
    return null;
  }
}

function esquecerQuiz(nodeId: string | undefined): void {
  if (!nodeId) return;
  try {
    window.localStorage.removeItem(chaveDoQuiz(nodeId));
  } catch {
    // Armazenamento bloqueado: nada a fazer, e nada que impeça seguir.
  }
}

export function QuizTab({ node }: { node: RoadmapNode | null }) {
  const { dispatch } = useAppState();
  // Inicializador preguicoso: le o storage uma vez, na montagem.
  const [quiz, setQuiz] = useState<Quiz | null>(() => lerQuizAberto(node?.id));
  const generate = useMutation(() =>
    quizzesApi.generate({ node_id: node?.id, question_count: 6, difficulty: "adaptativo" }),
  );

  // Trocar de módulo com a aba de quiz aberta precisa trazer o quiz DAQUELE
  // módulo — sem isto, o estado inicial da montagem ficaria valendo para o
  // módulo seguinte.
  useEffect(() => {
    setQuiz(lerQuizAberto(node?.id));
  }, [node?.id]);

  useEffect(() => {
    if (!node?.id || !quiz) return;
    try {
      window.localStorage.setItem(chaveDoQuiz(node.id), JSON.stringify(quiz));
    } catch {
      // Armazenamento bloqueado: o quiz continua, so nao sobrevive ao F5.
    }
  }, [node?.id, quiz]);

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
        onSubmitted={() => esquecerQuiz(node?.id)}
        onFinished={() => {
          esquecerQuiz(node?.id);
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
