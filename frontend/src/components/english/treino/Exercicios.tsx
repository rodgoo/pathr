/**
 * Os oito formatos do treino diário de idioma.
 *
 * Cada um treina uma coisa diferente, e é por isso que existem oito e não um:
 *
 * - múltipla escolha e imagem: RECONHECER a forma certa;
 * - lacuna: RECUPERAR a palavra dentro da frase;
 * - montar a frase: PRODUZIR a ordem das palavras;
 * - associar pares: FLUÊNCIA com o vocabulário que já se tem;
 * - escuta: ENTENDER o que foi dito;
 * - ditado: ouvir e ESCREVER, sem ver;
 * - fala: DIZER em voz alta.
 *
 * Todos são controlados de fora: recebem `travado` depois da resposta e
 * `resultado` com o gabarito, e só então mostram o certo e o errado. O
 * gabarito nunca chega antes — a correção é do servidor.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { PracticeAnswer, PracticeAnswerResult, PracticeItem } from "@/api/types";
import { useT, type Traduzir } from "@/lib/i18n";
import { ACC, ACC3, C, HAIRLINE, PANEL, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { IconButton } from "@/components/ui/IconButton";
import { ChoiceList } from "@/components/ui/ChoiceList";
import { ListeningPlayer, useVozes } from "@/components/english/ListeningPlayer";
import { locucao } from "@/lib/fala";
import { audiosDasFalas } from "@/lib/vozNeural";

/** Código de voz do navegador para cada idioma do catálogo. */
const VOZ: Record<string, string> = {
  en: "en-US",
  es: "es-ES",
  fr: "fr-FR",
  de: "de-DE",
  it: "it-IT",
  ja: "ja-JP",
  zh: "zh-CN",
  ko: "ko-KR",
  pt: "pt-BR",
};

/** tipo de exercício -> chave i18n do rótulo do formato. */
export const NOME_DO_FORMATO: Record<PracticeItem["type"], string> = {
  mcq: "idiomas.formato.mcq",
  gap: "idiomas.formato.gap",
  reorder: "idiomas.formato.reorder",
  match: "idiomas.formato.match",
  listening: "idiomas.formato.listening",
  dictation: "idiomas.formato.dictation",
  image: "idiomas.formato.image",
  speaking: "idiomas.formato.speaking",
};

/** O rótulo traduzido do formato do exercício. */
export function nomeDoFormato(tipo: PracticeItem["type"], t: Traduzir): string {
  return t(NOME_DO_FORMATO[tipo]);
}

export interface ExercicioProps {
  item: PracticeItem;
  idioma: string;
  travado: boolean;
  resultado: PracticeAnswerResult | null;
  onResponder: (resposta: PracticeAnswer) => void;
}

