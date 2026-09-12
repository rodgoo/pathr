/**
 * O artigo lido DENTRO do PathR, marcando progresso conforme a rolagem.
 *
 * Não é um `<iframe>` do site original: metade dos sites da biblioteca recusa
 * ser exibida dentro de outro (medido — freecodecamp, docs.github e w3schools
 * respondem `x-frame-options` ou `frame-ancestors 'self'`), e o bloqueio não é
 * detectável pelo JavaScript. O quadro só ficaria em branco. Quem busca e
 * extrai é o servidor; aqui só se renderiza o texto já limpo.
 *
 * A rolagem é o progresso. Num vídeo o player diz onde a pessoa está; num
 * texto, a única evidência equivalente é quanto dele passou pela tela. Mede-se
 * a MAIOR posição alcançada, e não a atual: rolar de volta para reler um
 * trecho não é desandar o progresso.
 *
 * E é essa mesma fração que traz a pessoa de volta. Reabrir um artigo começava
 * no topo — o progresso estava salvo, mas era preciso rolar à mão até achar o
 * ponto. Agora a caixa abre onde a leitura parou. Fração e não pixels: o texto
 * reflui com a largura, e 60% do artigo no celular é o mesmo trecho que 60% no
 * computador, enquanto 3.000px não são.
 */

import { useEffect, useRef, useState } from "react";
import type { ReaderContent } from "@/api/types";
import { ACC, ACC3, HAIRLINE, TEXT } from "@/lib/tokens";

/** Palavras por minuto de leitura técnica — mais devagar que prosa, porque
 * bloco de código se lê parando. */
const PALAVRAS_POR_MINUTO = 180;

/** De quanto em quanto tempo a posição é gravada. Igual ao vídeo. */
const INTERVALO_GRAVACAO_MS = 15_000;

/** A partir daqui o artigo conta como terminado, e reabrir volta ao topo:
 * quem abre de novo algo que já leu inteiro quer reler, e cair no último
 * parágrafo obrigaria a rolar tudo de volta. */
const RELER_A_PARTIR_DE = 0.97;

