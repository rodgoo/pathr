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
import { explanations as explanationsApi, roadmap as roadmapApi } from "@/api/endpoints";
import type { ExplanationResult } from "@/api/types";
import type { RoadmapNode } from "@/api/types";
import { ACC3, C, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { Kicker, Panel } from "@/components/ui/primitives";

/** Quanto tempo sem digitar antes de gravar. Curto o bastante para não perder
 * trabalho, longo o bastante para não mandar uma requisição por tecla. */
const PAUSA_MS = 900;

type Estado = "carregando" | "ocioso" | "gravando" | "salvo" | "erro";

export function ActivityPanel({ node }: { node: RoadmapNode }) {
  const [answer, setAnswer] = useState("");
  const [estado, setEstado] = useState<Estado>("carregando");
  const [enviando, setEnviando] = useState(false);
  const [correcao, setCorrecao] = useState<ExplanationResult | null>(null);
  const [erroCorrecao, setErroCorrecao] = useState<string | null>(null);
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

  async function corrigir() {
    setEnviando(true);
    setErroCorrecao(null);
    setCorrecao(null);
    try {
      // O conceito sai do título do módulo: é o que a pessoa está estudando, e
      // pedir para ela digitá-lo de novo seria burocracia antes do exercício.
      const resultado = await explanationsApi.submit({
        concept: node.title,
        content: answer.trim(),
        node_id: node.id,
      });
      setCorrecao(resultado);
    } catch (caught) {
      setErroCorrecao(
        caught instanceof Error ? caught.message : "Não consegui corrigir agora.",
      );
    } finally {
      setEnviando(false);
    }
  }

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
          className="input campo-codigo"
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          placeholder="Escreva aqui, do zero."
          // A fonte vem da classe e não daqui: inline ela venceria a regra de
          // toque do app.css, e o Safari do iPhone daria zoom ao focar.
          style={{ minHeight: 200 }}
        />
      </div>

      <div style={{ marginTop: 14, display: "flex", gap: 8.4, alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={enviando || answer.trim().length < 40}
          onClick={() => void corrigir()}
        >
          <Icon name="send" size={15} />
          {enviando ? "Lendo sua explicação…" : "Enviar para correção"}
        </button>
        {answer.trim().length < 40 ? (
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>
            Escreva ao menos algumas frases — uma linha não é explicação.
          </span>
        ) : null}
      </div>

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
