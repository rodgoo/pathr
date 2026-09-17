/**
 * O treino diário de idioma: um exercício por vez, corrigido na hora.
 *
 * ## Por que a correção é imediata aqui e não no fim
 *
 * O quiz técnico corrige no fim. Em idioma, não: o erro não corrigido na hora
 * vira hábito, e o exercício seguinte já seria feito com a forma errada na
 * cabeça. Por isso cada resposta mostra na hora o certo, o porquê — em
 * português — e o que aconteceu com o ponto de melhora.
 *
 * ## A reciclagem é dita, não escondida
 *
 * Quando um erro vira ponto de melhora, a tela diz que ele volta com outras
 * palavras. Quando uma revisão é acertada, diz que ela volta mais tarde e num
 * formato mais exigente. Sem a frase, a pessoa reencontraria a mesma ideia dias
 * depois sem entender por quê, e acharia que o app repete pergunta por preguiça.
 *
 * ## Persistência
 *
 * O treino mora no servidor. Sair no meio e voltar — nesta tela, em outra aba
 * ou em outro aparelho — retoma no próximo exercício pendente.
 */

import { useState } from "react";
import { english as englishApi } from "@/api/endpoints";
import type {
  PracticeAnswer,
  PracticeAnswerResult,
  PracticeItem,
  PracticeSession,
  PracticeSummary,
} from "@/api/types";
import { useT } from "@/lib/i18n";
import { ACC, ACC4, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { IconButton } from "@/components/ui/IconButton";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { nomeDaHabilidade } from "@/components/english/QuadroDeHabilidades";
import { Exercicio, nomeDoFormato } from "./Exercicios";

const ORIGEM: Record<PracticeItem["origin"], string> = {
  revisao: "idiomas.treino.origem.revisao",
  reforco: "idiomas.treino.origem.reforco",
  novo: "idiomas.treino.origem.novo",
};

const PONTO: Record<NonNullable<PracticeAnswerResult["improvement"]>, string> = {
  novo_ponto: "idiomas.treino.ponto.novoPonto",
  subiu: "idiomas.treino.ponto.subiu",
  volta_hoje: "idiomas.treino.ponto.voltaHoje",
};

export function TreinoDoDia({
  inicial,
  idioma,
  onSair,
}: {
  inicial: PracticeSession;
  idioma: string;
  onSair: () => void;
}) {
  const t = useT();
  const [sessao, setSessao] = useState(inicial);
  const [respondendo, setRespondendo] = useState<PracticeItem | null>(null);
  const [resultado, setResultado] = useState<PracticeAnswerResult | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [preparando, setPreparando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Enquanto a correção está na tela, o exercício respondido fica: a sessão
  // nova (que já não o traz entre os pendentes) só entra ao continuar.
  const atual = respondendo ?? sessao.items[0] ?? null;

  async function responder(resposta: PracticeAnswer) {
    if (!atual || enviando || resultado) return;
    setEnviando(true);
    setErro(null);
    setRespondendo(atual);
    try {
      setResultado(await englishApi.answerPractice(sessao.id, atual.id, resposta));
    } catch (caught) {
      setRespondendo(null);
      setErro(caught instanceof Error ? caught.message : t("idiomas.treino.erroCorrigir"));
    } finally {
      setEnviando(false);
    }
  }

  async function buscarProximos(id: string) {
    setPreparando(true);
    setErro(null);
    try {
      setSessao(await englishApi.practice(id));
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : t("idiomas.treino.erroPreparar"));
    } finally {
      setPreparando(false);
    }
  }

  async function continuar() {
    if (!resultado) return;
    const proxima = resultado.session;
    setResultado(null);
    setRespondendo(null);
    setSessao(proxima);
    // Nenhum pronto, mas ainda há o que preparar: o segundo plano pode não ter
    // terminado. Pedir o treino de novo gera ali mesmo.
    if (proxima.items.length === 0 && proxima.status !== "done" && proxima.generating) {
      await buscarProximos(proxima.id);
    }
  }

  if (sessao.status === "done" && sessao.summary && !resultado) {
    return <Resumo resumo={sessao.summary} onSair={onSair} />;
  }

  const feito = sessao.total ? Math.round((100 * sessao.answered) / sessao.total) : 0;

  return (
    <div style={{ ...SCREEN_IN, maxWidth: 680 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11.2, marginBottom: 11.2 }}>
        <IconButton icon="arrowLeft" label={t("idiomas.treino.sairDoTreino")} onClick={onSair} />
        <div
          role="progressbar"
          aria-label={t("idiomas.treino.progressoAria")}
          aria-valuemin={0}
          aria-valuemax={sessao.total}
          aria-valuenow={sessao.answered}
          style={{
            flex: 1,
            height: 6,
            borderRadius: 3,
            background: "rgba(233,233,237,.12)",
            overflow: "hidden",
          }}
        >
          <div style={{ width: `${feito}%`, height: "100%", background: ACC4, transition: "width .3s" }} />
        </div>
        <span style={{ fontSize: 12, color: TEXT.faint, whiteSpace: "nowrap" }}>
          {t("idiomas.treino.deTotal", { feito: sessao.answered, total: sessao.total })}
        </span>
      </div>

      {erro ? (
        <Panel>
          <p style={{ fontSize: 13, color: C.ambar, margin: "0 0 8px" }}>{erro}</p>
          <button type="button" className="btn btn-secondary" onClick={() => buscarProximos(sessao.id)}>
            <Icon name="refresh" size={15} />
            {t("idiomas.treino.tentarDeNovo")}
          </button>
        </Panel>
      ) : null}

      {!atual ? (
        <Panel>
          <p style={{ fontSize: 13.5, color: TEXT.muted, margin: 0 }}>
            {preparando ? t("idiomas.treino.preparandoProximos") : t("idiomas.treino.nenhumPronto")}
          </p>
          {!preparando && !erro && sessao.status !== "done" ? (
            <button
              type="button"
              className="btn btn-secondary"
              style={{ marginTop: 10 }}
              onClick={() => buscarProximos(sessao.id)}
            >
              <Icon name="refresh" size={15} />
              {t("idiomas.treino.carregarProximos")}
            </button>
          ) : null}
        </Panel>
      ) : (
        <Panel pad={22.4}>
          <div
            style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12, alignItems: "center" }}
          >
            <span className="tag tag-outline">{nomeDoFormato(atual.type, t)}</span>
            <span style={{ fontSize: 11.5, color: TEXT.faint }}>
              {nomeDaHabilidade(atual.skill, t)}
              {atual.topic ? ` · ${atual.topic}` : ""}
              {atual.band ? ` · ${atual.band}` : ""}
            </span>
            <span
              style={{
                marginLeft: "auto",
                fontSize: 11,
                color:
                  atual.origin === "revisao" ? C.ambar : atual.origin === "reforco" ? ACC4 : TEXT.faint,
              }}
            >
              {t(ORIGEM[atual.origin])}
            </span>
          </div>

          {atual.payload.enunciado ? (
            <h2 style={{ fontSize: 17, fontWeight: 500, lineHeight: 1.35, margin: "0 0 14px" }}>
              {atual.payload.enunciado}
            </h2>
          ) : null}

          <Exercicio
            item={atual}
            idioma={idioma}
            travado={enviando || resultado !== null}
            resultado={resultado}
            onResponder={responder}
          />

          {resultado ? <Correcao resultado={resultado} onContinuar={continuar} /> : null}
        </Panel>
      )}
    </div>
  );
}

