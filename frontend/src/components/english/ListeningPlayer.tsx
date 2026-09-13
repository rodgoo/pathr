/**
 * O áudio do item de listening, falado pelo próprio navegador.
 *
 * ## Por que a voz do navegador, e não um TTS de servidor
 *
 * Custo. `speechSynthesis` é parte do navegador: não há chave, não há
 * requisição, não há cobrança por caractere — o som é gerado no aparelho de
 * quem está fazendo o teste. Um TTS de provedor cobraria por item gerado, e
 * o nivelamento gera itens novos a cada lote, para cada pessoa, em cada
 * tentativa. Era o único jeito de o listening existir sem virar custo por uso.
 *
 * O preço disso é a voz: ela é sintética e varia por sistema. Para um item de
 * compreensão em nível CEFR isso serve — o que se mede é entender o que foi
 * dito, não reconhecer timbre humano.
 *
 * ## A transcrição fica ESCONDIDA
 *
 * Se ela aparece junto, o item vira leitura e para de medir escuta. Ela
 * continua acessível num toque, porque quem não consegue ouvir precisa dela e
 * porque errar sem poder conferir o texto não ensina nada.
 */

import { useEffect, useRef, useState } from "react";
import { locucao, SEM_VOZ_DO_IDIOMA, vozesDoIdioma } from "@/lib/fala";
import { ACC, ACC3, HAIRLINE, TEXT } from "@/lib/tokens";

/** Uma fala do diálogo: quem fala e o que diz. */
interface Fala {
  quem: string;
  texto: string;
}

/**
 * "Ana: I'll push it.\nMarc: Thanks." -> duas falas.
 *
 * Linha sem "Nome:" é continuação da fala anterior — diálogo real tem frase
 * que quebra em duas linhas, e lê-la como fala nova trocaria a voz no meio.
 */
export function separarFalas(contexto: string): Fala[] {
  const falas: Fala[] = [];
  for (const linha of contexto.split("\n")) {
    const limpa = linha.trim();
    if (!limpa) continue;
    const marca = limpa.match(/^([^:]{1,40}):\s*(.+)$/);
    if (marca) {
      falas.push({ quem: marca[1].trim(), texto: marca[2].trim() });
    } else if (falas.length > 0) {
      falas[falas.length - 1].texto += ` ${limpa}`;
    }
  }
  return falas;
}

/** As vozes do sistema chegam de forma assíncrona no Safari e no Chrome: na
 * primeira chamada a lista costuma vir vazia, e só o evento `voiceschanged`
 * avisa que encheu. Sem esperar, todo diálogo sairia na voz padrão. */
export function useVozes(idioma: string): { vozes: SpeechSynthesisVoice[]; semVozDoIdioma: boolean } {
  const [vozes, setVozes] = useState<SpeechSynthesisVoice[]>([]);
  // Só dá para dizer "não há voz" depois que o sistema entregou a lista —
  // antes disso ela vem vazia em todo navegador.
  const [carregou, setCarregou] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const carregar = () => {
      const todas = window.speechSynthesis.getVoices();
      if (todas.length > 0) setCarregou(true);
      setVozes(vozesDoIdioma(todas, idioma));
    };
    carregar();
    window.speechSynthesis.addEventListener("voiceschanged", carregar);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", carregar);
  }, [idioma]);

  return { vozes, semVozDoIdioma: carregou && vozes.length === 0 };
}

