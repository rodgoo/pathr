/**
 * A aba de quiz do módulo.
 *
 * O quiz é GERADO sob demanda, a partir das tags do módulo aberto — não há
 * banco de questões pronto. É o que permite a pergunta ser sobre o que a
 * pessoa está estudando agora, no nível em que ela está.
 *
 * O que já foi gerado e respondido MORA NO SERVIDOR, e é de lá que a aba parte:
 *
 *  - um quiz gerado e ainda não enviado volta com o que já foi respondido
 *    (`emAndamento`), então sair da aba, recarregar ou trocar de aparelho não
 *    faz ninguém recomeçar — a IA já escreveu aquelas perguntas;
 *  - as tentativas enviadas ficam no histórico do módulo, e cada uma reabre a
 *    correção completa (o que respondeu, o gabarito, a explicação).
 *
 * A cópia no navegador continua existindo, mas só como plano B: é o que
 * aparece quando o servidor não responde.
 */

import { quizzes as quizzesApi } from "@/api/endpoints";
import type { Quiz, QuizHistoricoItem, QuizRascunho, QuizResult, RoadmapNode } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useMutation, useQuery } from "@/hooks/useApi";
import { useT } from "@/lib/i18n";
import { C, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Panel } from "@/components/ui/primitives";
import { ProgressoDaTarefa } from "@/components/ui/ProgressoDaTarefa";
import { QuizRunner, Review } from "./QuizRunner";
import { useEffect, useState } from "react";

/**
 * O quiz gerado, guardado no aparelho — o PLANO B.
 *
 * As questões são escritas pela IA na hora. Com o servidor no ar, elas voltam de lá (`emAndamento`); esta cópia
 * é o que sobra quando a consulta falha, para uma queda de rede no meio do quiz não virar "começar do zero".
 * A chave é por módulo: cada módulo tem o seu.
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
  const t = useT();
  const { dispatch } = useAppState();
  const nodeId = node?.id;
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [progresso, setProgresso] = useState<QuizRascunho | null>(null);
  // Até o servidor responder não se sabe se há quiz aberto: mostrar "começar quiz" por um instante e trocar
  // por um quiz em andamento é pior que esperar meio segundo.
  const [consultando, setConsultando] = useState(Boolean(nodeId));
  const [reaberta, setReaberta] = useState<{ quiz: Quiz; result: QuizResult } | null>(null);

  const generate = useMutation(() =>
    quizzesApi.generate({ node_id: nodeId, question_count: 6, difficulty: "adaptativo" }),
  );
  const abrir = useMutation((attemptId: string) => quizzesApi.tentativa(attemptId));
  const historico = useQuery(() => quizzesApi.historico(nodeId as string), [nodeId], {
    enabled: Boolean(nodeId),
  });

  // Trocar de módulo com a aba de quiz aberta traz o quiz DAQUELE módulo — e é aqui, a cada troca e na
  // montagem, que o servidor é consultado.
  useEffect(() => {
    setReaberta(null);
    if (!nodeId) {
      setConsultando(false);
      return undefined;
    }
    let vivo = true;
    setConsultando(true);
    quizzesApi
      .emAndamento(nodeId)
      .then((resposta) => {
        if (!vivo) return;
        if (resposta.quiz) {
          setQuiz(resposta.quiz);
          setProgresso(resposta.rascunho);
          dispatch({ type: "openQuiz", quizId: resposta.quiz.id });
        } else {
          // O servidor é quem sabe: sem quiz aberto lá, a cópia daqui é de um quiz que já foi enviado.
          esquecerQuiz(nodeId);
          setQuiz(null);
          setProgresso(null);
        }
      })
      .catch(() => {
        // Sem rede (ou o servidor fora do ar): o que estiver guardado no aparelho é melhor que nada.
        if (!vivo) return;
        setQuiz(lerQuizAberto(nodeId));
        setProgresso(null);
      })
      .finally(() => {
        if (vivo) setConsultando(false);
      });
    return () => {
      vivo = false;
    };
  }, [nodeId, dispatch]);

  useEffect(() => {
    if (!nodeId || !quiz) return;
    try {
      window.localStorage.setItem(chaveDoQuiz(nodeId), JSON.stringify(quiz));
    } catch {
      // Armazenamento bloqueado: o quiz continua, so nao sobrevive ao F5 sem rede.
    }
  }, [nodeId, quiz]);

  async function start() {
    const created = await generate.run();
    if (created) {
      setQuiz(created);
      setProgresso(null);
      dispatch({ type: "openQuiz", quizId: created.id });
    }
  }

  async function reabrir(attemptId: string) {
    const encontrada = await abrir.run(attemptId);
    if (encontrada) setReaberta(encontrada);
  }

  if (!node) {
    return (
      <EmptyState
        title={t("modulo.quiz.nenhumModuloTitulo")}
        description={t("modulo.quiz.nenhumModuloDescricao")}
      />
    );
  }

  if (consultando) return <Loading label={t("modulo.quiz.retomando")} />;

  if (reaberta) {
    return (
      <div>
        <button
          type="button"
          className="btn btn-secondary"
          style={{ marginBottom: 11.2 }}
          onClick={() => setReaberta(null)}
        >
          <Icon name="arrowLeft" size={15} />
          {t("modulo.quiz.voltarAoHistorico")}
        </button>
        <Review quiz={reaberta.quiz} result={reaberta.result} />
      </div>
    );
  }

  if (quiz) {
    const retomou = progresso !== null && Object.keys(progresso.answers).length > 0;
    return (
      <div>
        {retomou ? (
          <p style={{ fontSize: 12, color: TEXT.faint, margin: "0 0 8.4px" }}>{t("modulo.quiz.continuando")}</p>
        ) : null}
        <QuizRunner
          key={quiz.id}
          quiz={quiz}
          progressoInicial={progresso ?? undefined}
          onSubmitted={() => {
            esquecerQuiz(nodeId);
            historico.reload();
          }}
          onFinished={() => {
            esquecerQuiz(nodeId);
            setQuiz(null);
            setProgresso(null);
            dispatch({ type: "openQuiz", quizId: null });
            historico.reload();
          }}
        />
      </div>
    );
  }

  return (
    <div>
      <Panel pad={22.4}>
        <h3 style={{ fontSize: 18, margin: "0 0 8.4px", fontWeight: 500 }}>
          {t("modulo.quiz.quizDe", { titulo: node.title })}
        </h3>
        <p style={{ fontSize: 13.5, color: "rgba(233,233,237,.7)", maxWidth: "60ch" }}>
          {t("modulo.quiz.descricao")}
        </p>

        {generate.error ? <ErrorState message={generate.error} onRetry={start} /> : null}

        <div style={{ display: "flex", gap: 8.4, alignItems: "center", marginTop: 14, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-primary" onClick={start} disabled={generate.pending}>
            <Icon name="playSolid" size={15} />
            {generate.pending ? t("modulo.quiz.escrevendoQuestoes") : t("modulo.quiz.comecarQuiz")}
          </button>
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>
            {generate.pending ? t("modulo.quiz.iaLevaSegundos") : t("modulo.quiz.levaCerca")}
          </span>
        </div>
        <ProgressoDaTarefa
          ativo={generate.pending}
          chave="quiz-gerar"
          etapas={[
            t("modulo.quiz.gerarEtapa1"),
            t("modulo.quiz.gerarEtapa2"),
            t("modulo.quiz.gerarEtapa3"),
          ]}
          duracaoMs={20_000}
          style={{ marginTop: 14 }}
        />
      </Panel>

      <Historico
        itens={historico.data ?? []}
        abrindo={abrir.pending}
        erro={abrir.error}
        onAbrir={reabrir}
      />
    </div>
  );
}

/**
 * As tentativas já enviadas neste módulo.
 *
 * Sem isto a correção só existia na tela do momento do envio: sair da aba a perdia, e a nota — que é a única
 * evidência de domínio que o app coleta — ficava sem lugar onde ser conferida depois.
 */
