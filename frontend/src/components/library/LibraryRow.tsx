/**
 * Uma linha da biblioteca.
 *
 * O título abre a fonte original numa aba nova — o app cura e acompanha, não
 * re-hospeda o conteúdo de ninguém. O botão de estado fica à parte para
 * marcar "concluído" não depender de sair da página.
 */

import { useEffect, useState } from "react";
import type { Resource, ResourceState } from "@/api/types";
import { ACC, ACC4, C, SIZE, TEXT, tint } from "@/lib/tokens";
import { formatarTempo } from "@/components/library/VideoPlayer";
import { Icon, type IconName } from "@/components/ui/icons";

const ICON_BY_KIND: Record<string, IconName> = {
  video: "play",
  article: "article",
  course: "book",
  doc: "file",
  book: "book",
  podcast: "chat",
  repo: "code",
  exercise: "code",
};

/** Em curso lidera, salvo é marcador, concluído recua. */
function stateColor(state: ResourceState | null): string {
  if (state === "done") return "rgba(233,233,237,.4)";
  if (state === "in_progress") return ACC4;
  if (state === "saved") return C.azul;
  return TEXT.faint;
}

const STATE_LABEL: Record<string, string> = {
  saved: "salvo",
  in_progress: "em curso",
  done: "concluído",
  dismissed: "dispensado",
};

/** O próximo estado no ciclo do botão: novo → em curso → concluído → novo. */
function nextState(state: ResourceState | null): ResourceState {
  if (state === "in_progress") return "done";
  if (state === "done") return "saved";
  return "in_progress";
}

export function LibraryRow({
  resource,
  kindLabel,
  onProgress,
  onPosition,
  aberto = false,
  onAbrir,
}: {
  resource: Resource;
  kindLabel: string;
  onProgress: (next: ResourceState) => void;
  /** Grava onde a pessoa parou. Ver o campo abaixo do título. */
  onPosition: (nota: string) => void;
  /** O material está aberto no visualizador logo abaixo desta linha. */
  aberto?: boolean;
  /** Abre ou fecha o visualizador. Sem isto, a linha volta a ser um link
   * para fora — que é o que o produto deixou de querer. */
  onAbrir?: () => void;
}) {
  const chipColor = resource.kind === "video" ? ACC : resource.kind === "exercise" ? C.verde : C.azul;
  const emCurso = resource.user_status === "in_progress";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 11.2,
        padding: 12,
        borderRadius: 8,
        background: "#16161b",
        boxShadow: "0 0 0 1px #3f424d",
      }}
    >
      {/* 38 e não 30: o chip acompanha duas linhas de texto ao lado, e a
          versão pequena ficava perdida contra o título. */}
      <span
        title={kindLabel}
        style={{
          width: 38,
          height: 38,
          flex: "none",
          borderRadius: 9,
          display: "grid",
          placeItems: "center",
          background: tint(chipColor, 16),
          color: chipColor,
          // Acompanha o `padding` do título: assim o chip fica centrado na
          // primeira linha dele, e não no topo da caixa de texto.
          marginTop: 2,
        }}
      >
        <Icon name={ICON_BY_KIND[resource.kind] ?? "article"} size={20} />
      </span>

      {/* O ritmo vertical é o que fazia a linha parecer espremida: título e
          fonte encostados, e o progresso colado neles. Quatro pixels entre as
          linhas do mesmo assunto, seis antes do progresso, que é outro. */}
      <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
        <span style={{ display: "flex", alignItems: "flex-start", gap: 8.4 }}>
          {/* Botão, e não link: o material abre AQUI DENTRO, e o progresso sai
              do próprio consumo. O link para a fonte continua existindo, dentro
              do visualizador, onde a pessoa o vê ao ler. */}
          <button
            type="button"
            onClick={onAbrir}
            aria-expanded={aberto}
            style={{
              flex: 1,
              minWidth: 0,
              textAlign: "left",
              // Sem `minHeight` aqui. A tentativa de esticar o título até 44px
              // com margens negativas puxava a linha da fonte para cima dele e
              // era isso que deixava o cartão espremido. O alvo grande desta
              // linha é a própria altura do cartão; o título é um link dentro
              // dele, como um link dentro de um parágrafo.
              padding: "2px 0",
              border: "none",
              background: "transparent",
              font: "inherit",
              fontSize: SIZE.corpo,
              lineHeight: 1.3,
              color: aberto ? ACC4 : "inherit",
              cursor: "pointer",
            }}
          >
            {resource.title}
          </button>
          <BotaoDeEstado estado={resource.user_status} onProgress={onProgress} />
        </span>

        <span style={{ display: "block", fontSize: SIZE.rotulo, color: TEXT.faint }}>
          {[
            resource.provider ?? resource.author,
            resource.duration_min ? `${resource.duration_min} min` : null,
            resource.language === "pt" ? "português" : resource.language === "en" ? "inglês" : resource.language,
            kindLabel,
          ]
            .filter(Boolean)
            .join(" · ")}
        </span>

        {/* Progresso e "onde parei" na MESMA linha: são a mesma pergunta, e
            dois blocos separados dobravam a altura do cartão sem dizer nada a
            mais. */}
        {emCurso ? (
          <span
            style={{
              display: "flex",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 8.4,
              marginTop: 2,
            }}
          >
            {resource.user_progress_pct > 0 ? (
              <Progresso pct={resource.user_progress_pct} segundos={resource.user_position_seconds} />
            ) : null}
            <ParouEm id={resource.id} nota={resource.user_position_note} onSalvar={onPosition} />
          </span>
        ) : null}
      </span>
    </div>
  );
}

