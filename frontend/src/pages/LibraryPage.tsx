/**
 * Biblioteca: material curado a partir das tags do usuário.
 *
 * O filtro por tags é o padrão e é o que faz a lista parecer pessoal sem o
 * catálogo ser duplicado por pessoa. "Ver tudo" abre o catálogo inteiro, para
 * procurar algo que ainda não está no plano.
 */

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
import { LibraryRow } from "@/components/library/LibraryRow";

const LANGS: readonly { value: ContentLang; label: string }[] = [
  { value: "pt", label: "Português" },
  { value: "en", label: "Inglês" },
  { value: "both", label: "Ambos" },
];

export function LibraryPage() {
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
            state.librarySearch || state.libraryFilter !== "todos"
              ? "Tente outro termo ou tire os filtros."
              : "A curadoria segue as suas tags. Adicione competências ao plano para o material aparecer aqui."
          }
        />
      ) : null}

      {resources.data && resources.data.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
          {resources.data.map((resource) => (
            <LibraryRow
              key={resource.id}
              resource={resource}
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
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
