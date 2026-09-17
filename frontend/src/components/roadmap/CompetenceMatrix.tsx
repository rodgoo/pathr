/**
 * O roadmap como matriz de competência.
 *
 * Célula preenchida é domínio já registrado no perfil; a de contorno é o
 * próximo nível que o plano alcança. Ler uma linha da esquerda para a direita
 * responde "até onde este plano me leva neste assunto?", que nem a linha do
 * tempo nem as colunas mostram.
 */

import { TEXT } from "@/lib/tokens";
import { useT } from "@/lib/i18n";
import type { Roadmap, UserTag } from "@/api/types";
import { Panel } from "@/components/ui/primitives";
import { MASTERY_KEYS } from "@/components/profile/TechnologyRow";

/** As colunas: N1 a N4. N0 é o piso implícito e não ganha coluna. */
const LEVELS = [1, 2, 3, 4] as const;

export function CompetenceMatrix({
  roadmap,
  tags,
}: {
  roadmap: Roadmap;
  tags: UserTag[];
}) {
  const t = useT();
  // Só as tags que o plano realmente toca — a matriz responde sobre ESTE
  // plano, e listar competências que ele não cobre diluiria a resposta.
  const covered = new Set(
    roadmap.phases.flatMap((phase) => phase.modules.flatMap((module) => module.tag_ids)),
  );
  const rows = tags
    .filter((tag) => covered.has(tag.tag_id))
    .sort((a, b) => b.proficiency - a.proficiency || a.name.localeCompare(b.name));

  if (rows.length === 0) {
    return (
      <Panel>
        <p style={{ margin: 0, fontSize: 13.5, color: TEXT.muted }}>
          {t("roadmap.matriz.vazio")}
        </p>
      </Panel>
    );
  }

  return (
    <Panel style={{ overflowX: "auto" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(140px,1fr) repeat(4,minmax(74px,1fr))",
          gap: 8.4,
          alignItems: "center",
          minWidth: 520,
        }}
      >
        <div />
        {LEVELS.map((level) => (
          <div
            key={level}
            style={{
              fontSize: 10,
              letterSpacing: ".08em",
              textTransform: "uppercase",
              color: TEXT.faint,
              textAlign: "center",
            }}
          >
            N{level} {t(MASTERY_KEYS[level])}
          </div>
        ))}

        {rows.map((tag) => (
          <div key={tag.id} style={{ display: "contents" }}>
            <div style={{ fontSize: 13.5, padding: "6px 0" }}>{tag.name}</div>
            {LEVELS.map((level) => {
              const attained = level <= tag.proficiency;
              const next = level === tag.proficiency + 1;
              return (
                <div
                  key={level}
                  title={t("roadmap.matriz.celula", {
                    nome: tag.name,
                    nivel: level,
                    estado: attained
                      ? t("roadmap.matriz.estado.atingido")
                      : next
                        ? t("roadmap.matriz.estado.proximo")
                        : t("roadmap.matriz.estado.alem"),
                  })}
                  style={{
                    height: 24,
                    borderRadius: 5,
                    background: attained
                      ? "rgba(145,132,217,.5)"
                      : next
                        ? "rgba(145,132,217,.12)"
                        : "rgba(233,233,237,.05)",
                    boxShadow: next ? "inset 0 0 0 1px rgba(145,132,217,.6)" : "none",
                  }}
                />
              );
            })}
          </div>
        ))}
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 14,
          marginTop: 16.8,
          fontSize: 11.5,
          color: TEXT.faint,
        }}
      >
        <span>{t("roadmap.matriz.legendaPreenchido")}</span>
        <span>{t("roadmap.matriz.legendaContorno")}</span>
      </div>
    </Panel>
  );
}
