/**
 * Uma tecnologia lida do currículo, com o nível ajustável.
 *
 * Mostra a EVIDÊNCIA — a frase do currículo que sustentou a estimativa —
 * porque é ela que permite julgar a nota. Sem a frase, um "nível 4 em Java" é
 * indistinguível entre três anos liderando e uma linha numa lista de
 * palavras-chave.
 */

import type { ParsedTechnology } from "@/api/types";
import { useT } from "@/lib/i18n";
import { ACC, C, TEXT } from "@/lib/tokens";

/** A escala N0..N5, na ordem do índice. Espelha o prompt do backend. */
export const MASTERY_LABELS = [
  "quer aprender",
  "contato inicial",
  "com apoio",
  "autônomo",
  "referência",
  "especialista",
] as const;

/** As mesmas etiquetas como chaves de tradução, na ordem N0..N5. Quem mostra o
 * rótulo na tela usa `t(MASTERY_KEYS[nivel])`; `MASTERY_LABELS` fica para quem
 * ainda lê o texto cru. */
export const MASTERY_KEYS = [
  "perfil.niveis.querAprender",
  "perfil.niveis.contatoInicial",
  "perfil.niveis.comApoio",
  "perfil.niveis.autonomo",
  "perfil.niveis.referencia",
  "perfil.niveis.especialista",
] as const;

export function TechnologyRow({
  technology,
  dropped,
  onLevel,
  onToggle,
}: {
  technology: ParsedTechnology;
  dropped: boolean;
  onLevel: (level: number) => void;
  onToggle: () => void;
}) {
  const t = useT();
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: 11.2,
        padding: "8.4px 11.2px",
        borderRadius: 8,
        background: dropped ? "transparent" : "rgba(145,132,217,.07)",
        boxShadow: `0 0 0 1px ${dropped ? "rgba(233,233,237,.08)" : "rgba(145,132,217,.28)"}`,
        opacity: dropped ? 0.55 : 1,
      }}
    >
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: 9,
          flex: 1,
          minWidth: 160,
          cursor: "pointer",
          fontSize: 13.5,
        }}
      >
        <input
          type="checkbox"
          checked={!dropped}
          onChange={onToggle}
          style={{ accentColor: ACC }}
        />
        <span>
          <span style={{ display: "block" }}>{technology.nome}</span>
          {technology.evidencia ? (
            <span
              style={{
                display: "block",
                fontSize: 11,
                color: TEXT.faint,
                fontStyle: "italic",
                marginTop: 2,
              }}
            >
              “{technology.evidencia}”
            </span>
          ) : (
            <span style={{ display: "block", fontSize: 11, color: TEXT.faint, marginTop: 2 }}>
              {t("curriculo.revisao.semFrase")}
            </span>
          )}
        </span>
      </label>

      <span
        role="group"
        aria-label={t("curriculo.revisao.nivelDe", { nome: technology.nome })}
        style={{ display: "flex", gap: 3 }}
      >
        {MASTERY_KEYS.map((chave, level) => {
          const picked = !dropped && technology.proficiencia === level;
          return (
            <button
              key={chave}
              type="button"
              aria-pressed={picked}
              title={`N${level} · ${t(chave)}`}
              onClick={() => onLevel(level)}
              style={{
                width: 28,
                padding: "3px 0",
                borderRadius: 5,
                font: "inherit",
                fontSize: 10.5,
                fontFamily: "ui-monospace, Menlo, monospace",
                cursor: "pointer",
                border: `1px solid ${picked ? ACC : "rgba(233,233,237,.12)"}`,
                background: picked ? "rgba(145,132,217,.18)" : "transparent",
                color: picked ? "#e7e5fe" : "rgba(233,233,237,.38)",
              }}
            >
              N{level}
            </button>
          );
        })}
      </span>

      <span
        style={{
          fontSize: 11,
          color: technology.proficiencia === 0 ? C.verde : TEXT.faint,
          minWidth: 96,
          textAlign: "right",
        }}
      >
        {dropped ? t("curriculo.revisao.foraDoPlano") : t(MASTERY_KEYS[technology.proficiencia])}
      </span>
    </div>
  );
}
