/**
 * Um texto em que cada palavra pode ser consultada.
 *
 * No nivelamento, travar numa palavra faz o item medir vocabulário quando ele
 * queria medir compreensão — e a saída honesta de quem não sabe é chutar, o
 * que estraga a medição dos dois jeitos. Poder tocar na palavra e ver o que
 * ela quer dizer troca o chute por uma leitura.
 *
 * Isso não facilita o teste: o que se mede aqui é entender o enunciado, e a
 * tradução de UMA palavra não entrega a resposta certa entre quatro
 * alternativas. O que ela evita é a pergunta virar adivinhação.
 *
 * **E consultar é evidência.** É a única vez em que a pessoa diz, sem ser
 * perguntada, "esta eu não tenho". O servidor põe o termo no baralho vencendo
 * hoje e devolve o cartão (ver `POST /languages/lookup`), então a consulta
 * alimenta o que o app sabe sobre ela — não é só um dicionário embutido.
 *
 * O balão fica ABAIXO da palavra, posicionado sobre o texto em vez de
 * empurrá-lo: abrir uma consulta não pode fazer a frase que se estava lendo
 * pular de lugar.
 */

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { english as englishApi } from "@/api/endpoints";
import type { WordMeaning } from "@/api/types";
import { useMutation } from "@/hooks/useApi";
import { useT } from "@/lib/i18n";
import { ACC, ACC3, HAIRLINE, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";

/** Palavras e o que as separa, preservando os dois na mesma lista. */
const PEDACOS = /([^\W\d_][\w'’-]*)/u;

/**
 * O que já se consultou nesta aba, por idioma, palavra e frase. Reabrir a
 * mesma palavra no mesmo texto não vai ao servidor: a resposta não muda, e a
 * espera de novo era o que fazia a consulta parecer lenta. A frase entra na
 * chave porque o significado depende dela ("book" de reservar ≠ de livro).
 */
const consultadas = new Map<string, WordMeaning>();

/** O trecho destacado pelo servidor: `[[clean up]]`. Ver `_TRECHO_MARCADO`. */
const MARCA = /\[\[([^[\]]+)\]\]/g;
const TRECHOS = /(\[\[[^[\]]+\]\])/;
const MARCA_INTEIRA = /^\[\[([^[\]]+)\]\]$/;

export function limparConsultasEmMemoria() {
  consultadas.clear();
}

interface Alvo {
  palavra: string;
  /** Posição da palavra dentro do bloco, para ancorar o balão embaixo dela. */
  topo: number;
  esquerda: number;
  altura: number;
}

export function TextoConsultavel({
  texto,
  idioma = "en",
  style,
}: {
  texto: string;
  idioma?: string;
  /** O estilo do bloco de texto — quem usa decide se é contexto ou enunciado. */
  style?: CSSProperties;
}) {
  const t = useT();
  const bloco = useRef<HTMLSpanElement | null>(null);
  const [alvo, setAlvo] = useState<Alvo | null>(null);
  const [significado, setSignificado] = useState<WordMeaning | null>(null);
  // O servidor recebe a frase sem a marca de destaque: "[[clean up]]" é
  // desenho de tela, não parte do que a pessoa leu.
  const semMarcas = texto.replace(MARCA, "$1");
  const consulta = useMutation((palavra: string) => englishApi.lookup(palavra, idioma, semMarcas));

  function fechar() {
    setAlvo(null);
    setSignificado(null);
    consulta.clearError();
  }

  // Sair pelo teclado. Um balão que só fecha com o mouse deixa preso quem
  // navega pelo teclado — e quem abriu sem querer no celular.
  useEffect(() => {
    if (!alvo) return undefined;
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") fechar();
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [alvo]);

  async function consultar(palavra: string, elemento: HTMLElement) {
    if (alvo?.palavra === palavra) {
      fechar();
      return;
    }
    setSignificado(null);
    consulta.clearError();
    setAlvo({
      palavra,
      topo: elemento.offsetTop,
      esquerda: elemento.offsetLeft,
      altura: elemento.offsetHeight,
    });
    const chave = `${idioma}|${palavra.toLowerCase()}|${texto}`;
    const guardado = consultadas.get(chave);
    if (guardado) {
      setSignificado(guardado);
      return;
    }
    const achado = await consulta.run(palavra);
    if (achado) {
      consultadas.set(chave, achado);
      setSignificado(achado);
    }
  }

  return (
    // `span` e não `div`: este bloco é usado dentro de um `<h2>`, e só
    // conteúdo de frase pode morar ali. `display: block` devolve o
    // comportamento de bloco sem quebrar o encaixe.
    <span ref={bloco} style={{ display: "block", position: "relative", ...style }}>
      {texto.split(TRECHOS).map((trecho, indiceDoTrecho) => {
        const destacado = MARCA_INTEIRA.exec(trecho);
        const conteudo = destacado ? destacado[1] : trecho;
        const palavras = conteudo.split(PEDACOS).map((pedaco, posicao) =>
          PEDACOS.test(pedaco) && pedaco.length > 1 ? (
            <button
              // A posição entra na chave porque a mesma palavra repete no texto,
              // e duas ocorrências são dois lugares diferentes para ancorar.
              key={`${pedaco}-${indiceDoTrecho}-${posicao}`}
              type="button"
              className="palavra"
              aria-label={t("idiomas.texto.consultar", { palavra: pedaco })}
              aria-expanded={alvo?.palavra === pedaco}
              onClick={(evento) => void consultar(pedaco, evento.currentTarget)}
            >
              {pedaco}
            </button>
          ) : (
            <span key={`t-${indiceDoTrecho}-${posicao}`}>{pedaco}</span>
          ),
        );
        // O trecho que a pergunta aponta ("the underlined part") continua
        // sublinhado por cima das palavras consultáveis — o pontilhado de cada
        // palavra não pode apagar o destaque de que a resposta depende.
        return destacado ? (
          <mark key={`d-${indiceDoTrecho}`} className="destaque">
            {palavras}
          </mark>
        ) : (
          <span key={`s-${indiceDoTrecho}`}>{palavras}</span>
        );
      })}

      {alvo ? (
        <Balao
          alvo={alvo}
          largura={bloco.current?.clientWidth ?? 0}
          carregando={consulta.pending}
          erro={consulta.error}
          significado={significado}
          onFechar={fechar}
        />
      ) : null}
    </span>
  );
}

/** Largura do balão. Fixa para o cálculo de encaixe saber com o que conta. */
const LARGURA = 260;

function Balao({
  alvo,
  largura,
  carregando,
  erro,
  significado,
  onFechar,
}: {
  alvo: Alvo;
  largura: number;
  carregando: boolean;
  erro: string | null;
  significado: WordMeaning | null;
  onFechar: () => void;
}) {
  const t = useT();
  // Encostado à esquerda da palavra, mas sem sair do bloco: numa palavra no
  // fim da linha o balão escaparia pela direita e metade dele ficaria fora da
  // tela do celular.
  const esquerda = Math.max(0, Math.min(alvo.esquerda, Math.max(0, largura - LARGURA)));

  return (
    <span
      role="dialog"
      aria-label={t("idiomas.texto.oQueQuerDizer", { palavra: alvo.palavra })}
      style={{
        // `span` pelo mesmo motivo do bloco acima: isto pode estar dentro de
        // um `<h2>`, onde só cabe conteúdo de frase.
        display: "block",
        position: "absolute",
        top: alvo.topo + alvo.altura + 4,
        left: esquerda,
        width: Math.min(LARGURA, largura || LARGURA),
        zIndex: 2,
        padding: "11.2px 14px",
        borderRadius: 8,
        background: "#0c0c10",
        boxShadow: `0 8px 24px rgba(0,0,0,.45), 0 0 0 1px ${HAIRLINE}`,
        fontSize: 12.5,
        lineHeight: 1.5,
        color: TEXT.muted,
        whiteSpace: "normal",
        textAlign: "left",
      }}
    >
      <span style={{ display: "flex", alignItems: "baseline", gap: 8.4 }}>
        <strong style={{ color: TEXT.strong, fontWeight: 500 }}>{alvo.palavra}</strong>
        {significado?.phonetic ? (
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>{significado.phonetic}</span>
        ) : null}
        <button
          type="button"
          className="btn btn-ghost"
          aria-label={t("idiomas.texto.fechar")}
          title={t("idiomas.texto.fechar")}
          style={{ marginLeft: "auto", padding: 4, minHeight: 0, color: TEXT.faint }}
          onClick={onFechar}
        >
          <Icon name="x" size={14} />
        </button>
      </span>

      {carregando ? (
        <span
          role="status"
          style={{ display: "block", margin: "5.6px 0 0", color: TEXT.faint }}
        >
          {t("idiomas.texto.consultando")}
        </span>
      ) : null}

      {erro ? (
        <span style={{ display: "block", margin: "5.6px 0 0", color: "#cfa25e" }}>{erro}</span>
      ) : null}

      {significado ? (
        <>
          {significado.translation ? (
            <span style={{ display: "block", marginTop: 5.6, color: ACC3, fontSize: 14 }}>
              {significado.translation}
            </span>
          ) : null}
          {significado.definition ? (
            <span style={{ display: "block", margin: "5.6px 0 0" }}>{significado.definition}</span>
          ) : null}
          {significado.synonyms.length > 0 ? (
            <span style={{ display: "block", margin: "5.6px 0 0", color: TEXT.faint }}>
              {t("idiomas.texto.sinonimos", { lista: significado.synonyms.join(", ") })}
            </span>
          ) : null}
          {significado.example ? (
            <span
              style={{ display: "block", margin: "5.6px 0 0", color: TEXT.faint, fontStyle: "italic" }}
            >
              {significado.example}
            </span>
          ) : null}
          {/* Dizer o que a consulta PROVOCOU. Sem esta linha, olhar uma
              palavra parece um dicionário à parte; com ela, fica claro que o
              app anotou a lacuna e vai trazê-la de volta. */}
          {significado.card ? (
            <span style={{ display: "block", margin: "8.4px 0 0", fontSize: 11.5, color: ACC }}>
              {t("idiomas.texto.entrouRevisao")}
            </span>
          ) : null}
        </>
      ) : null}
    </span>
  );
}