export function ListeningPlayer({
  contexto,
  idioma = "en",
}: {
  contexto: string;
  /** Código do idioma do item — o mesmo do nivelamento. */
  idioma?: string;
}) {
  const falas = separarFalas(contexto);
  const { vozes, semVozDoIdioma } = useVozes(idioma);
  const [tocando, setTocando] = useState(false);
  const [atual, setAtual] = useState(-1);
  const [mostrarTexto, setMostrarTexto] = useState(false);
  const cancelado = useRef(false);

  const suportado = typeof window !== "undefined" && !!window.speechSynthesis;

  // Sair da tela no meio da fala deixaria a voz falando sozinha: a síntese é
  // global do navegador e não morre com o componente.
  useEffect(() => {
    return () => {
      cancelado.current = true;
      window.speechSynthesis?.cancel();
    };
  }, []);

  // Item novo, áudio novo: sem isto, avançar a pergunta manteria a fala
  // anterior tocando por cima da próxima.
  useEffect(() => {
    window.speechSynthesis?.cancel();
    setTocando(false);
    setAtual(-1);
  }, [contexto]);

  /** Quem fala em cada linha ganha uma voz diferente, quando o sistema tem
   * mais de uma. É o que deixa o diálogo audível como diálogo. */
  function posicaoDaVoz(quem: string): number {
    const nomes = [...new Set(falas.map((f) => f.quem))];
    return Math.max(0, nomes.indexOf(quem));
  }

  function tocar() {
    if (!suportado || falas.length === 0) return;
    window.speechSynthesis.cancel();
    cancelado.current = false;
    setTocando(true);

    falas.forEach((fala, indice) => {
      // As vozes vêm da melhor para a pior; cada interlocutor pega a sua a
      // partir da melhor, e só dá a volta se o sistema tiver poucas.
      const fase = locucao(fala.texto, idioma, vozes, posicaoDaVoz(fala.quem));
      // Um pouco mais devagar que o padrão: é material de estudo em língua
      // estrangeira, e a velocidade nativa do sintetizador atropela quem
      // ainda está aprendendo.
      fase.rate = 0.92;
      fase.onstart = () => !cancelado.current && setAtual(indice);
      if (indice === falas.length - 1) {
        fase.onend = () => {
          if (cancelado.current) return;
          setTocando(false);
          setAtual(-1);
        };
      }
      window.speechSynthesis.speak(fase);
    });
  }

  function parar() {
    cancelado.current = true;
    window.speechSynthesis?.cancel();
    setTocando(false);
    setAtual(-1);
  }

  if (falas.length === 0) return null;

  return (
    <div
      style={{
        marginBottom: 16.8,
        padding: "11.2px 14px",
        borderRadius: 8,
        background: "rgba(233,233,237,.04)",
        borderLeft: `2px solid ${HAIRLINE}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 11.2, flexWrap: "wrap" }}>
        {suportado ? (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => (tocando ? parar() : tocar())}
            style={{ fontSize: 12.5 }}
          >
            {tocando ? "parar" : atual === -1 ? "ouvir o diálogo" : "ouvir de novo"}
          </button>
        ) : (
          <span style={{ fontSize: 11.5, color: TEXT.muted }}>
            Este navegador não tem voz para reproduzir o diálogo.
          </span>
        )}

        <button
          type="button"
          onClick={() => setMostrarTexto((atual) => !atual)}
          style={{
            border: "none",
            background: "transparent",
            padding: 0,
            font: "inherit",
            fontSize: 11.5,
            color: ACC3,
            cursor: "pointer",
          }}
        >
          {mostrarTexto ? "esconder transcrição" : "ver transcrição"}
        </button>

        <span style={{ fontSize: 11, color: TEXT.faint, marginLeft: "auto" }}>
          {falas.length} falas
        </span>
      </div>

      {suportado && semVozDoIdioma ? (
        <p role="note" style={{ margin: "8.4px 0 0", fontSize: 11.5, color: "#cfa25e", lineHeight: 1.5 }}>
          {SEM_VOZ_DO_IDIOMA}
        </p>
      ) : null}

      {/* A transcrição só aparece quando pedida: junto do áudio, o item
          viraria leitura e pararia de medir escuta. Quando aparece, a fala em
          curso é destacada — é o que ajuda a acompanhar. */}
      {(mostrarTexto || !suportado) ? (
        <div style={{ marginTop: 11.2, fontSize: 13.5, lineHeight: 1.6 }}>
          {falas.map((fala, indice) => (
            <p
              key={`${fala.quem}-${indice}`}
              style={{
                margin: "0 0 5.6px",
                color: indice === atual ? ACC : "rgba(233,233,237,.75)",
              }}
            >
              <span style={{ color: TEXT.faint }}>{fala.quem}:</span> {fala.texto}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