export function Exercicio(props: ExercicioProps) {
  const { item } = props;
  // `key` pelo id: exercício novo começa do zero, sem a escolha do anterior.
  switch (item.type) {
    case "mcq":
    case "image":
    case "gap":
    case "listening":
      return <Escolha key={item.id} {...props} />;
    case "reorder":
      return <MontarFrase key={item.id} {...props} />;
    case "match":
      return <AssociarPares key={item.id} {...props} />;
    case "dictation":
      return <Ditado key={item.id} {...props} />;
    case "speaking":
      return <Fala key={item.id} {...props} />;
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Reconhecer: múltipla escolha, imagem, lacuna e escuta
// ---------------------------------------------------------------------------

function Escolha({ item, idioma, travado, resultado, onResponder }: ExercicioProps) {
  const t = useT();
  const { payload } = item;
  const [escolha, setEscolha] = useState<number | null>(null);
  const alternativas = payload.alternativas ?? [];
  const certa =
    resultado && typeof resultado.correct_answer === "string"
      ? alternativas.indexOf(resultado.correct_answer)
      : -1;

  return (
    <div>
      {item.type === "image" && payload.emoji ? (
        // A imagem grande, sozinha: é ela que carrega a pergunta.
        <div
          role="img"
          aria-label={t("idiomas.exercicio.imagemAria")}
          style={{ fontSize: 88, lineHeight: 1, textAlign: "center", margin: "8px 0 18px" }}
        >
          {payload.emoji}
        </div>
      ) : null}

      {item.type === "listening" && payload.audio ? (
        <ListeningPlayer
          contexto={payload.dialogo ? payload.audio : `${t("idiomas.exercicio.voz")}: ${payload.audio}`}
          idioma={idioma}
        />
      ) : null}

      {item.type === "gap" && payload.frase ? <FraseComLacuna frase={payload.frase} /> : null}

      <ChoiceList
        label={t("idiomas.exercicio.alternativas")}
        options={alternativas}
        pick={escolha}
        answer={certa >= 0 ? certa : undefined}
        english
        numerada
        busy={travado}
        onPick={(indice) => {
          setEscolha(indice);
          onResponder({ indice });
        }}
      />
    </div>
  );
}

function FraseComLacuna({ frase }: { frase: string }) {
  const t = useT();
  const [antes, depois] = frase.split("___");
  return (
    <p style={{ fontSize: 18, lineHeight: 1.5, margin: "0 0 16px", color: TEXT.full }}>
      {antes}
      <span
        aria-label={t("idiomas.exercicio.lacunaAria")}
        style={{
          display: "inline-block",
          minWidth: 64,
          borderBottom: `2px solid ${ACC}`,
          margin: "0 4px",
        }}
      >
        &nbsp;
      </span>
      {depois}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Produzir a ordem: montar a frase
// ---------------------------------------------------------------------------

function MontarFrase({ item, travado, resultado, onResponder }: ExercicioProps) {
  const t = useT();
  const pecas = item.payload.pecas ?? [];
  // Índices das peças usadas, na ordem em que foram tocadas. Índice e não
  // texto: a mesma palavra pode aparecer duas vezes ("the … the").
  const [usadas, setUsadas] = useState<number[]>([]);
  const completa = pecas.length > 0 && usadas.length === pecas.length;

  return (
    <div>
      {item.payload.traducao ? (
        <p style={{ fontSize: 13.5, color: TEXT.muted, margin: "0 0 12px" }}>
          “{item.payload.traducao}”
        </p>
      ) : null}

      <div
        aria-label={t("idiomas.exercicio.fraseMontada")}
        style={{
          minHeight: 52,
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
          padding: "10px 0",
          borderBottom: `1px solid ${HAIRLINE}`,
          marginBottom: 12,
        }}
      >
        {usadas.map((indice, posicao) => (
          <Peca
            key={`${indice}-${posicao}`}
            texto={pecas[indice]}
            desabilitada={travado}
            onClick={() => setUsadas((atual) => atual.filter((_, p) => p !== posicao))}
          />
        ))}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
        {pecas.map((texto, indice) =>
          usadas.includes(indice) ? (
            // O lugar vazio fica: se as peças se reorganizassem a cada toque,
            // a pessoa perderia de vista a que ia tocar em seguida.
            <span
              key={indice}
              aria-hidden
              style={{
                padding: "7px 12px",
                borderRadius: 8,
                background: "rgba(233,233,237,.05)",
                color: "transparent",
                fontSize: 15,
              }}
            >
              {texto}
            </span>
          ) : (
            <Peca
              key={indice}
              texto={texto}
              desabilitada={travado}
              onClick={() => setUsadas((atual) => [...atual, indice])}
            />
          ),
        )}
      </div>

      {!travado ? (
        <button
          type="button"
          className="btn btn-primary"
          disabled={!completa}
          onClick={() => onResponder({ tokens: usadas.map((i) => pecas[i]) })}
        >
          <Icon name="check" size={15} />
          {t("idiomas.exercicio.conferir")}
        </button>
      ) : null}

      {resultado && !resultado.is_correct && typeof resultado.correct_answer === "string" ? (
        <RespostaCerta texto={resultado.correct_answer} />
      ) : null}
    </div>
  );
}

function Peca({
  texto,
  onClick,
  desabilitada,
}: {
  texto: string;
  onClick: () => void;
  desabilitada: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={desabilitada}
      style={{
        padding: "7px 12px",
        borderRadius: 8,
        border: "1px solid rgba(233,233,237,.18)",
        background: PANEL,
        color: TEXT.full,
        font: "inherit",
        fontSize: 15,
        cursor: desabilitada ? "default" : "pointer",
      }}
    >
      {texto}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Fluência: associar pares
// ---------------------------------------------------------------------------

const estiloDoPar = {
  padding: "10px 12px",
  borderRadius: 8,
  border: "1px solid rgba(233,233,237,.16)",
  background: PANEL,
  color: TEXT.full,
  font: "inherit",
  fontSize: 14,
  textAlign: "left" as const,
  cursor: "pointer",
};

function AssociarPares({ item, travado, resultado, onResponder }: ExercicioProps) {
  const t = useT();
  const esquerda = item.payload.esquerda ?? [];
  const direita = item.payload.direita ?? [];
  const [pares, setPares] = useState<Record<string, number>>({});
  const [selecionada, setSelecionada] = useState<number | null>(null);
  const gabarito =
    resultado && resultado.correct_answer && typeof resultado.correct_answer === "object"
      ? resultado.correct_answer
      : null;
  const usadasDireita = new Set(Object.values(pares));
  const completo = esquerda.length > 0 && Object.keys(pares).length === esquerda.length;

  function corDoPar(esq: number): string {
    if (!gabarito || pares[String(esq)] === undefined) return ACC;
    return gabarito[String(esq)] === pares[String(esq)] ? C.verde : C.ambar;
  }

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 14 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {esquerda.map((termo, i) => {
            const ligado = pares[String(i)] !== undefined;
            return (
              <button
                key={termo}
                type="button"
                disabled={travado}
                aria-pressed={selecionada === i}
                onClick={() => setSelecionada(selecionada === i ? null : i)}
                style={{
                  ...estiloDoPar,
                  borderColor:
                    selecionada === i ? ACC : ligado ? corDoPar(i) : "rgba(233,233,237,.16)",
                  background: selecionada === i ? "rgba(145,132,217,.14)" : PANEL,
                }}
              >
                {termo}
                {ligado ? (
                  <span style={{ display: "block", fontSize: 11.5, color: corDoPar(i), marginTop: 2 }}>
                    → {direita[pares[String(i)]]}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {direita.map((traducao, j) => (
            <button
              key={traducao}
              type="button"
              disabled={travado || selecionada === null || usadasDireita.has(j)}
              onClick={() => {
                if (selecionada === null) return;
                setPares((atual) => ({ ...atual, [String(selecionada)]: j }));
                setSelecionada(null);
              }}
              style={{ ...estiloDoPar, opacity: usadasDireita.has(j) ? 0.4 : 1 }}
            >
              {traducao}
            </button>
          ))}
        </div>
      </div>

      {!travado ? (
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!completo}
            onClick={() => onResponder({ pares })}
          >
            <Icon name="check" size={15} />
            {t("idiomas.exercicio.conferir")}
          </button>
          {Object.keys(pares).length > 0 ? (
            <IconButton icon="undo" label={t("idiomas.exercicio.recomecar")} onClick={() => setPares({})} />
          ) : (
            <span style={{ fontSize: 12, color: TEXT.faint }}>
              {t("idiomas.exercicio.toqueTermo")}
            </span>
          )}
        </div>
      ) : null}

      {gabarito && resultado && !resultado.is_correct ? (
        <div style={{ fontSize: 13, color: TEXT.muted, marginTop: 10 }}>
          {esquerda.map((termo, i) => (
            <div key={termo}>
              {termo} → <span style={{ color: C.verde }}>{direita[gabarito[String(i)]]}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ouvir e escrever: ditado
// ---------------------------------------------------------------------------

/**
 * Toca uma frase, sem transcrição.
 *
 * Não reaproveita o player da escuta: aquele mostra a transcrição num botão,
 * e também quando o navegador não tem voz — o que no ditado entregaria a
 * resposta. "Mais devagar" é o recurso clássico de todo exercício de ditado.
 */
function OuvirFrase({ texto, idioma }: { texto: string; idioma: string }) {
  const t = useT();
  const temSintese = typeof window !== "undefined" && !!window.speechSynthesis;
  const [tocando, setTocando] = useState(false);
  const [preparando, setPreparando] = useState(false);
  // Só quando a voz neural falhou: com ela, o inventário de vozes do aparelho
  // não tem efeito nenhum sobre o que se ouve.
  const [naVozDoNavegador, setNaVozDoNavegador] = useState(false);
  const { vozes, semVozDoIdioma } = useVozes(idioma);
  const tocador = useRef<HTMLAudioElement | null>(null);

  function calar() {
    window.speechSynthesis?.cancel();
    if (tocador.current) {
      tocador.current.pause();
      tocador.current = null;
    }
  }

  useEffect(() => {
    return () => calar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [texto]);

  async function tocar(velocidade: number) {
    calar();
    setTocando(true);
    setPreparando(true);

    const audios = await audiosDasFalas([{ texto, voz: 0 }], idioma);
    setPreparando(false);

    if (audios) {
      setNaVozDoNavegador(false);
      const audio = audios[0];
      tocador.current = audio;
      // "Mais devagar" continua existindo com o áudio gravado: `playbackRate`
      // estica o tempo, e o navegador corrige o tom sozinho — a frase sai
      // lenta sem virar voz grave, que é o que o ditado precisa.
      audio.playbackRate = velocidade;
      audio.onended = () => {
        tocador.current = null;
        setTocando(false);
      };
      audio.play().catch(() => setTocando(false));
      return;
    }

    if (!temSintese) {
      setTocando(false);
      setNaVozDoNavegador(true);
      return;
    }
    setNaVozDoNavegador(true);
    const fala = locucao(texto, idioma, vozes);
    fala.rate = velocidade;
    fala.onend = () => setTocando(false);
    window.speechSynthesis.speak(fala);
  }

  return (
    <div style={{ display: "flex", gap: 8, margin: "4px 0 14px", flexWrap: "wrap" }}>
      <button type="button" className="btn btn-secondary" onClick={() => void tocar(0.92)}>
        <Icon name="playSolid" size={14} />
        {preparando ? t("idiomas.exercicio.preparando") : tocando ? t("idiomas.exercicio.tocando") : t("idiomas.exercicio.ouvir")}
      </button>
      <button type="button" className="btn btn-ghost" onClick={() => void tocar(0.6)}>
        {t("idiomas.exercicio.maisDevagar")}
      </button>
      {naVozDoNavegador && (semVozDoIdioma || !temSintese) ? (
        <p role="note" style={{ flexBasis: "100%", margin: 0, fontSize: 11.5, color: C.ambar }}>
          {temSintese
            ? t("idiomas.semVozDoIdioma")
            : t("idiomas.exercicio.semVozDitado")}
        </p>
      ) : null}
    </div>
  );
}

function Ditado({ item, idioma, travado, resultado, onResponder }: ExercicioProps) {
  const t = useT();
  const [texto, setTexto] = useState("");
  return (
    <div>
      <OuvirFrase texto={item.payload.audio ?? ""} idioma={idioma} />
      <textarea
        className="input"
        rows={3}
        value={texto}
        disabled={travado}
        aria-label={t("idiomas.exercicio.oQueOuviu")}
        placeholder={t("idiomas.exercicio.escrevaOuviu")}
        lang={idioma}
        spellCheck={false}
        autoCapitalize="off"
        onChange={(evento) => setTexto(evento.target.value)}
        style={{ width: "100%", fontSize: 16, resize: "vertical" }}
      />
      {!travado ? (
        <button
          type="button"
          className="btn btn-primary"
          style={{ marginTop: 10 }}
          disabled={texto.trim().length === 0}
          onClick={() => onResponder({ texto })}
        >
          {t("idiomas.exercicio.conferir")}
        </button>
      ) : null}
      {resultado ? <DetalheDeTexto resultado={resultado} /> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dizer: fala em voz alta
// ---------------------------------------------------------------------------

interface Reconhecimento {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  onresult: ((evento: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((evento: { error: string }) => void) | null;
  onend: (() => void) | null;
}

function criarReconhecimento(): Reconhecimento | null {
  if (typeof window === "undefined") return null;
  const janela = window as unknown as {
    SpeechRecognition?: new () => Reconhecimento;
    webkitSpeechRecognition?: new () => Reconhecimento;
  };
  const Classe = janela.SpeechRecognition ?? janela.webkitSpeechRecognition;
  return Classe ? new Classe() : null;
}

/**
 * Leitura em voz alta, corrigida pelo reconhecimento de voz do navegador.
 *
 * Sem microfone, ou em navegador sem reconhecimento (o Firefox não tem), o
 * exercício oferece "Não posso falar agora" — que o servidor registra como
 * PULADO, e não como erro. Culpar a pronúncia pela falta de um microfone
 * derrubaria o nível de fala de quem só estava num lugar onde não podia falar.
 */
function Fala({ item, idioma, travado, resultado, onResponder }: ExercicioProps) {
  const t = useT();
  const reconhecimento = useMemo(criarReconhecimento, []);
  const [ouvindo, setOuvindo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const texto = item.payload.texto ?? "";
  const { vozes } = useVozes(idioma);

  useEffect(() => () => reconhecimento?.stop(), [reconhecimento]);

  /** O modelo que a pessoa vai imitar.
   *
   * É onde a voz neural mais importa em todo o treino: aqui o áudio não é
   * material de escuta, é o alvo da imitação. Uma voz que erra a entonação
   * ensina a errar junto, e logo em seguida o reconhecimento de fala cobra a
   * pronúncia certa. */
  async function ouvirModelo() {
    window.speechSynthesis?.cancel();
    const audios = await audiosDasFalas([{ texto, voz: 0 }], idioma);
    if (audios) {
      audios[0].playbackRate = 0.9;
      void audios[0].play().catch(() => undefined);
      return;
    }
    if (!window.speechSynthesis) return;
    const fala = locucao(texto, idioma, vozes);
    fala.rate = 0.9;
    window.speechSynthesis.speak(fala);
  }

  function gravar() {
    if (!reconhecimento) return;
    setErro(null);
    reconhecimento.lang = VOZ[idioma] ?? idioma;
    reconhecimento.interimResults = false;
    reconhecimento.maxAlternatives = 1;
    reconhecimento.onresult = (evento) => {
      onResponder({ texto: evento.results[0]?.[0]?.transcript ?? "" });
    };
    reconhecimento.onerror = (evento) => {
      setErro(
        evento.error === "not-allowed"
          ? t("idiomas.exercicio.semMicrofone")
          : t("idiomas.exercicio.naoOuvi"),
      );
    };
    reconhecimento.onend = () => setOuvindo(false);
    setOuvindo(true);
    reconhecimento.start();
  }

  return (
    <div>
      <p style={{ fontSize: 20, lineHeight: 1.45, margin: "0 0 6px", color: TEXT.full }} lang={idioma}>
        {texto}
      </p>
      {item.payload.traducao ? (
        <p style={{ fontSize: 13, color: TEXT.muted, margin: "0 0 14px" }}>
          “{item.payload.traducao}”
        </p>
      ) : null}

      {!travado ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button type="button" className="btn btn-ghost" onClick={ouvirModelo}>
            <Icon name="playSolid" size={14} />
            {t("idiomas.exercicio.ouvirComoSeDiz")}
          </button>
          {reconhecimento ? (
            <button type="button" className="btn btn-primary" disabled={ouvindo} onClick={gravar}>
              <Icon name="mic" size={15} />
              {ouvindo ? t("idiomas.exercicio.ouvindoFale") : t("idiomas.exercicio.falar")}
            </button>
          ) : (
            <span style={{ fontSize: 12.5, color: TEXT.muted }}>
              {t("idiomas.exercicio.semReconhecimento")}
            </span>
          )}
          <button type="button" className="btn btn-ghost" onClick={() => onResponder({ texto: "" })}>
            {t("idiomas.exercicio.naoPossoFalar")}
          </button>
        </div>
      ) : null}
      {erro ? <p style={{ fontSize: 12.5, color: C.ambar, marginTop: 8 }}>{erro}</p> : null}
      {resultado && !resultado.skipped ? <DetalheDeTexto resultado={resultado} fala /> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pedaços da correção
// ---------------------------------------------------------------------------

function RespostaCerta({ texto }: { texto: string }) {
  const t = useT();
  return (
    <p style={{ fontSize: 14, margin: "10px 0 0", color: TEXT.muted }}>
      {t("idiomas.exercicio.respostaCerta")} <span style={{ color: C.verde }}>{texto}</span>
    </p>
  );
}

function DetalheDeTexto({
  resultado,
  fala = false,
}: {
  resultado: PracticeAnswerResult;
  fala?: boolean;
}) {
  const t = useT();
  const detalhe = resultado.detail ?? {};
  const certa = typeof resultado.correct_answer === "string" ? resultado.correct_answer : "";
  return (
    <div style={{ marginTop: 10, fontSize: 13.5, lineHeight: 1.55 }}>
      {!resultado.is_correct || detalhe.acentos ? (
        <div style={{ color: TEXT.muted }}>
          {fala ? t("idiomas.exercicio.aFraseEra") : t("idiomas.exercicio.oTextoEra")}: <span style={{ color: C.verde }}>{certa}</span>
        </div>
      ) : null}
      {detalhe.faltaram && detalhe.faltaram.length > 0 ? (
        <div style={{ color: TEXT.faint, marginTop: 4 }}>
          {fala ? t("idiomas.exercicio.naoReconheci") : t("idiomas.exercicio.faltouDiferente")}:{" "}
          {detalhe.faltaram.map((palavra, i) => (
            <span key={`${palavra}-${i}`} style={{ color: C.ambar }}>
              {i > 0 ? ", " : ""}
              {palavra}
            </span>
          ))}
        </div>
      ) : null}
      {detalhe.acentos ? (
        <div style={{ color: ACC3, marginTop: 4 }}>{t("idiomas.exercicio.atencaoAcentos")}</div>
      ) : null}
    </div>
  );
}
