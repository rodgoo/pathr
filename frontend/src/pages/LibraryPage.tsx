/**
 * Biblioteca: material curado a partir das tags do usuário.
 *
 * O filtro por tags é o padrão e é o que faz a lista parecer pessoal sem o
 * catálogo ser duplicado por pessoa. "Ver tudo" abre o catálogo inteiro, para
 * procurar algo que ainda não está no plano.
 */

import { useState } from "react";
import { library as libraryApi } from "@/api/endpoints";
import { KIND_LABEL, LIBRARY_FILTERS } from "@/api/library-filters";
import { useAppState } from "@/hooks/useAppState";
import { useQuery } from "@/hooks/useApi";
import { TEXT } from "@/lib/tokens";
import type { ContentLang } from "@/types";
import { Chip } from "@/components/ui/Chip";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { SCREEN_IN } from "@/components/ui/primitives";
import { CurateButton } from "@/components/library/CurateButton";
import { LibraryRow } from "@/components/library/LibraryRow";
import { ResourceViewer } from "@/components/library/ResourceViewer";

const LANGS: readonly { value: ContentLang; label: string }[] = [
  { value: "pt", label: "Português" },
  { value: "en", label: "Inglês" },
  { value: "both", label: "Ambos" },
];

export function LibraryPage() {
  // Qual material esta aberto no visualizador. Um por vez: dois videos
  // tocando juntos e ruido, e a tela perde o foco do que se esta estudando.
  const [aberto, setAberto] = useState<string | null>(null);
  const { state, dispatch } = useAppState();
  const resources = useQuery(
    () =>
      libraryApi.list({
        q: state.librarySearch.trim() || undefined,
        kind: state.libraryFilter === "todos" ? undefined : state.libraryFilter,
        language: state.contentLang === "both" ? undefined : state.contentLang,
        only_mine: true,
      }),
    [state.librarySearch, state.libraryFilter, state.contentLang],
  );

  // Há um filtro estreitando a lista? O idioma entra na conta: quem deixou em
  // "Português" e não vê nada pode ter material em inglês esperando, e mandar
  // buscar de novo não resolveria isso.
  const filtrando =
    Boolean(state.librarySearch.trim()) ||
    state.libraryFilter !== "todos" ||
    state.contentLang !== "both";

  return (
    <div style={SCREEN_IN}>
      <header
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-end",
          gap: 16.8,
          marginBottom: 5.6,
        }}
      >
        <div style={{ flex: 1, minWidth: 240 }}>
          <div style={{ fontSize: 12.5, color: TEXT.muted }}>Curadoria ligada às suas tags</div>
          <h1 style={{ fontSize: 28, margin: 0 }}>Biblioteca</h1>
        </div>
        <span style={{ display: "flex", alignItems: "center", gap: 8.4 }}>
          <span style={{ fontSize: 11, color: TEXT.faint }}>idioma</span>
          <Segmented
            name="library-lang"
            label="Idioma do material"
            value={state.contentLang}
            options={LANGS}
            onChange={(lang) => dispatch({ type: "setContentLang", lang })}
          />
        </span>
      </header>

      <p style={{ margin: "0 0 16.8px", fontSize: 12.5, color: TEXT.faint }}>
        {resources.data
          ? `${resources.data.length} ${resources.data.length === 1 ? "material" : "materiais"} para as tecnologias do seu plano`
          : "Carregando a curadoria…"}
      </p>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 11.2,
          alignItems: "flex-end",
          marginBottom: 14,
        }}
      >
        <div className="field" style={{ flex: 1, minWidth: 220 }}>
          <label htmlFor="library-search">Buscar na biblioteca</label>
          <input
            id="library-search"
            className="input"
            type="search"
            placeholder="Buscar por título ou fonte"
            value={state.librarySearch}
            onChange={(event) => dispatch({ type: "setLibrarySearch", value: event.target.value })}
          />
        </div>
        <div
          role="group"
          aria-label="Filtrar por tipo"
          style={{ display: "flex", flexWrap: "wrap", gap: 5.6 }}
        >
          {LIBRARY_FILTERS.map((filter) => (
            <Chip
              key={filter.key}
              active={state.libraryFilter === filter.key}
              onClick={() => dispatch({ type: "setLibraryFilter", filter: filter.key })}
            >
              {filter.label}
            </Chip>
          ))}
        </div>
      </div>

      {resources.loading ? <Loading label="Buscando material…" /> : null}
      {resources.error ? (
        <ErrorState message={resources.error} onRetry={resources.reload} />
      ) : null}

      {resources.data && resources.data.length === 0 ? (
        <EmptyState
          title="Nada encontrado"
          description={
            filtrando
              ? "Tente outro termo ou tire os filtros."
              : "A busca cobre as suas tags: vídeo no YouTube, artigo num buscador e documentação oficial."
          }
          // Só oferece a busca quando a lista está vazia de verdade. Com um
          // filtro ligado, o catálogo pode estar cheio e a tela vazia — aí o
          // botão gastaria cota para "consertar" algo que se resolve tirando
          // o filtro.
          action={filtrando ? undefined : <CurateButton onFound={resources.reload} />}
        />
      ) : null}

      {resources.data && resources.data.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
          {resources.data.map((resource) => (
            <div key={resource.id}>
            <LibraryRow
              resource={resource}
              aberto={aberto === resource.id}
              onAbrir={() => setAberto((atual) => (atual === resource.id ? null : resource.id))}
              kindLabel={KIND_LABEL[resource.kind] ?? resource.kind}
              onProgress={async (next) => {
                resources.set((current) =>
                  current.map((item) =>
                    item.id === resource.id ? { ...item, user_status: next } : item,
                  ),
                );
                await libraryApi.setProgress(resource.id, {
                  status: next,
                  minutes_spent: next === "done" ? resource.duration_min ?? 0 : 0,
                });
              }}
              onPosition={async (nota) => {
                resources.set((current) =>
                  current.map((item) =>
                    item.id === resource.id ? { ...item, user_position_note: nota } : item,
                  ),
                );
                // O status vai junto porque a rota o exige, e ele NÃO muda
                // aqui: anotar onde parou não conclui nem reabre nada.
                await libraryApi.setProgress(resource.id, {
                  status: resource.user_status ?? "in_progress",
                  position_note: nota,
                });
              }}
            />
              {aberto === resource.id ? (
                <ResourceViewer
                  resource={resource}
                  onFechar={() => setAberto(null)}
                  onProgresso={(mudanca) =>
                    resources.set((current) =>
                      current.map((item) =>
                        item.id === resource.id
                          ? {
                              ...item,
                              user_status: mudanca.status,
                              user_progress_pct: mudanca.progress_pct,
                              user_position_seconds: mudanca.position_seconds,
                            }
                          : item,
                      ),
                    )
                  }
                />
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
