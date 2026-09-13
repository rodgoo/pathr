/**
 * O material do módulo — e o acervo inteiro, quando se procura.
 *
 * Esta aba ABSORVEU a Biblioteca, que era uma tela própria no menu. As duas
 * mostravam a mesma lista com recortes diferentes, e ter dois lugares para o
 * mesmo material é como um app passa a ter dois lugares onde marcar
 * "concluído" e só um deles contar. Agora há um: o material vive dentro do
 * módulo a que serve.
 *
 * O que a Biblioteca fazia e não podia se perder veio junto: a busca, o filtro
 * por tipo e a escolha de idioma. A diferença é o ESCOPO. Sem termo de busca,
 * a lista é a do módulo aberto — que é a pergunta de quem está estudando
 * agora. Com termo, a busca atravessa todo o material do seu plano, porque
 * quem procura "kafka" não quer saber em qual módulo aquilo ficou guardado.
 */

import { library as libraryApi } from "@/api/endpoints";
import { KIND_LABEL, LIBRARY_FILTERS } from "@/api/library-filters";
import type { Resource, RoadmapNode } from "@/api/types";
import { useEffect, useState } from "react";
import { useAppState } from "@/hooks/useAppState";
import { useQuery, type Query } from "@/hooks/useApi";
import { curarModulo } from "@/lib/curadoria";
import { C, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import type { ContentLang } from "@/types";
import { Chip } from "@/components/ui/Chip";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { CurateButton } from "@/components/library/CurateButton";
import { LibraryRow } from "@/components/library/LibraryRow";

const LANGS: readonly { value: ContentLang; label: string }[] = [
  { value: "pt", label: "Português" },
  { value: "en", label: "Inglês" },
  { value: "both", label: "Ambos" },
];

export function MaterialTab({ node }: { node: RoadmapNode }) {
  const { state, dispatch } = useAppState();
  const [curando, setCurando] = useState(false);

  const termo = state.librarySearch.trim();
  const filtro = state.libraryFilter;
  // Procurar é atravessar o acervo; sem termo, o assunto é o módulo aberto.
  const acervo = termo.length > 0 || filtro !== "todos";

  const resources = useQuery(
    () =>
      libraryApi.list({
        q: termo || undefined,
        kind: filtro === "todos" ? undefined : filtro,
        language: state.contentLang === "both" ? undefined : state.contentLang,
        only_mine: true,
      }),
    [termo, filtro, state.contentLang],
  );

  // O filtro por tag acontece no cliente porque a lista já veio filtrada pelo
  // perfil e é pequena — pedir ao servidor de novo, por tag, seria uma
  // requisição a mais para cortar dez linhas.
  const wanted = new Set(node.tag_ids);
  const matching = acervo
    ? resources.data ?? []
    : (resources.data ?? []).filter((resource) =>
        resource.tag_ids.some((tag) => wanted.has(tag)),
      );
  // Só o módulo VAZIO procura sozinho. Uma busca que não achou nada é
  // resposta, não lacuna — sair curando por causa dela gastaria uma rodada de
  // requisições a cada palavra digitada.
  const vazio = !acervo && !resources.loading && !resources.error && matching.length === 0;

  // Com "Português" e nada encontrado, quanto existe nos outros idiomas. É
  // o que deixa a tela dizer "há 3 em inglês" em vez de "nada encontrado" —
  // documentação e exercício quase sempre só existem em inglês, e esconder
  // isso fazia parecer que a busca não tinha achado nada.
  const semNada = resources.data !== null && matching.length === 0;
  const alternativas = useQuery(
    () =>
      libraryApi.list({
        q: termo || undefined,
        kind: filtro === "todos" ? undefined : filtro,
        only_mine: true,
      }),
    [termo, filtro],
    { enabled: semNada && state.contentLang === "pt" },
  );
  const emOutroIdioma = semNada
    ? (alternativas.data ?? []).filter((item) => item.language !== "pt").length
    : 0;

  // Módulo sem material procura sozinho, uma vez. O botão manual continua
  // logo abaixo para quando a busca automática não trouxer nada — ele é o
  // caminho de quem quer insistir, e o único que mostra o motivo.
  useEffect(() => {
    if (!vazio) return undefined;
    let vivo = true;
    setCurando(true);
    void curarModulo(node.id).then((achou) => {
      if (!vivo) return;
      setCurando(false);
      if (achou) resources.reload();
    });
    return () => {
      vivo = false;
    };
    // `resources.reload` é estável (useCallback sem dependências).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vazio, node.id]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 11.2, alignItems: "flex-end" }}>
        <div className="field" style={{ flex: 1, minWidth: 220, margin: 0 }}>
          <label htmlFor="material-search">Buscar material</label>
          <input
            id="material-search"
            className="input"
            type="search"
            placeholder="Buscar em todo o seu material"
            value={state.librarySearch}
            onChange={(event) => dispatch({ type: "setLibrarySearch", value: event.target.value })}
          />
        </div>
        {/* Sempre à mão, e não só na lista vazia: o idioma contava como
            filtro, e quem usava "Português" nunca via o botão. */}
        <CurateButton nodeId={node.id} onFound={resources.reload} />
        <span style={{ display: "flex", alignItems: "center", gap: 8.4 }}>
          <span style={{ fontSize: 11, color: TEXT.faint }}>idioma</span>
          <Segmented
            name="material-lang"
            label="Idioma do material"
            value={state.contentLang}
            options={LANGS}
            onChange={(lang) => dispatch({ type: "setContentLang", lang })}
          />
        </span>
      </div>

      <div
        role="group"
        aria-label="Filtrar por tipo"
        style={{ display: "flex", flexWrap: "wrap", gap: 5.6 }}
      >
        {LIBRARY_FILTERS.map((item) => (
          <Chip
            key={item.key}
            icon={item.icon}
            active={filtro === item.key}
            onClick={() => dispatch({ type: "setLibraryFilter", filter: item.key })}
          >
            {item.label}
          </Chip>
        ))}
      </div>

      <Lista
        node={node}
        acervo={acervo}
        curando={curando}
        matching={matching}
        resources={resources}
        emOutroIdioma={emOutroIdioma}
        onMostrarIngles={() => dispatch({ type: "setContentLang", lang: "both" })}
        onAbrir={(id) => dispatch({ type: "openResource", resourceId: id })}
      />
    </div>
  );
}

/**
 * A lista e os estados dela.
 *
 * Separada porque a moldura de busca precisa ficar DE PÉ enquanto a lista
 * carrega, dá erro ou vem vazia. Se o estado substituísse a tela inteira, quem
 * digitasse um termo que não acha nada perderia o campo de busca junto com o
 * resultado — sem como corrigir o que acabou de escrever.
 */
function Lista({
  node,
  acervo,
  curando,
  matching,
  resources,
  emOutroIdioma,
  onMostrarIngles,
  onAbrir,
}: {
  node: RoadmapNode;
  /** A lista é o acervo inteiro (há busca) ou só a deste módulo? */
  acervo: boolean;
  curando: boolean;
  matching: Resource[];
  resources: Query<Resource[]>;
  /** Quantos existem fora do português, quando em português não há nenhum. */
  emOutroIdioma: number;
  onMostrarIngles: () => void;
  onAbrir: (id: string) => void;
}) {
  if (resources.loading) return <Loading label="Buscando material…" />;
  if (resources.error) {
    return <ErrorState message={resources.error} onRetry={resources.reload} />;
  }
  if (curando) return <Loading label="Procurando material para este módulo…" />;

  if (matching.length === 0) {
    // Documentação e exercício quase sempre só existem em inglês. Dizer
    // "nada encontrado" para quem filtrou por português esconde justamente o
    // material que existe, e faz a busca parecer quebrada.
    if (emOutroIdioma > 0) {
      return (
        <EmptyState
          title="Nada em português"
          description={`Não há material em português para este recorte — há ${emOutroIdioma} em inglês.`}
          action={
            <button type="button" className="btn btn-secondary" onClick={onMostrarIngles}>
              Mostrar também em inglês
            </button>
          }
        />
      );
    }
    return acervo ? (
      <EmptyState
        title="Nada encontrado"
        description="Nenhum material do seu plano casa com esse termo. Limpe a busca para voltar ao material deste módulo."
      />
    ) : (
      <EmptyState
        title="Sem material para este módulo ainda"
        description="Já procurei nas tecnologias deste módulo e não achei nada que passasse na verificação. Tentar de novo mais tarde costuma trazer resultado."
        action={<CurateButton nodeId={node.id} onFound={resources.reload} />}
      />
    );
  }

  const linha = (resource: Resource) => (
    <LibraryRow
      key={resource.id}
      resource={resource}
      onAbrir={() => onAbrir(resource.id)}
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
        // O status vai junto porque a rota o exige, e ele NÃO muda aqui:
        // anotar onde parou não conclui nem reabre nada.
        await libraryApi.setProgress(resource.id, {
          status: resource.user_status ?? "in_progress",
          position_note: nota,
        });
      }}
    />
  );

  // O que já foi concluído desce para uma seção própria: misturado à lista,
  // o material que falta ficava entre itens já vistos e a pessoa tinha de
  // ler cada etiqueta para achar o próximo.
  const pendentes = matching.filter((item) => item.user_status !== "done");
  const concluidos = matching.filter((item) => item.user_status === "done");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
      <p style={{ fontSize: 11.5, color: TEXT.faint, margin: 0 }}>
        {matching.length} {matching.length === 1 ? "material" : "materiais"}{" "}
        {acervo ? "em todo o seu plano." : "para as tecnologias deste módulo."}
        {concluidos.length > 0 ? ` ${concluidos.length} ${concluidos.length === 1 ? "concluído" : "concluídos"}.` : ""}
      </p>
      {pendentes.map(linha)}
      {pendentes.length === 0 ? (
        <p style={{ fontSize: 12.5, color: C.verde, margin: "2px 0", display: "flex", alignItems: "center", gap: 6 }}>
          <Icon name="check" size={14} /> Tudo deste recorte já foi concluído.
        </p>
      ) : null}
      {concluidos.length > 0 ? (
        <section aria-label="Concluídos" style={{ display: "flex", flexDirection: "column", gap: 8.4, marginTop: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 11.5, letterSpacing: ".12em", textTransform: "uppercase", color: C.verde, fontWeight: 600 }}>
            <Icon name="check" size={13} />
            Concluído · {concluidos.length}
            <span aria-hidden style={{ flex: 1, height: 1, background: "rgba(99,180,143,.25)", marginLeft: 4 }} />
          </div>
          {concluidos.map(linha)}
        </section>
      ) : null}
    </div>
  );
}