function Historico({
  itens,
  abrindo,
  erro,
  onAbrir,
}: {
  itens: QuizHistoricoItem[];
  abrindo: boolean;
  erro: string | null;
  onAbrir: (attemptId: string) => void;
}) {
  const t = useT();
  return (
    <Panel pad={22.4} style={{ marginTop: 11.2 }}>
      <h4 style={{ fontSize: 14, margin: "0 0 11.2px", fontWeight: 500 }}>{t("modulo.quiz.historicoTitulo")}</h4>
      {erro ? <ErrorState message={erro} /> : null}
      {itens.length === 0 ? (
        <p style={{ fontSize: 12.5, color: TEXT.faint, margin: 0 }}>{t("modulo.quiz.historicoVazio")}</p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8.4 }}>
          {itens.map((item) => {
            const nota = Math.round(item.score ?? 0);
            return (
              <li
                key={item.attempt_id}
                style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 11.2, fontSize: 13 }}
              >
                <span style={{ minWidth: 42, fontWeight: 500, color: nota >= 70 ? C.verde : C.ambar }}>{nota}%</span>
                <span style={{ color: TEXT.muted }}>
                  {t("modulo.quiz.certas", { n: item.correct_count ?? 0, total: item.total ?? 0 })}
                </span>
                <span style={{ color: TEXT.faint, fontSize: 12 }}>{quandoFoi(item.finished_at)}</span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ marginLeft: "auto" }}
                  disabled={abrindo}
                  onClick={() => onAbrir(item.attempt_id)}
                >
                  {abrindo ? t("modulo.quiz.abrindoCorrecao") : t("modulo.quiz.verCorrecao")}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}

function quandoFoi(iso: string | null): string {
  if (!iso) return "";
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return "";
  return data.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
}
