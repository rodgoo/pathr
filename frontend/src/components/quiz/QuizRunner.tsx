/**
 * O quiz do módulo.
 *
 * Uma pergunta por vez, e a correção vem no fim. Essa é uma mudança em
 * relação ao protótipo, que revelava a resposta a cada clique: a correção é
 * feita no servidor — é lá que está o gabarito, e é o mesmo momento em que a
 * proficiência por tag é atualizada com evidência. Revelar item a item pediria
 * um endpoint por questão e uma tentativa que não fecha, o que tornaria o
 * resultado impossível de auditar.
 *
 * A revisão no fim mostra cada questão com o que foi escolhido, o que era
 * certo e por quê — que é o que a explicação imediata dava, sem perder o
 * registro da tentativa.
 */

import { useEffect, useState } from "react";
import { quizzes as quizzesApi } from "@/api/endpoints";
import type { Quiz, QuizResult } from "@/api/types";
import { useMutation } from "@/hooks/useApi";
import { ACC, ACC4, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { ChoiceList } from "@/components/ui/ChoiceList";
import { ErrorState } from "@/components/ui/States";
import { Panel } from "@/components/ui/primitives";
import { CodeBlock } from "./CodeBlock";

/**
 * Onde a pessoa parou neste quiz.
 *
 * Por quiz, e nao global: dois quizzes abertos em abas diferentes sao duas
 * posicoes independentes, e uma chave so faria um sobrescrever o outro.
 */
const chaveDoProgresso = (quizId: string) => `pathr:quiz:${quizId}`;

interface Progresso {
  index: number;
  answers: Record<string, number>;
}

function lerProgresso(quizId: string): Progresso {
  try {
    const bruto = window.localStorage.getItem(chaveDoProgresso(quizId));
    if (!bruto) return { index: 0, answers: {} };
    const guardado = JSON.parse(bruto) as Partial<Progresso>;
    return { index: guardado.index ?? 0, answers: guardado.answers ?? {} };
  } catch {
    return { index: 0, answers: {} };
  }
}

export function QuizRunner({
  quiz,
  onFinished,
  onSubmitted,
}: {
  quiz: Quiz;
  onFinished?: () => void;
  /**
   * A tentativa fechou no servidor. Quem guardou o enunciado usa isto para
   * esquecê-lo: recarregar a página depois da correção deve levar ao botão de
   * gerar outro quiz, não a refazer um quiz que já tem nota.
   */
  onSubmitted?: () => void;
}) {
  // Inicializador preguicoso: le o storage uma vez, na montagem.
  const [progresso] = useState(() => lerProgresso(quiz.id));
  const [index, setIndex] = useState(progresso.index);
  const [answers, setAnswers] = useState<Record<string, number>>(progresso.answers);
  const [startedAt] = useState(() => Date.now());
  const [result, setResult] = useState<QuizResult | null>(null);

  // Grava a cada resposta e a cada avanco. Sair da tela no meio de um quiz de
  // dez questoes e comum -- consultar o material e o objetivo do produto -- e
  // voltar para a questao 1 com tudo em branco faz a pessoa desistir.
  useEffect(() => {
    if (result) return;
    try {
      window.localStorage.setItem(
        chaveDoProgresso(quiz.id),
        JSON.stringify({ index, answers }),
      );
    } catch {
      // Armazenamento bloqueado: o quiz continua, so nao lembra.
    }
  }, [quiz.id, index, answers, result]);

  const submit = useMutation(() =>
    quizzesApi.submit(quiz.id, answers, Math.round((Date.now() - startedAt) / 1000)),
  );

  if (result) {
    return <Review quiz={quiz} result={result} onRestart={onFinished} />;
  }

  const question = quiz.questions[index];
  if (!question) return null;

  const picked = answers[question.id];
  const last = index + 1 >= quiz.questions.length;

  async function advance() {
    if (!last) {
      setIndex((current) => current + 1);
      return;
    }
    const finished = await submit.run();
    if (finished) {
      setResult(finished);
      onSubmitted?.();
      // Quiz enviado: o progresso guardado so atrapalharia se a pessoa
      // reabrisse este mesmo quiz, que agora tem tentativa fechada.
      try {
        window.localStorage.removeItem(chaveDoProgresso(quiz.id));
      } catch {
        // Ignorado pelo mesmo motivo da escrita.
      }
    }
  }

  return (
    <Panel pad={22.4}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 8.4,
          marginBottom: 16.8,
        }}
      >
        <span
          style={{ fontSize: 11, letterSpacing: ".08em", textTransform: "uppercase", color: ACC }}
        >
          Pergunta {index + 1} de {quiz.questions.length}
        </span>
        <span className="tag tag-outline">{question.difficulty}</span>
        <span style={{ marginLeft: "auto", fontSize: 11.5, color: TEXT.faint }}>
          {Object.keys(answers).length} respondidas
        </span>
      </div>

      <h3 style={{ fontSize: 17, lineHeight: 1.35, marginBottom: 16.8, fontWeight: 500 }}>
        {question.prompt}
      </h3>

      {question.code_snippet ? (
        <div style={{ marginBottom: 16.8 }}>
          <CodeBlock
            label="Trecho da questão"
            lines={question.code_snippet.split("\n")}
            filename={question.code_language ?? undefined}
          />
        </div>
      ) : null}

      <ChoiceList
        label="Opções de resposta"
        options={question.options}
        pick={picked ?? null}
        letters
        onPick={(choice) => setAnswers((current) => ({ ...current, [question.id]: choice }))}
      />

      {submit.error ? <ErrorState message={submit.error} onRetry={advance} /> : null}

      <div
        style={{ display: "flex", gap: 8.4, marginTop: 16.8, alignItems: "center", flexWrap: "wrap" }}
      >
        {index > 0 ? (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setIndex((current) => current - 1)}
          >
            Voltar
          </button>
        ) : null}
        <button
          type="button"
          className="btn btn-primary"
          onClick={advance}
          disabled={picked === undefined || submit.pending}
        >
          {submit.pending ? "Corrigindo…" : last ? "Enviar respostas" : "Próxima"}
        </button>
        {picked === undefined ? (
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>Escolha uma alternativa.</span>
        ) : null}
      </div>
    </Panel>
  );
}