/**
 * O ciclo do estado, numa pílula.
 *
 * O botão tem 44px de altura e a pílula não. A área de toque precisa do piso
 * da diretriz da Apple; o desenho, não — uma pílula de 44px ao lado de um
 * título de 14px é o que fazia a linha inteira parecer desequilibrada. O
 * botão é transparente e alto; o que se vê é o `span` de dentro.
 */
function BotaoDeEstado({
  estado,
  onProgress,
}: {
  estado: ResourceState | null;
  onProgress: (next: ResourceState) => void;
}) {
  const cor = stateColor(estado);
  return (
    <button
      type="button"
      onClick={() => onProgress(nextState(estado))}
      title={estado ? `Marcar como ${STATE_LABEL[nextState(estado)]}` : "Marcar como em curso"}
      style={{
        flex: "none",
        display: "inline-flex",
        alignItems: "center",
        minHeight: 40,
        marginTop: -9,
        marginBottom: -9,
        padding: 0,
        border: 0,
        background: "none",
        cursor: "pointer",
        font: "inherit",
        fontSize: SIZE.apoio,
      }}
    >
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          padding: "3px 9px",
          borderRadius: 999,
          border: `1px solid ${estado ? cor : "rgba(233,233,237,.14)"}`,
          color: cor,
        }}
      >
        <Icon name={estado === "done" ? "check" : estado === "in_progress" ? "play" : "plus"} size={12} />
        {estado ? STATE_LABEL[estado] : "marcar"}
      </span>
    </button>
  );
}

/**
 * Onde a pessoa parou neste material.
 *
 * Só aparece com o item em curso: num material salvo ainda não há posição, e
 * num concluído a marca atrapalharia em vez de ajudar.
 *
 * Texto livre, e escrito à mão, porque o material abre em OUTRA aba — o app
 * não tem como observar o player do YouTube nem o scroll de um artigo de
 * terceiro. Um campo de segundos serviria só a vídeo, e metade da biblioteca
 * é artigo e PDF.
 */
function ParouEm({
  id,
  nota,
  onSalvar,
}: {
  /** O id do material. O `for` do rótulo precisa apontar para algo estável. */
  id: string;
  nota: string | null;
  onSalvar: (valor: string) => void;
}) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(nota ?? "");

  // A linha vem do servidor e pode mudar por fora (outro dispositivo, uma
  // recarga). Sem isto o campo ficaria preso ao primeiro valor visto.
  useEffect(() => setTexto(nota ?? ""), [nota]);

  function salvar() {
    setEditando(false);
    if ((nota ?? "") !== texto) onSalvar(texto);
  }

  if (!editando) {
    return (
      <button
        type="button"
        onClick={() => setEditando(true)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          padding: "3px 0",
          border: 0,
          background: "none",
          cursor: "pointer",
          font: "inherit",
          fontSize: SIZE.apoio,
          color: nota ? ACC4 : TEXT.faint,
          textDecoration: "underline",
          textDecorationStyle: nota ? "solid" : "dashed",
          textUnderlineOffset: 3,
        }}
      >
        <Icon name="pencil" size={12} />
        {nota ? `parei em ${nota}` : "marcar onde parei"}
      </button>
    );
  }

  return (
    <input
      id={`parei-${id}`}
      className="input"
      aria-label="Onde você parou neste material"
      autoFocus
      value={texto}
      placeholder="23:10, capítulo 4…"
      onChange={(event) => setTexto(event.target.value)}
      onBlur={salvar}
      onKeyDown={(event) => {
        if (event.key === "Enter") salvar();
        // Escape desiste: o campo se abre com um toque, e sair dele sem
        // gravar precisa ser tão barato quanto entrar.
        if (event.key === "Escape") {
          setTexto(nota ?? "");
          setEditando(false);
        }
      }}
      // Sem `fontSize` inline: um tamanho aqui venceria a regra de toque do
      // app.css, e um campo com menos de 16px faz o Safari do iPhone dar zoom
      // na página ao focar — zoom que não volta sozinho.
      style={{ padding: "2px 7px", maxWidth: 170, height: "auto" }}
    />
  );
}

/**
 * O quanto já foi consumido, na própria linha da lista.
 *
 * É o que responde "onde eu parei?" antes de abrir: uma lista de dezessete
 * materiais em que só se lê "em curso" não diz qual está quase no fim e qual
 * mal começou.
 */
function Progresso({ pct, segundos }: { pct: number; segundos: number | null }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5.6 }}>
      <span
        aria-hidden
        style={{
          width: 64,
          height: 3,
          borderRadius: 2,
          background: "rgba(233,233,237,.16)",
          overflow: "hidden",
        }}
      >
        <span style={{ display: "block", width: `${pct}%`, height: "100%", background: ACC }} />
      </span>
      <span style={{ fontSize: SIZE.rotulo, color: TEXT.faint }}>
        {pct}%{segundos ? ` · ${formatarTempo(segundos)}` : ""}
      </span>
    </span>
  );
}