function Correcao({
  resultado,
  onContinuar,
}: {
  resultado: PracticeAnswerResult;
  onContinuar: () => void;
}) {
  const t = useT();
  const tom = resultado.skipped ? TEXT.muted : resultado.is_correct ? C.verde : C.ambar;
  const titulo = resultado.skipped
    ? t("idiomas.treino.pulado")
    : resultado.is_correct
      ? t("idiomas.treino.certo")
      : t("idiomas.treino.aindaNao");

  return (
    <div role="status" style={{ marginTop: 18, paddingTop: 14, borderTop: `1px solid ${HAIRLINE}` }}>
      <div style={{ fontSize: 15, fontWeight: 600, color: tom, marginBottom: 6 }}>{titulo}</div>
      {resultado.explanation && !resultado.skipped ? (
        <p style={{ fontSize: 13.5, lineHeight: 1.6, color: "rgba(233,233,237,.85)", margin: "0 0 8px" }}>
          {resultado.explanation}
        </p>
      ) : null}
      {resultado.improvement ? (
        <p style={{ fontSize: 12.5, lineHeight: 1.5, color: ACC4, margin: "0 0 10px" }}>
          {t(PONTO[resultado.improvement])}
        </p>
      ) : null}
      {/* O foco vai para o botão: quem responde pelo teclado segue com Enter. */}
      <button type="button" className="btn btn-primary" autoFocus onClick={onContinuar}>
        <Icon name="arrowRight" size={15} />
        {t("idiomas.treino.continuar")}
      </button>
    </div>
  );
}

