/**
 * A atividade prática do módulo — uma fila, não uma tarefa só.
 *
 * Escrever a solução do zero é o ponto: o modo "sem IA" existe porque a
 * pessoa que pediu este produto queria parar de depender de assistente para
 * codar. O que fica registrado é o texto dela, e a correção compara — não
 * completa.
 *
 * ## Sempre há algo para fazer
 *
 * Antes havia UMA atividade por módulo, tirada do objetivo: respondida, a aba
 * não tinha mais nada. Agora cada módulo tem uma fila (routers/atividades.py):
 * ao abrir, vem a atividade aberta — ou uma nova é gerada; respondeu e corrigiu,
 * "Próxima atividade" gera outra, diferente das anteriores e puxando o que a
 * correção apontou. As feitas ficam listadas com a nota.
 *
 * Se o servidor ainda não tiver a fila (versão antiga no ar), a tela volta ao
 * modo de antes, com o objetivo do módulo como tarefa.
 *
 * ## O rascunho
 *
 * Mora no SERVIDOR (`PUT /roadmap/nodes/{id}/draft`): preso a um navegador, a
 * solução escrita do zero se perdia ao trocar de máquina. Grava sozinho, com
 * uma pausa depois da última tecla; ao seguir para a próxima atividade, começa
 * vazio.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { explanations as explanationsApi, roadmap as roadmapApi } from "@/api/endpoints";
import type { AtividadePratica, ExplanationResult, FilaDeAtividades } from "@/api/types";
import type { RoadmapNode } from "@/api/types";
import { ACC3, ACC4, C, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { Kicker, Panel } from "@/components/ui/primitives";
import { EditorDeCodigo } from "@/components/ui/EditorDeCodigo";
import { ProgressoDaTarefa } from "@/components/ui/ProgressoDaTarefa";

/** Quanto tempo sem digitar antes de gravar. Curto o bastante para não perder
 * trabalho, longo o bastante para não mandar uma requisição por tecla. */
const PAUSA_MS = 900;

type Estado = "carregando" | "ocioso" | "gravando" | "salvo" | "erro";

const TIPO: Record<string, string> = {
  codigo: "Código",
  comandos: "Comandos",
  explicacao: "Explicação",
  configuracao: "Configuração",
  pratica: "Prática",
};

const ETAPAS_GERAR = ["Relendo o que você já fez", "Escolhendo o próximo desafio", "Escrevendo o enunciado"] as const;
const ETAPAS_CORRIGIR = ["Lendo sua resposta", "Comparando com o que foi pedido", "Escrevendo a correção"] as const;

function mensagem(erro: unknown, padrao: string): string {
  return erro instanceof Error ? erro.message : padrao;
}

