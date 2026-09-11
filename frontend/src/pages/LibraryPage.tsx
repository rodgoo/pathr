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
import { CurateButton } from "@/components/library/CurateButton";
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

  // Com "Português" e nada encontrado, quanto existe nos outros idiomas. É o
  // que deixa a tela dizer "há 3 em inglês" em vez de "nada encontrado" —
  // documentação e exercício quase sempre só existem em inglês, e esconder
  // isso fazia parecer que a busca não tinha achado nada.
  const vazio = resources.data !== null && resources.data.length === 0;
  const alternativas = useQuery(
    () =>
      libraryApi.list({
        q: state.librarySearch.trim() || undefined,
        kind: state.libraryFilter === "todos" ? undefined : state.libraryFilter,
        only_mine: true,
      }),
    [state.librarySearch, state.libraryFilter],
    { enabled: vazio && state.contentLang === "pt" },
  );
  const emOutroIdioma = vazio
    ? (alternativas.data ?? []).filter((item) => item.language !== "pt").length
    : 0;
  const nomeDoFiltro =
    state.libraryFilter === "todos"
      ? "material"
      : (LIBRARY_FILTERS.find((f) => f.key === state.libraryFilter)?.label ?? "material").toLowerCase();

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
        {/* Sempre à mão. Ficava só na lista vazia e sem filtro, e como o
            idioma contava como filtro, quem usava "Português" nunca o via. */}
        <CurateButton onFound={resources.reload} />
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
              icon={filter.icon}
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
            emOutroIdioma > 0
              ? `Não há ${nomeDoFiltro} em português para as suas tecnologias — há ${emOutroIdioma} em inglês.`
              : state.librarySearch.trim()
                ? "Tente outro termo."
                : "A busca procura vídeo no YouTube, artigo, documentação e exercício para as suas tecnologias."
          }
          action={
            emOutroIdioma > 0 ? (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => dispatch({ type: "setContentLang", lang: "both" })}
              >
                Mostrar também em inglês
              </button>
            ) : (
              <CurateButton onFound={resources.reload} />
            )
          }
        />
      ) : null}

      {resources.data && resources.data.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
          {resources.data.map((resource) => (
            <LibraryRow
              key={resource.id}
              resource={resource}
              onAbrir={() => dispatch({ type: "openResource", resourceId: resource.id })}
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
          ))}
        </div>
      ) : null}
    </div>
  );
}
