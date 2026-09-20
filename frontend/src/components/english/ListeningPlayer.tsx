/**
 * O áudio do item de listening.
 *
 * ## Duas fontes de voz, nesta ordem
 *
 * 1. **`/languages/tts`** — TTS neural do Gemini, na chave que o app já usa
 *    para o resto da IA. É quem fala normalmente.
 * 2. **`speechSynthesis`** — o sintetizador do próprio navegador, quando a
 *    primeira não pôde responder.
 *
 * A ordem já foi a inversa, e por um motivo defensável: custo. A síntese do
 * navegador não tem chave nem cobrança por caractere, e o nivelamento gera
 * itens novos a cada lote, para cada pessoa, em cada tentativa — um TTS pago
 * por item era o que impedia o listening de existir.
 *
 * O que derrubou essa escolha não foi o custo ter mudado, foi a VOZ não ser
 * escolha do app. O navegador só oferece o que o sistema tem instalado, e num
 * Windows em português sobra uma voz de inglês da geração SAPI antiga, que lê
 * palavra por palavra: não pausa na vírgula, não sobe no ponto de
 * interrogação, não separa uma fala da outra. Compreensão em nível CEFR se
 * apoia em prosódia — sem ela o item mede outra coisa.
 *
 * O custo continua contido, e é `app/tts.py` que explica como: cache por
 * conteúdo, teto de tamanho e o tier gratuito. E a queda para a voz antiga é
 * automática — sem cota, o áudio piora, mas a atividade continua existindo.
 *
 * ## Tudo ou nada por diálogo
 *
 * Se uma fala vier do servidor e outra do sintetizador, o timbre troca no
 * meio e soa como defeito. Por isso `audiosDasFalas` é tudo ou nada: falhou
 * uma, o diálogo inteiro sai pela voz do navegador.
 *
 * ## A transcrição fica ESCONDIDA
 *
 * Se ela aparece junto, o item vira leitura e para de medir escuta. Ela
 * continua acessível num toque, porque quem não consegue ouvir precisa dela e
 * porque errar sem poder conferir o texto não ensina nada.
 */

