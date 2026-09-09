/**
 * O catálogo de competências.
 *
 * Duas coisas na mesma tela porque são a mesma decisão: o que está no plano
 * (a lista de cima, editável) e o que existe para adicionar (a busca).
 *
 * O nível é o campo honesto do produto — dizer "já sou N3 aqui" é o que
 * impede o roadmap de ensinar o que a pessoa já faz.
 */

import { useState } from "react";
import { tags as tagsApi } from "@/api/endpoints";
import type { Tag } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useQuery } from "@/hooks/useApi";
import { ACC, TEXT } from "@/lib/tokens";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";
import { MASTERY_LABELS } from "./TechnologyRow";

export function SkillsTab() {
  const { state, dispatch } = useAppState();
  const mine = useQuery(() => tagsApi.mine(), []);
  const term = state.skillSearch.trim();
  const catalog = useQuery(() => tagsApi.catalog(term), [term], { enabled: term.length >= 2 });
  const [busy, setBusy] = useState<string | null>(null);

  if (mine.loading) return <Loading />;
  if (mine.error) return <ErrorState message={mine.error} onRetry={mine.reload} />;

  const owned = new Set((mine.data ?? []).map((tag) => tag.tag_id));

  async function setLevel(userTagId: string, level: number) {
    mine.set((current) =>
      current.map((tag) => (tag.id === userTagId ? { ...tag, proficiency: level } : tag)),
    );
    await tagsApi.update(userTagId, { proficiency: level });
  }

  async function add(tag: Tag) {
    setBusy(tag.id);
    await tagsApi.add({ tag_id: tag.id, proficiency: 0, is_target: true });
    setBusy(null);
    mine.reload();
  }

  async function remove(userTagId: string) {
    mine.set((current) => current.filter((tag) => tag.id !== userTagId));
    await tagsApi.remove(userTagId);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <Panel pad={16.8}>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 11.2,
            marginBottom: 5.6,
          }}
        >
          <Kicker>Skills do plano</Kicker>
          <span style={{ marginLeft: "auto", fontSize: 11.5, color: TEXT.faint }}>
            {(mine.data ?? []).length} no perfil
          </span>
        </div>
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "70ch" }}>
          Esta é a origem das tags do perfil. Ajuste o nível que você já tem — o plano cobre o
          caminho de onde você está até N3.
        </p>
        <div className="field">
          <label htmlFor="skill-search">Buscar tecnologia para adicionar</label>
          <input
            id="skill-search"
            className="input"
            type="search"
            placeholder="ex: Kafka, Terraform"
            value={state.skillSearch}
            onChange={(event) => dispatch({ type: "setSkillSearch", value: event.target.value })}
          />
        </div>

        {term.length >= 2 ? (
          <div style={{ marginTop: 11.2, display: "flex", flexWrap: "wrap", gap: 5.6 }}>
            {catalog.loading ? (
              <span style={{ fontSize: 12, color: TEXT.faint }}>Buscando…</span>
            ) : null}
            {(catalog.data ?? [])
              .filter((tag) => !owned.has(tag.id))
              .slice(0, 12)
              .map((tag) => (
                <button
                  key={tag.id}
                  type="button"
                  disabled={busy === tag.id}
                  onClick={() => void add(tag)}
                  style={{
                    padding: "5px 10px",
                    borderRadius: 6,
                    font: "inherit",
                    fontSize: 12.5,
                    cursor: "pointer",
                    border: "1px dashed rgba(233,233,237,.22)",
                    background: "transparent",
                    color: TEXT.muted,
                  }}
                >
                  + {tag.name}
                </button>
              ))}
            {catalog.data && catalog.data.filter((tag) => !owned.has(tag.id)).length === 0 ? (
              <span style={{ fontSize: 12, color: TEXT.faint }}>
                Nada novo com esse termo — ou você já tem todas.
              </span>
            ) : null}
          </div>
        ) : null}
      </Panel>

      <Panel pad={16.8}>
        <Kicker style={{ display: "block", marginBottom: 11.2 }}>Suas competências</Kicker>
        <div style={{ display: "flex", flexDirection: "column", gap: 5.6 }}>
          {(mine.data ?? []).map((tag) => (
            <div
              key={tag.id}
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: 11.2,
                padding: "8.4px 11.2px",
                borderRadius: 8,
                background: "#1b1d2b",
                boxShadow: "0 0 0 1px rgba(233,233,237,.08)",
              }}
            >
              <span style={{ flex: 1, minWidth: 140, fontSize: 13.5 }}>
                {tag.name}
                <span style={{ display: "block", fontSize: 11, color: TEXT.faint }}>
                  {tag.category}
                </span>
              </span>

              <span role="group" aria-label={`Nível de ${tag.name}`} style={{ display: "flex", gap: 3 }}>
                {MASTERY_LABELS.map((label, level) => {
                  const picked = tag.proficiency === level;
                  return (
                    <button
                      key={label}
                      type="button"
                      aria-pressed={picked}
                      title={`N${level} · ${label}`}
                      onClick={() => void setLevel(tag.id, level)}
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

              <button
                type="button"
                className="btn btn-ghost"
                style={{ fontSize: 11.5 }}
                onClick={() => void remove(tag.id)}
              >
                Remover
              </button>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