/**
 * A correção.
 *
 * Cada questão aparece com o que foi escolhido, o que era certo e a
 * explicação — inclusive as acertadas, porque saber POR QUE acertou é o que
 * separa aprendizado de sorte.
 */
function Review({
  quiz,
  result,
  onRestart,
}: {
  quiz: Quiz;
  result: QuizResult;
  onRestart?: () => void;
}) {
  const byId = new Map(quiz.questions.map((question) => [question.id, question]));
  const passed = result.score >= 70;

  return (
    <Panel pad={22.4}>
      <div style={{ textAlign: "center", paddingBottom: 22.4 }}>
        <div style={{ fontSize: 42, color: passed ? ACC4 : C.ambar, lineHeight: 1 }}>
          {result.correct_count}/{result.total}
        </div>
        <p style={{ fontSize: 14, color: "rgba(233,233,237,.7)", margin: "8.4px 0 0" }}>
          {passed
            ? "Bom resultado — a proficiência das tags deste quiz subiu no seu perfil."
            : "Abaixo de 70%. Revise o material antes de seguir; o perfil não subiu."}
        </p>
        <ReviewOutcome review={result.review} />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
        {result.results.map((item, position) => {
          const question = byId.get(item.question_id);
          if (!question) return null;
          return (
            <div
              key={item.question_id}
              style={{
                padding: 14,
                borderRadius: 8,
                background: "#1b1d2b",
                borderLeft: `2px solid ${item.is_correct ? C.verde : C.ambar}`,
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 8.4,
                  alignItems: "baseline",
                  marginBottom: 5.6,
                  fontSize: 11.5,
                  color: TEXT.faint,
                }}
              >
                <span>Pergunta {position + 1}</span>
                <span style={{ marginLeft: "auto", color: item.is_correct ? C.verde : C.ambar }}>
                  {item.is_correct ? "acertou" : "errou"}
                </span>
              </div>
              <div style={{ fontSize: 14, marginBottom: 8.4 }}>{question.prompt}</div>
              <div style={{ fontSize: 12.5, color: TEXT.muted, marginBottom: 4 }}>
                Correta: {question.options[item.correct_index]}
              </div>
              {!item.is_correct && item.answer !== null ? (
                <div style={{ fontSize: 12.5, color: TEXT.faint, marginBottom: 8.4 }}>
                  Você escolheu: {question.options[item.answer]}
                </div>
              ) : null}
              <div style={{ fontSize: 13, color: "rgba(233,233,237,.85)", lineHeight: 1.5 }}>
                {item.explanation}
              </div>
            </div>
          );
        })}
      </div>

      {onRestart ? (
        <button
          type="button"
          className="btn btn-secondary"
          style={{ marginTop: 16.8 }}
          onClick={onRestart}
        >
          Gerar outro quiz
        </button>
      ) : null}
    </Panel>
  );
}

/**
 * O que o erro virou.
 *
 * Dizer isto no fim do quiz é o que separa "errei" de "vou ver de novo". Sem
 * a frase, a reciclagem acontece em silêncio e a pessoa reencontra a mesma
 * ideia semanas depois sem entender por quê — ou pior, acha que o app está
 * repetindo pergunta por preguiça.
 *
 * O texto diz "com outras palavras" de propósito: se voltasse igual, decorar
 * o enunciado bastaria, e é exatamente isso que a reescrita evita.
 */
function ReviewOutcome({ review }: { review?: { volta: string[]; aprendido: string[] } }) {
  if (!review) return null;
  const { volta, aprendido } = review;
  if (volta.length === 0 && aprendido.length === 0) return null;

  return (
    <div
      style={{
        marginTop: 16.8,
        paddingTop: 14,
        borderTop: `1px solid ${HAIRLINE}`,
        fontSize: 12.5,
        lineHeight: 1.6,
        color: TEXT.muted,
      }}
    >
      {aprendido.length > 0 ? (
        <div style={{ color: C.verde }}>
          {aprendido.length === 1
            ? "1 conceito que você tinha errado voltou e você acertou."
            : `${aprendido.length} conceitos que você tinha errado voltaram e você acertou.`}{" "}
          Eles vão rarear até sumir.
        </div>
      ) : null}
      {volta.length > 0 ? (
        <div style={{ marginTop: aprendido.length > 0 ? 5.6 : 0 }}>
          {volta.length === 1 ? "1 conceito volta" : `${volta.length} conceitos voltam`} no próximo
          quiz desta trilha, com outras palavras: {volta.join(" · ")}
        </div>
      ) : null}
    </div>
  );
}