export function ActivityPanel({ node }: { node: RoadmapNode }) {
  const [answer, setAnswer] = useState("");
  const [estado, setEstado] = useState<Estado>("carregando");
  const [enviando, setEnviando] = useState(false);
  const [correcao, setCorrecao] = useState<ExplanationResult | null>(null);
  const [erroCorrecao, setErroCorrecao] = useState<string | null>(null);
  // O que o servidor já tem. Sem isto, a gravação automática dispararia uma
  // vez logo após a carga, gravando exatamente o que acabou de ser lido.
  const gravado = useRef<string | null>(null);

  const [fila, setFila] = useState<FilaDeAtividades | null>(null);
  const [atual, setAtual] = useState<AtividadePratica | null>(null);
  const [gerando, setGerando] = useState(false);
  const [erroFila, setErroFila] = useState<string | null>(null);
  // Servidor sem a fila: a tarefa volta a ser o objetivo do módulo.
  const [semFila, setSemFila] = useState(false);

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

  const gerarProxima = useCallback(async () => {
    setGerando(true);
    setErroFila(null);
    try {
      setAtual(await roadmapApi.proximaAtividade(node.id));
    } catch (caught) {
      setErroFila(mensagem(caught, "Não consegui gerar a próxima atividade."));
    } finally {
      setGerando(false);
    }
  }, [node.id]);

  // Ao abrir o módulo: a atividade aberta, ou uma nova. Sempre há algo.
  useEffect(() => {
    let vivo = true;
    setFila(null);
    setAtual(null);
    setCorrecao(null);
    setSemFila(false);
    void roadmapApi
      .atividades(node.id)
      .then((dados) => {
        if (!vivo) return;
        setFila(dados);
        if (dados.atual) setAtual(dados.atual);
        else void gerarProxima();
      })
      .catch(() => {
        if (vivo) setSemFila(true);
      });
    return () => {
      vivo = false;
    };
  }, [node.id, gerarProxima]);

  const objective = node.objectives[0];
  const respondida = Boolean(correcao && !correcao.fora_do_tema);

  async function corrigir() {
    setEnviando(true);
    setErroCorrecao(null);
    setCorrecao(null);
    try {
      // O conceito sai do título do módulo: é o que a pessoa está estudando, e
      // pedir para ela digitá-lo de novo seria burocracia antes do exercício.
      // `atividade` + `exercise_id`: corrigida pelo enunciado DESTA atividade,
      // que o servidor lê do banco, lendo os comentários como a explicação.
      const resultado = await explanationsApi.submit({
        concept: node.title,
        content: answer.trim(),
        node_id: node.id,
        modo: "atividade",
        exercise_id: semFila ? undefined : atual?.id,
      });
      setCorrecao(resultado);
      if (!resultado.fora_do_tema && fila && atual) {
        const feita = { ...atual, nota: resultado.score, respondida_em: new Date().toISOString() };
        setFila({ ...fila, atual: null, feitas: [feita, ...fila.feitas].slice(0, 10), total_feitas: fila.total_feitas + 1 });
      }
    } catch (caught) {
      setErroCorrecao(mensagem(caught, "Não consegui corrigir agora."));
    } finally {
      setEnviando(false);
    }
  }

  /** Depois da correção: campo vazio, rascunho vazio, e a próxima atividade. */
  async function seguir() {
    setCorrecao(null);
    setErroCorrecao(null);
    setAtual(null);
    gravado.current = "";
    setAnswer("");
    void roadmapApi.saveDraft(node.id, "").catch(() => undefined);
    await gerarProxima();
  }

  const podeEnviar = !enviando && !respondida && answer.trim().length >= 40 && (semFila || Boolean(atual));

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
        {fila && fila.total_feitas > 0 ? (
          <span style={{ fontSize: 11.5, color: TEXT.faint, marginLeft: "auto" }}>
            {fila.total_feitas} {fila.total_feitas === 1 ? "feita" : "feitas"} neste módulo
          </span>
        ) : null}
      </div>

      <h3 style={{ fontSize: 18, marginBottom: 8.4, fontWeight: 500 }}>{node.title}</h3>

      {semFila ? (
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
      ) : null}

      {!semFila && gerando ? (
        <ProgressoDaTarefa
          ativo={gerando}
          chave="atividade-gerar"
          etapas={ETAPAS_GERAR}
          duracaoMs={12_000}
          style={{ margin: "11.2px 0" }}
        />
      ) : null}

      {!semFila && !gerando && erroFila && !atual ? (
        <div role="alert" style={{ margin: "11.2px 0", fontSize: 12.5, color: C.ambar, display: "flex", gap: 8.4, alignItems: "center", flexWrap: "wrap" }}>
          {erroFila}
          <button type="button" className="btn btn-secondary" style={{ fontSize: 12.5 }} onClick={() => void gerarProxima()}>
            <Icon name="refresh" size={14} />
            Tentar de novo
          </button>
        </div>
      ) : null}

      {!semFila && atual ? (
        <section
          aria-label="Atividade atual"
          style={{
            margin: "11.2px 0",
            padding: "12.6px 14px",
            borderRadius: 9,
            background: tint(ACC4, 7),
            boxShadow: `inset 0 0 0 1px ${tint(ACC4, 28)}`,
          }}
        >
          <div style={{ fontSize: 11.5, color: ACC4, marginBottom: 5 }}>
            {TIPO[atual.tipo] ?? "Prática"} · atividade {(fila?.total_feitas ?? 0) + (respondida ? 0 : 1)}
          </div>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: TEXT.full, whiteSpace: "pre-wrap" }}>
            {atual.enunciado}
          </p>
          {atual.dicas.length > 0 ? (
            <details style={{ marginTop: 8.4, fontSize: 12.5, color: TEXT.muted }}>
              <summary style={{ cursor: "pointer" }}>{atual.dicas.length === 1 ? "Ver dica" : "Ver dicas"}</summary>
              <ul style={{ margin: "5.6px 0 0", paddingLeft: 18 }}>
                {atual.dicas.map((dica) => (
                  <li key={dica}>{dica}</li>
                ))}
              </ul>
            </details>
          ) : null}
        </section>
      ) : null}

      <div className="field" style={{ marginTop: 14 }}>
        <label htmlFor="activity-answer">Sua resposta</label>
        {/* A fonte vem da classe e não daqui: inline ela venceria a regra de
            toque do app.css, e o Safari do iPhone daria zoom ao focar. */}
        <EditorDeCodigo
          id="activity-answer"
          value={answer}
          onChange={setAnswer}
          placeholder={"Escreva aqui, do zero.\n\ngit push  // comentários explicam o que o comando faz"}
          describedBy="activity-answer-dica"
        />
        <div id="activity-answer-dica" style={{ fontSize: 11.5, color: TEXT.faint, marginTop: 5 }}>
          Comentários (<code>//</code>, <code>#</code>, <code>--</code>, <code>/* */</code>) contam como a sua
          explicação. Só vale resposta para esta atividade.
        </div>
      </div>

      <div style={{ marginTop: 14, display: "flex", gap: 8.4, alignItems: "center", flexWrap: "wrap" }}>
        {respondida && !semFila ? (
          <button type="button" className="btn btn-primary" disabled={gerando} onClick={() => void seguir()}>
            Próxima atividade
            <Icon name="arrowRight" size={15} />
          </button>
        ) : (
          <button type="button" className="btn btn-primary" disabled={!podeEnviar} onClick={() => void corrigir()}>
            <Icon name="send" size={15} />
            {enviando ? "Corrigindo…" : "Enviar para correção"}
          </button>
        )}
        {!respondida && answer.trim().length < 40 ? (
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>
            Escreva ao menos algumas frases — uma linha não é explicação.
          </span>
        ) : null}
      </div>

      <ProgressoDaTarefa
        ativo={enviando}
        chave="atividade-corrigir"
        etapas={ETAPAS_CORRIGIR}
        duracaoMs={14_000}
        style={{ marginTop: 11.2 }}
      />

      {correcao ? <Correcao resultado={correcao} /> : null}
      {erroCorrecao ? (
        <div
          role="alert"
          style={{
            marginTop: 11.2,
            padding: "11.2px 14px",
            borderRadius: 8,
            background: "#0c0c10",
            borderLeft: `2px solid ${C.ambar}`,
            fontSize: 12.5,
            color: "rgba(233,233,237,.75)",
          }}
        >
          {erroCorrecao}
        </div>
      ) : null}

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

      {fila && fila.feitas.length > 0 ? (
        <details style={{ marginTop: 16.8, fontSize: 12.5, color: TEXT.muted }}>
          <summary style={{ cursor: "pointer" }}>Atividades feitas neste módulo ({fila.total_feitas})</summary>
          <ol style={{ listStyle: "none", margin: "8.4px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
            {fila.feitas.map((feita) => (
              <li key={feita.id} style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
                <span
                  style={{
                    flex: "none",
                    minWidth: 30,
                    fontVariantNumeric: "tabular-nums",
                    color: (feita.nota ?? 0) >= 70 ? C.verde : C.ambar,
                  }}
                >
                  {feita.nota ?? "—"}
                </span>
                <span style={{ color: TEXT.strong, overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                  {feita.enunciado}
                </span>
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </Panel>
  );
}

/**
 * A correção da explicação.
 *
 * Mostra a nota, o que se sustentou e as lacunas — nunca uma versão melhorada
 * do texto. Ler a explicação pronta faz a pessoa concordar e voltar a achar
 * que entendeu, que é exatamente a ilusão que este exercício quebra.
 *
 * A última linha é a que fecha o método: dizer que a lacuna VAI VOLTAR como
 * questão transforma um retorno em plano de estudo. Sem ela a correção seria
 * só uma nota, e nota não ensina nada.
 */
function Correcao({ resultado }: { resultado: ExplanationResult }) {
  if (resultado.fora_do_tema) {
    return (
      <div
        role="alert"
        style={{
          marginTop: 14,
          padding: 14,
          borderRadius: 8,
          background: "#0c0c10",
          borderLeft: `2px solid ${C.ambar}`,
          fontSize: 13,
          lineHeight: 1.55,
        }}
      >
        <strong style={{ fontWeight: 500, color: C.ambar }}>Não parece uma resposta para esta atividade.</strong>{" "}
        {resultado.feedback ?? "Escreva a solução do que o módulo pede."} Nada entrou na revisão nem contou como
        estudo.
      </div>
    );
  }
  const bom = resultado.score >= 70;
  return (
    <div
      style={{
        marginTop: 14,
        padding: 14,
        borderRadius: 8,
        background: "#0c0c10",
        borderLeft: `2px solid ${bom ? C.verde : C.ambar}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 8.4, marginBottom: 8.4 }}>
        <span style={{ fontSize: 24, color: bom ? C.verde : C.ambar, lineHeight: 1 }}>
          {resultado.score}
        </span>
        <span style={{ fontSize: 11.5, color: TEXT.faint }}>
          de 100 — quanto a explicação se sustenta sozinha
        </span>
      </div>

      {resultado.feedback ? (
        <p style={{ margin: "0 0 11.2px", fontSize: 13, lineHeight: 1.55 }}>{resultado.feedback}</p>
      ) : null}

      {(resultado.sustenta ?? []).length > 0 ? (
        <ul style={{ margin: "0 0 11.2px", paddingLeft: 18, fontSize: 12.5, color: C.verde }}>
          {(resultado.sustenta ?? []).map((item) => (
            <li key={item} style={{ marginBottom: 3 }}>
              {item}
            </li>
          ))}
        </ul>
      ) : null}

      {resultado.gaps.length > 0 ? (
        <>
          <div style={{ fontSize: 11.5, color: TEXT.faint, marginBottom: 5.6 }}>
            O que ficou pela metade
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.5 }}>
            {resultado.gaps.map((lacuna) => (
              <li key={lacuna.conceito} style={{ marginBottom: 5.6 }}>
                <strong style={{ fontWeight: 500 }}>{lacuna.conceito}</strong>
                {lacuna.por_que ? (
                  <span style={{ color: TEXT.muted }}> — {lacuna.por_que}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p style={{ margin: 0, fontSize: 12.5, color: C.verde }}>
          Nenhuma lacuna encontrada. Você conseguiu explicar sem apoio.
        </p>
      )}

      {resultado.viraram_revisao ? (
        <p style={{ margin: "11.2px 0 0", fontSize: 11.5, color: TEXT.muted }}>
          {resultado.viraram_revisao === 1
            ? "1 lacuna entrou na sua revisão"
            : `${resultado.viraram_revisao} lacunas entraram na sua revisão`}{" "}
          e volta como questão, com outras palavras, no próximo quiz desta trilha.
        </p>
      ) : null}
    </div>
  );
}