export function ArticleReader({
  conteudo,
  onProgresso,
  comecarEm = 0,
}: {
  conteudo: ReaderContent;
  /** A maior fração do artigo já alcançada, de 0 a 1. */
  onProgresso: (fracao: number) => void;
  /** Onde a leitura parou da última vez (0 a 1), vindo do servidor. */
  comecarEm?: number;
}) {
  const caixa = useRef<HTMLDivElement | null>(null);
  // Começa do que já foi lido, e não de zero: sem isto a barra reabria em 0%
  // com o progresso salvo.
  const maiorFracao = useRef(comecarEm);
  const [lido, setLido] = useState(comecarEm);
  const inicio = useRef(comecarEm >= RELER_A_PARTIR_DE ? 0 : comecarEm);
  const [retomado, setRetomado] = useState(false);

  const reportar = useRef(onProgresso);
  reportar.current = onProgresso;

  useEffect(() => {
    const elemento = caixa.current;
    if (!elemento || conteudo.status !== "ok") return;

    const medir = () => {
      const rolavel = elemento.scrollHeight - elemento.clientHeight;
      // Artigo curto cabe inteiro na tela e nunca rola. Abrir já é ler.
      const fracao = rolavel <= 0 ? 1 : elemento.scrollTop / rolavel;
      const limitada = Math.max(0, Math.min(1, fracao));
      if (limitada > maiorFracao.current) {
        maiorFracao.current = limitada;
        setLido(limitada);
      }
    };

    // Posiciona onde a leitura parou. Reaplica quando uma imagem termina de
    // carregar — ela muda a altura do texto e empurraria o trecho para longe —
    // mas só até a pessoa mexer. Depois disso a posição é dela, e a tela não
    // pode arrancá-la de onde escolheu ficar.
    let interagiu = false;
    const posicionar = () => {
      if (interagiu || inicio.current <= 0) return;
      const rolavel = elemento.scrollHeight - elemento.clientHeight;
      if (rolavel > 0) elemento.scrollTop = inicio.current * rolavel;
    };
    const marcarInteracao = () => {
      interagiu = true;
    };
    const gestos = ["wheel", "touchstart", "pointerdown", "keydown"] as const;
    posicionar();
    if (inicio.current > 0.02) setRetomado(true);
    elemento.addEventListener("load", posicionar, true);
    for (const gesto of gestos) {
      elemento.addEventListener(gesto, marcarInteracao, { passive: true });
    }

    medir();
    elemento.addEventListener("scroll", medir, { passive: true });
    const timer = window.setInterval(() => {
      if (maiorFracao.current > 0) reportar.current(maiorFracao.current);
    }, INTERVALO_GRAVACAO_MS);

    return () => {
      elemento.removeEventListener("load", posicionar, true);
      for (const gesto of gestos) elemento.removeEventListener(gesto, marcarInteracao);
      elemento.removeEventListener("scroll", medir);
      window.clearInterval(timer);
      // Fechar é o momento mais comum de sair: grava o alcançado antes de ir.
      if (maiorFracao.current > 0) reportar.current(maiorFracao.current);
    };
  }, [conteudo.status, conteudo.id]);

  /**
   * Um link do artigo não pode levar o app embora.
   *
   * O HTML é de terceiro e os links vêm como vieram: sem `target`, clicar em
   * "configure-pages action" trocava o PathR pela página do GitHub NA MESMA
   * aba. Instalado na tela de início, onde não há barra de endereço nem botão
   * de voltar, isso é o app sumir — e com ele o módulo aberto, o quiz em
   * andamento e a posição da leitura.
   *
   * O carimbo é feito depois de cada renderização, e não no servidor, porque é
   * decisão de apresentação: o mesmo HTML guardado serve para qualquer lugar
   * que venha a mostrá-lo.
   */
  useEffect(() => {
    const elemento = caixa.current;
    if (!elemento || conteudo.status !== "ok") return;
    for (const link of elemento.querySelectorAll("a[href]")) {
      link.setAttribute("target", "_blank");
      // `noopener` é o que impede a página aberta de mexer na nossa pela
      // referência `window.opener` — vale para qualquer link de fora.
      link.setAttribute("rel", "noreferrer noopener");
    }
  }, [conteudo.status, conteudo.html]);

  if (conteudo.status !== "ok" || !conteudo.html) {
    return <LeituraIndisponivel conteudo={conteudo} />;
  }

  const minutos = conteudo.words ? Math.max(1, Math.round(conteudo.words / PALAVRAS_POR_MINUTO)) : null;

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 8.4,
          flexWrap: "wrap",
          marginBottom: 8.4,
          fontSize: 11.5,
          color: TEXT.faint,
        }}
      >
        {minutos ? <span>{minutos} min de leitura</span> : null}
        <span>{Math.round(lido * 100)}% lido</span>
        {/* A fonte, sempre. O modo leitura não substitui o original: quem
            escreveu merece o crédito e a visita. */}
        <a
          href={conteudo.url}
          target="_blank"
          rel="noreferrer noopener"
          style={{ marginLeft: "auto", color: ACC3 }}
        >
          ler no site original{conteudo.provider ? ` · ${conteudo.provider}` : ""}
        </a>
      </div>

      {retomado ? (
        <div role="status" style={{ fontSize: 12, color: TEXT.muted, marginBottom: 8.4 }}>
          Retomado de onde você parou ({Math.round(inicio.current * 100)}%).{" "}
          <button
            type="button"
            onClick={() => {
              // Zerar o início também desliga o reposicionamento: uma imagem
              // que carregasse depois arrastaria a pessoa de volta ao meio.
              inicio.current = 0;
              if (caixa.current) caixa.current.scrollTop = 0;
              setRetomado(false);
            }}
            style={{
              border: 0,
              background: "transparent",
              padding: 0,
              font: "inherit",
              color: ACC3,
              textDecoration: "underline",
              cursor: "pointer",
            }}
          >
            Voltar ao início
          </button>
        </div>
      ) : null}

      <div
        aria-hidden
        style={{ height: 3, borderRadius: 2, background: "rgba(233,233,237,.14)", marginBottom: 14 }}
      >
        <div
          style={{
            width: `${lido * 100}%`,
            height: "100%",
            borderRadius: 2,
            background: ACC,
            transition: "width .2s",
          }}
        />
      </div>

      <div
        ref={caixa}
        className="leitura"
        style={{
          maxHeight: "62vh",
          overflowY: "auto",
          paddingRight: 14,
          fontSize: 14.5,
          lineHeight: 1.7,
          color: "rgba(233,233,237,.86)",
        }}
        // O HTML vem do nosso servidor, já extraído e sanitizado com lista de
        // permissão (nh3, sem script/iframe/on*/style) — ver
        // backend/app/services/reader.py. É o único lugar do app que injeta
        // markup, e é por isso que a limpeza mora no servidor, onde não pode
        // ser pulada por quem chama.
        dangerouslySetInnerHTML={{ __html: conteudo.html }}
      />
    </div>
  );
}

/**
 * O que aparece quando a extração não deu.
 *
 * Diz o motivo e oferece o original. Um quadro vazio faria a pessoa achar que
 * o app quebrou; a página pode simplesmente estar fora, recusar robôs ou não
 * ter texto extraível.
 */
function LeituraIndisponivel({ conteudo }: { conteudo: ReaderContent }) {
  return (
    <div
      style={{
        padding: 22.4,
        borderRadius: 10,
        border: `1px solid ${HAIRLINE}`,
        textAlign: "center",
      }}
    >
      <p style={{ fontSize: 13.5, color: "rgba(233,233,237,.75)", margin: "0 0 5.6px" }}>
        {conteudo.error ?? "Ainda não busquei o texto deste material."}
      </p>
      <p style={{ fontSize: 12, color: TEXT.faint, margin: "0 0 16.8px" }}>
        Dá para ler no site de origem — e o progresso continua sendo marcado aqui.
      </p>
      <a
        className="btn btn-secondary"
        href={conteudo.url}
        target="_blank"
        rel="noreferrer noopener"
        style={{ textDecoration: "none" }}
      >
        Abrir no site original
      </a>
    </div>
  );
}