import { useEffect, useRef, useState } from "react";
import { locucao, vozesDoIdioma } from "@/lib/fala";
import { audiosDasFalas } from "@/lib/vozNeural";
import { useT } from "@/lib/i18n";
import { ACC, ACC3, HAIRLINE, TEXT } from "@/lib/tokens";
import { IconButton } from "@/components/ui/IconButton";

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
  const t = useT();
  const falas = separarFalas(contexto);
  const { vozes, semVozDoIdioma } = useVozes(idioma);
  const [tocando, setTocando] = useState(false);
  // Gerar voz neural leva segundos, e o clique precisa responder na hora.
  // Sem este estado, o botão ficaria parado em "Ouvir" durante a espera e a
  // pessoa clicaria de novo, achando que não pegou.
  const [preparando, setPreparando] = useState(false);
  // Verdadeiro só quando a voz neural falhou e quem está falando é o
  // sintetizador do sistema. É o que decide mostrar o aviso de pronúncia:
  // com a voz do servidor, o inventário de vozes do aparelho não importa.
  const [naVozDoNavegador, setNaVozDoNavegador] = useState(false);
  const [atual, setAtual] = useState(-1);
  const [mostrarTexto, setMostrarTexto] = useState(false);
  const cancelado = useRef(false);
  // O áudio em curso, para poder pará-lo. A síntese do navegador é global e
  // se cancela sozinha; um `<audio>` é um objeto, e sem guardá-lo aqui o
  // botão "Parar" não teria o que parar.
  const tocador = useRef<HTMLAudioElement | null>(null);

  const temSintese = typeof window !== "undefined" && !!window.speechSynthesis;

  /** Silêncio, venha ele do sintetizador ou de um `<audio>`. */
  function calar() {
    window.speechSynthesis?.cancel();
    if (tocador.current) {
      tocador.current.pause();
      tocador.current = null;
    }
  }

  // Sair da tela no meio da fala deixaria a voz falando sozinha: a síntese é
  // global do navegador e não morre com o componente.
  useEffect(() => {
    return () => {
      cancelado.current = true;
      calar();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Item novo, áudio novo: sem isto, avançar a pergunta manteria a fala
  // anterior tocando por cima da próxima.
  useEffect(() => {
    calar();
    setTocando(false);
    setPreparando(false);
    setAtual(-1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contexto]);

  /** Quem fala em cada linha ganha uma voz diferente. É o que deixa o diálogo
   * audível como diálogo, e vale para as duas fontes de voz. */
  function posicaoDaVoz(quem: string): number {
    const nomes = [...new Set(falas.map((f) => f.quem))];
    return Math.max(0, nomes.indexOf(quem));
  }

  function terminou() {
    if (cancelado.current) return;
    tocador.current = null;
    setTocando(false);
    setAtual(-1);
  }

  /** Toca os áudios do servidor em sequência.
   *
   * Um de cada vez, e não todos de uma vez: é o encadeamento por `onended`
   * que mantém o destaque da linha em curso e a ordem das falas. */
  function tocarEmSequencia(audios: HTMLAudioElement[], indice: number) {
    if (cancelado.current || indice >= audios.length) {
      terminou();
      return;
    }
    const audio = audios[indice];
    tocador.current = audio;
    setAtual(indice);
    audio.onended = () => tocarEmSequencia(audios, indice + 1);
    // Um `play()` recusado (autoplay, aba em segundo plano) não pode deixar o
    // botão preso em "Parar": trata como fim.
    audio.play().catch(() => terminou());
  }

  /** O caminho antigo: o sintetizador do próprio navegador. */
  function tocarComSintese() {
    if (!temSintese) {
      // Nem voz do servidor, nem sintetizador: não há como tocar nada. O
      // estado precisa mudar MESMO assim, porque é dele que depende o aviso
      // logo abaixo — sem isto a tela ficava muda, e "apertei ouvir e não
      // aconteceu nada" é o pior jeito possível de falhar: quem está do outro
      // lado não sabe se o defeito é do app, do som do computador ou dele.
      setNaVozDoNavegador(true);
      terminou();
      return;
    }
    setNaVozDoNavegador(true);
    window.speechSynthesis.cancel();

    falas.forEach((fala, indice) => {
      // As vozes vêm da melhor para a pior; cada interlocutor pega a sua a
      // partir da melhor, e só dá a volta se o sistema tiver poucas.
      const fase = locucao(fala.texto, idioma, vozes, posicaoDaVoz(fala.quem));
      // Um pouco mais devagar que o padrão: é material de estudo em língua
      // estrangeira, e a velocidade nativa do sintetizador atropela quem
      // ainda está aprendendo.
      fase.rate = 0.92;
      fase.onstart = () => !cancelado.current && setAtual(indice);
      if (indice === falas.length - 1) fase.onend = terminou;
      window.speechSynthesis.speak(fase);
    });
  }

  async function tocar() {
    if (falas.length === 0) return;
    calar();
    cancelado.current = false;
    setTocando(true);
    setPreparando(true);

    // A voz neural primeiro. `audiosDasFalas` devolve null em qualquer falha
    // — inclusive uma única fala que não veio — e aí o diálogo inteiro sai
    // pelo sintetizador, para não trocar de timbre no meio.
    const audios = await audiosDasFalas(
      falas.map((fala) => ({ texto: fala.texto, voz: posicaoDaVoz(fala.quem) })),
      idioma,
    );

    // Parar durante a espera: a pessoa desistiu, e o áudio que acabou de
    // chegar não pode começar a tocar depois disso.
    if (cancelado.current) {
      setPreparando(false);
      return;
    }
    setPreparando(false);

    if (audios) {
      setNaVozDoNavegador(false);
      tocarEmSequencia(audios, 0);
      return;
    }
    tocarComSintese();
  }

  function parar() {
    cancelado.current = true;
    calar();
    setTocando(false);
    setPreparando(false);
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
        <IconButton
          icon={tocando ? "stop" : "playSolid"}
          label={
            preparando
              ? t("idiomas.listening.preparandoAudio")
              : tocando
                ? t("idiomas.listening.parar")
                : atual === -1
                  ? t("idiomas.listening.ouvirDialogo")
                  : t("idiomas.listening.ouvirDeNovo")
          }
          tone="secondary"
          onClick={() => (tocando ? parar() : void tocar())}
        />

        <IconButton
          icon={mostrarTexto ? "eyeOff" : "eye"}
          label={mostrarTexto ? t("idiomas.listening.esconderTranscricao") : t("idiomas.listening.verTranscricao")}
          pressed={mostrarTexto}
          color={ACC3}
          onClick={() => setMostrarTexto((atual) => !atual)}
        />

        <span style={{ fontSize: 11, color: TEXT.faint, marginLeft: "auto" }}>
          {falas.length === 1
            ? t("idiomas.listening.falasUm", { n: falas.length })
            : t("idiomas.listening.falasVarias", { n: falas.length })}
        </span>
      </div>

      {/* Só quando a voz neural falhou E o aparelho também não tem voz do
          idioma: aí o áudio realmente sai com pronúncia de outra língua, e a
          pessoa precisa saber que o problema não é o ouvido dela. Enquanto o
          servidor responde, nada disso importa e o aviso não aparece. */}
      {naVozDoNavegador && (semVozDoIdioma || !temSintese) ? (
        <p role="note" style={{ margin: "8.4px 0 0", fontSize: 11.5, color: "#cfa25e", lineHeight: 1.5 }}>
          {temSintese ? t("idiomas.semVozDoIdioma") : t("idiomas.listening.semVozNavegador")}
        </p>
      ) : null}

      {/* A transcrição só aparece quando pedida: junto do áudio, o item
          viraria leitura e pararia de medir escuta. Quando aparece, a fala em
          curso é destacada — é o que ajuda a acompanhar.

          A exceção é não haver áudio NENHUM — nem o do servidor, nem o do
          navegador. Aí o item ficaria sem enunciado, e um item sem enunciado
          não mede escuta, só impede de responder. Antes bastava não haver
          `speechSynthesis` para cair aqui; agora é preciso que a voz neural
          também tenha falhado, o que só se sabe depois da primeira tentativa. */}
      {mostrarTexto || (naVozDoNavegador && !temSintese) ? (
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
