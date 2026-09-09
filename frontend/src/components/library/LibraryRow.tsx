/**
 * Uma linha da biblioteca.
 *
 * O título abre a fonte original numa aba nova — o app cura e acompanha, não
 * re-hospeda o conteúdo de ninguém. O botão de estado fica à parte para
 * marcar "concluído" não depender de sair da página.
 */

import { useEffect, useState } from "react";
import type { Resource, ResourceState } from "@/api/types";
import { ACC, ACC4, C, TEXT, tint } from "@/lib/tokens";
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
}: {
  resource: Resource;
  kindLabel: string;
  onProgress: (next: ResourceState) => void;
  /** Grava onde a pessoa parou. Ver o campo abaixo do título. */
  onPosition: (nota: string) => void;
}) {
  const chipColor = resource.kind === "video" ? ACC : resource.kind === "exercise" ? C.verde : C.azul;

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: 11.2,
        padding: "11.2px 14px",
        borderRadius: 8,
        background: "#232532",
        boxShadow: "0 0 0 1px #3f424d",
      }}
    >
      <span
        title={kindLabel}
        style={{
          width: 30,
          height: 30,
          flex: "none",
          borderRadius: 7,
          display: "grid",
          placeItems: "center",
          background: tint(chipColor, 16),
          color: chipColor,
        }}
      >
        <Icon name={ICON_BY_KIND[resource.kind] ?? "article"} />
      </span>

      <span style={{ flex: 1, minWidth: 180 }}>
        <a
          href={resource.url}
          target="_blank"
          rel="noreferrer noopener"
          style={{ display: "block", fontSize: 14, color: "inherit", textDecoration: "none" }}
        >
          {resource.title}
        </a>
        <span style={{ display: "block", fontSize: 11.5, color: TEXT.faint }}>
          {[
            resource.provider ?? resource.author,
            resource.duration_min ? `${resource.duration_min} min` : null,
            resource.language === "pt" ? "português" : resource.language === "en" ? "inglês" : resource.language,
            kindLabel,
          ]
            .filter(Boolean)
            .join(" · ")}
        </span>
        {resource.user_status === "in_progress" ? (
          <ParouEm nota={resource.user_position_note} onSalvar={onPosition} />
        ) : null}
      </span>

      <button
        type="button"
        onClick={() => onProgress(nextState(resource.user_status))}
        style={{
          fontSize: 11,
          padding: "4px 10px",
          borderRadius: 6,
          border: `1px solid ${resource.user_status ? stateColor(resource.user_status) : "rgba(233,233,237,.14)"}`,
          background: "transparent",
          color: stateColor(resource.user_status),
          cursor: "pointer",
          font: "inherit",
          minWidth: 96,
        }}
      >
        {resource.user_status ? STATE_LABEL[resource.user_status] : "marcar"}
      </button>
    </div>
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
  nota,
  onSalvar,
}: {
  nota: string | null;
  onSalvar: (valor: string) => void;
}) {
  const [texto, setTexto] = useState(nota ?? "");

  // A linha vem do servidor e pode mudar por fora (outro dispositivo, uma
  // recarga). Sem isto o campo ficaria preso ao primeiro valor visto.
  useEffect(() => setTexto(nota ?? ""), [nota]);

  return (
    <span style={{ display: "flex", alignItems: "center", gap: 5.6, marginTop: 5.6 }}>
      <label htmlFor={`parei-${nota ?? ""}`} style={{ fontSize: 11, color: TEXT.faint }}>
        parei em
      </label>
      <input
        className="input"
        value={texto}
        placeholder="23:10, capítulo 4…"
        onChange={(event) => setTexto(event.target.value)}
        onBlur={() => {
          if ((nota ?? "") !== texto) onSalvar(texto);
        }}
        style={{ fontSize: 11.5, padding: "2px 7px", width: 150, height: "auto" }}
      />
    </span>
  );
}