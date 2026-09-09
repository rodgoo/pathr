/**
 * O teste de nivelamento, item a item.
 *
 * Aqui a correção É imediata, ao contrário do quiz técnico: o backend expõe
 * `POST /english/assessment/{id}/answer`, que devolve o gabarito e ao mesmo
 * tempo calibra a dificuldade do próximo lote. Um envio em bloco no fim
 * tiraria justamente a adaptação que faz o teste convergir em 20 itens.
 *
 * O enunciado fica em inglês e a explicação em português — a pessoa está
 * aprendendo, e o ensino acontece na língua dela.
 */

import { useState } from "react";
import { english as englishApi } from "@/api/endpoints";
import type { EnglishAnswerResult, EnglishAssessment } from "@/api/types";
import { useMutation } from "@/hooks/useApi";
import { ACC, ACC4, C, TEXT } from "@/lib/tokens";
import { ChoiceList } from "@/components/ui/ChoiceList";
import { ErrorState, Loading } from "@/components/ui/States";
import { Panel, SCREEN_IN } from "@/components/ui/primitives";

export function Placement({
  assessment,
  onFinished,
}: {
  assessment: EnglishAssessment;
  onFinished: () => void;
}) {
  const [current, setCurrent] = useState(assessment);
  const [pick, setPick] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<EnglishAnswerResult | null>(null);

  const answer = useMutation((itemId: string, choice: number) =>
    englishApi.answer(current.id, itemId, choice),
  );
  const reload = useMutation(() => englishApi.getAssessment(current.id));

  const item = current.items[0];

  if (feedback?.finished) {
    return <Result result={feedback} onDone={onFinished} />;
  }

  if (!item) {
    // O lote acabou e o próximo já foi gerado no servidor — buscar de novo é
    // o que traz os itens novos.
    return (
      <Panel pad={22.4}>
        <Loading label="Preparando as próximas perguntas…" />
        <button
          type="button"
          className="btn btn-secondary btn-block"
          onClick={async () => {
            const next = await reload.run();
            if (next) {
              setCurrent(next);
              setFeedback(null);
              setPick(null);
            }
          }}
        >
          Continuar
        </button>
      </Panel>
    );
  }

  async function submit(choice: number) {
    setPick(choice);
    const result = await answer.run(item.id, choice);
    if (result) setFeedback(result);
  }

  async function next() {
    setFeedback(null);
    setPick(null);
    const refreshed = await reload.run();
    if (refreshed) setCurrent(refreshed);
  }

  const answered = current.answered_count + (feedback ? 1 : 0);

  return (
    <div style={SCREEN_IN}>
      <h1 style={{ fontSize: 24, margin: "0 0 5.6px" }}>Teste de nivelamento</h1>
      <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 16.8px" }}>
        Pergunta {answered + (feedback ? 0 : 1)} de {current.item_count} · a dificuldade se ajusta
        às suas respostas
      </p>

      <Panel pad={22.4}>
        {item.context ? (
          <div style={{ fontSize: 11.5, color: TEXT.muted, marginBottom: 8.4 }}>{item.context}</div>
        ) : null}
        <div style={{ fontSize: 11, color: ACC, marginBottom: 8.4 }}>
          {item.skill} · {item.cefr_band}
        </div>
        <h2 style={{ fontSize: 17, lineHeight: 1.4, marginBottom: 16.8, fontWeight: 500 }}>
          {item.prompt}
        </h2>

        <ChoiceList
          label="Respostas possíveis"
          options={item.options}
          pick={pick}
          answer={feedback ? feedback.correct_index : undefined}
          onPick={(choice) => void submit(choice)}
        />

        {answer.error ? <ErrorState message={answer.error} /> : null}

        {feedback ? (
          <div
            style={{
              marginTop: 16.8,
              padding: 14,
              borderRadius: 8,
              background: "#1b1d2b",
              borderLeft: `2px solid ${feedback.is_correct ? C.verde : ACC}`,
            }}
          >
            <div style={{ fontSize: 13.5, color: "rgba(233,233,237,.85)", lineHeight: 1.5 }}>
              {feedback.explanation}
            </div>
            <button
              type="button"
              className="btn btn-primary"
              style={{ marginTop: 11.2 }}
              onClick={next}
              disabled={reload.pending}
            >
              {reload.pending ? "Carregando…" : "Próxima"}
            </button>
          </div>
        ) : null}
      </Panel>
    </div>
  );
}

function Result({ result, onDone }: { result: EnglishAnswerResult; onDone: () => void }) {
  return (
    <div style={SCREEN_IN}>
      <Panel pad={22.4}>
        <div style={{ fontSize: 34, color: ACC4, lineHeight: 1 }}>
          {result.result?.cefr_level ?? "—"}
        </div>
        <p
          style={{
            fontSize: 14,
            color: "rgba(233,233,237,.75)",
            margin: "8.4px 0 16.8px",
            maxWidth: "50ch",
          }}
        >
          Este é o seu nível medido. Ele passa a valer para o plano diário e para o prazo da meta.
        </p>
        <button type="button" className="btn btn-primary" onClick={onDone}>
          Ver meu nível
        </button>
      </Panel>
    </div>
  );
}