function Resumo({ resumo, onSair }: { resumo: PracticeSummary; onSair: () => void }) {
  const t = useT();
  const mudaramDeLetra = resumo.levels.filter((n) => n.before && n.before !== n.after);
  const avancaram = resumo.levels.filter(
    (n) => n.delta !== null && n.delta >= 0.05 && !(n.before && n.before !== n.after),
  );

  return (
    <div style={{ ...SCREEN_IN, maxWidth: 680 }}>
      <Panel pad={22.4}>
        <Kicker style={{ display: "block", marginBottom: 8 }}>{t("idiomas.treino.concluido")}</Kicker>
        <div style={{ fontSize: 42, lineHeight: 1, color: ACC4 }}>
          {resumo.correct}/{resumo.answered}
        </div>
        <p style={{ fontSize: 13.5, color: TEXT.muted, margin: "8px 0 0" }}>
          {resumo.reviewed > 0
            ? t("idiomas.treino.recuperou", { recuperados: resumo.recovered, total: resumo.reviewed })
            : t("idiomas.treino.nadaVencia")}
        </p>

        {mudaramDeLetra.length > 0 || avancaram.length > 0 ? (
          <div style={{ marginTop: 16 }}>
            <Kicker style={{ display: "block", marginBottom: 6 }}>{t("idiomas.treino.seuNivelHoje")}</Kicker>
            {mudaramDeLetra.map((nivel) => (
              <div key={nivel.skill} style={{ fontSize: 13.5, padding: "3px 0" }}>
                {nomeDaHabilidade(nivel.skill, t)}:{" "}
                <span style={{ color: TEXT.faint }}>{nivel.before}</span> →{" "}
                <span style={{ color: (nivel.delta ?? 0) >= 0 ? C.verde : C.ambar }}>{nivel.after}</span>
              </div>
            ))}
            {avancaram.map((nivel) => (
              <div key={nivel.skill} style={{ fontSize: 13, padding: "3px 0", color: TEXT.muted }}>
                {t("idiomas.treino.avancouDentro", { nome: nomeDaHabilidade(nivel.skill, t), nivel: nivel.after ?? "" })}
              </div>
            ))}
          </div>
        ) : null}

        {resumo.topics.length > 0 ? (
          <div style={{ marginTop: 16 }}>
            <Kicker style={{ display: "block", marginBottom: 6 }}>{t("idiomas.treino.porTopico")}</Kicker>
            {resumo.topics.map((topico) => {
              const cor =
                topico.correct === topico.answered ? C.verde : topico.correct === 0 ? C.ambar : ACC;
              return (
                <div
                  key={`${topico.skill}-${topico.topic}`}
                  style={{ display: "flex", gap: 8, fontSize: 13, padding: "3px 0" }}
                >
                  <span style={{ color: "rgba(233,233,237,.82)" }}>{topico.topic}</span>
                  <span style={{ color: TEXT.faint }}>
                    {nomeDaHabilidade(topico.skill, t)}
                  </span>
                  <span style={{ marginLeft: "auto", color: cor }}>
                    {t("idiomas.quadro.correctDe", { correct: topico.correct, total: topico.answered })}
                  </span>
                </div>
              );
            })}
          </div>
        ) : null}

        <button type="button" className="btn btn-primary" style={{ marginTop: 18 }} onClick={onSair}>
          <Icon name="arrowLeft" size={15} />
          {t("idiomas.treino.voltarAoIdioma")}
        </button>
      </Panel>
    </div>
  );
}

/** O cartão do treino na tela do idioma: começar, continuar ou "feito hoje". */
export function CartaoDoTreino({
  hoje,
  carregando,
  comecando,
  erro,
  onComecar,
}: {
  hoje: PracticeSession | null;
  carregando: boolean;
  comecando: boolean;
  erro: string | null;
  onComecar: () => void;
}) {
  const t = useT();
  const feito = hoje?.status === "done";
  const emAndamento = hoje !== null && !feito && hoje.answered > 0;

  return (
    <Panel>
      <Kicker style={{ display: "block", marginBottom: 6 }}>{t("idiomas.treino.treinoDeHoje")}</Kicker>
      {feito && hoje?.summary ? (
        <>
          <div style={{ fontSize: 14, color: C.verde }}>
            {t("idiomas.treino.feitoHoje", { correct: hoje.summary.correct, total: hoje.summary.answered })}
          </div>
          <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "6px 0 10px" }}>
            {t("idiomas.treino.proximoAmanha")}
          </p>
          <button type="button" className="btn btn-secondary btn-block" onClick={onComecar}>
            <Icon name="arrowRight" size={15} />
            {t("idiomas.treino.verResumo")}
          </button>
        </>
      ) : (
        <>
          <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 10px", lineHeight: 1.5 }}>
            {emAndamento && hoje
              ? t("idiomas.treino.emAndamentoDesc", { feito: hoje.answered, total: hoje.total })
              : t("idiomas.treino.novoDesc")}
          </p>
          <button
            type="button"
            className="btn btn-primary btn-block"
            disabled={carregando || comecando}
            onClick={onComecar}
          >
            {comecando
              ? t("idiomas.treino.preparandoExercicios")
              : emAndamento
                ? t("idiomas.treino.continuarTreino")
                : t("idiomas.treino.comecarTreino")}
          </button>
          {comecando ? (
            <p style={{ fontSize: 11.5, color: TEXT.faint, margin: "6px 0 0" }}>
              {t("idiomas.treino.primeirosSegundos")}
            </p>
          ) : null}
        </>
      )}
      {erro ? <p style={{ fontSize: 12, color: C.ambar, margin: "8px 0 0" }}>{erro}</p> : null}
    </Panel>
  );
}
