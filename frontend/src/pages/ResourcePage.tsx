/**
 * Um material aberto — a tela dele, não uma caixa dentro da lista.
 *
 * Antes o vídeo e o artigo abriam expandindo a própria linha da biblioteca:
 * uma moldura dentro de outra, dentro do painel, dentro da moldura do app. No
 * celular sobravam uns 300px de largura para um player, e o texto de um
 * artigo ficava numa coluna de leitura impossível.
 *
 * Aqui o conteúdo é o assunto da tela e recebe a largura toda. O que fica em
 * volta é o mínimo que a pessoa precisa enquanto consome: de onde voltar, o
 * que está consumindo, e quanto já andou.
 *
 * O progresso no topo não é enfeite. Ele sai do próprio consumo — o player e
 * o leitor informam a posição, `ResourceViewer` decide o que gravar — e é a
 * resposta para "de onde eu retomo?" sem precisar rolar até o fim.
 */

import { useEffect, useState } from "react";
import { library as libraryApi } from "@/api/endpoints";
import type { Resource } from "@/api/types";
import { KIND_LABEL } from "@/api/library-filters";
import { useAppState } from "@/hooks/useAppState";
import { useQuery } from "@/hooks/useApi";
import { ACC, ACC4, C, SIZE, TEXT, tint } from "@/lib/tokens";
import { Icon, type IconName } from "@/components/ui/icons";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Meter, SCREEN_IN } from "@/components/ui/primitives";
import { ResourceViewer } from "@/components/library/ResourceViewer";
import { formatarTempo, idDoYoutube } from "@/components/library/VideoPlayer";

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

const VOLTAR: Partial<Record<string, string>> = {
  biblioteca: "Biblioteca",
  modulo: "Trilha",
};

export function ResourcePage() {
  const { state, dispatch } = useAppState();
  const id = state.activeResourceId;

  // Não existe rota para UM material: a lista já vem filtrada pelo perfil e é
  // pequena, e é a mesma resposta que a biblioteca acabou de usar — então sai
  // do cache do navegador, e do cache offline quando não há rede.
  const materiais = useQuery(() => libraryApi.list({ only_mine: true }), [], {
    enabled: id !== null,
  });
  const resource = materiais.data?.find((item) => item.id === id) ?? null;

  const voltar = () => dispatch({ type: "navigate", screen: state.resourceReturn });

  if (!id) {
    return (
      <EmptyState
        title="Nenhum material aberto"
        description="Escolha um item na biblioteca para abrir aqui."
        action={
          <button type="button" className="btn btn-primary" onClick={voltar}>
            <Icon name="arrowLeft" size={15} />
            Voltar
          </button>
        }
      />
    );
  }
  if (materiais.loading) return <Loading label="Abrindo o material…" />;
  if (materiais.error) {
    return <ErrorState message={materiais.error} onRetry={materiais.reload} />;
  }
  if (!resource) {
    return (
      <EmptyState
        title="Material não encontrado"
        description="Ele pode ter saído da sua biblioteca desde que esta tela foi aberta."
        action={
          <button type="button" className="btn btn-primary" onClick={voltar}>
            <Icon name="arrowLeft" size={15} />
            Voltar
          </button>
        }
      />
    );
  }

  return <Conteudo resource={resource} onVoltar={voltar} de={state.resourceReturn} />;
}

/**
 * Separado da tela porque o progresso é estado LOCAL desta sessão de consumo.
 *
 * Ele precisa nascer do material carregado — e um `useState` na tela acima
 * ficaria preso ao primeiro valor, que é `null` enquanto a lista não chegou.
 * Trocar de componente quando o material chega é o que dá o valor inicial
 * certo sem um efeito de sincronização.
 */
function Conteudo({
  resource,
  onVoltar,
  de,
}: {
  resource: Resource;
  onVoltar: () => void;
  de: string;
}) {
  const [progresso, setProgresso] = useState({
    status: resource.user_status,
    pct: resource.user_progress_pct,
    segundos: resource.user_position_seconds,
  });

  // O título da aba acompanha o que está aberto. Instalado na tela de início
  // o título não aparece, mas no navegador é ele que diferencia duas abas do
  // PathR — e é grátis.
  useEffect(() => {
    const anterior = document.title;
    document.title = `${resource.title} — PathR`;
    return () => {
      document.title = anterior;
    };
  }, [resource.title]);

  const cor = resource.kind === "video" ? ACC : resource.kind === "exercise" ? C.verde : C.azul;
  const concluido = progresso.status === "done";
  const temConteudoAqui = resource.kind !== "video" || idDoYoutube(resource.url) !== null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, ...SCREEN_IN }}>
      <button
        type="button"
        className="btn btn-ghost"
        // O rótulo visível repete o nome do destino, e o destino também é uma
        // aba da barra de baixo. Sem um nome próprio, "Biblioteca" passa a
        // designar dois botões diferentes na mesma tela — ambíguo para quem
        // navega por leitor de tela, e para qualquer teste.
        aria-label={`Voltar para ${VOLTAR[de] ?? "a tela anterior"}`}
        style={{ alignSelf: "flex-start", fontSize: SIZE.apoio, paddingInline: 0 }}
        onClick={onVoltar}
      >
        <Icon name="arrowLeft" size={14} />
        {VOLTAR[de] ?? "Voltar"}
      </button>

      <header style={{ display: "flex", alignItems: "flex-start", gap: 11.2 }}>
        <span
          aria-hidden
          style={{
            width: 40,
            height: 40,
            flex: "none",
            borderRadius: 10,
            display: "grid",
            placeItems: "center",
            background: tint(cor, 16),
            color: cor,
          }}
        >
          <Icon name={ICON_BY_KIND[resource.kind] ?? "article"} size={21} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 style={{ fontSize: 20, lineHeight: 1.25, margin: 0, fontWeight: 500 }}>
            {resource.title}
          </h1>
          <div style={{ fontSize: SIZE.rotulo, color: TEXT.faint, marginTop: 3 }}>
            {[
              resource.provider ?? resource.author,
              resource.duration_min ? `${resource.duration_min} min` : null,
              resource.language === "pt" ? "português" : resource.language === "en" ? "inglês" : resource.language,
              KIND_LABEL[resource.kind] ?? resource.kind,
            ]
              .filter(Boolean)
              .join(" · ")}
          </div>
        </div>
      </header>

      <Progresso pct={progresso.pct} segundos={progresso.segundos} concluido={concluido} />

      <ResourceViewer
        resource={resource}
        onProgresso={(mudanca) =>
          setProgresso({
            status: mudanca.status,
            pct: mudanca.progress_pct,
            segundos: mudanca.position_seconds,
          })
        }
      />

      {/* Só quando há conteúdo aqui dentro. Um vídeo que não é do YouTube já
          mostra o próprio botão para a fonte, e dois caminhos para o mesmo
          lugar, um embaixo do outro, é ruído. */}
      {temConteudoAqui ? (
        <a
          href={resource.url}
          target="_blank"
          rel="noreferrer noopener"
          style={{ fontSize: SIZE.apoio, color: TEXT.muted, alignSelf: "flex-start" }}
        >
          Abrir na fonte original
        </a>
      ) : null}
    </div>
  );
}

/** A barra do topo: quanto já foi, e onde parou. */
function Progresso({
  pct,
  segundos,
  concluido,
}: {
  pct: number;
  segundos: number | null;
  concluido: boolean;
}) {
  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8.4,
          marginBottom: 5.6,
          fontSize: SIZE.apoio,
        }}
      >
        <span style={{ flex: 1, minWidth: 0, color: TEXT.muted }}>
          {concluido ? "Concluído" : pct > 0 ? `${pct}% consumido` : "Ainda não começou"}
          {segundos && !concluido ? ` · parou em ${formatarTempo(segundos)}` : ""}
        </span>
        {concluido ? (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              color: ACC4,
              whiteSpace: "nowrap",
            }}
          >
            <Icon name="check" size={13} />
            concluído
          </span>
        ) : null}
      </div>
      <Meter pct={concluido ? 100 : pct} color={ACC4} label="Progresso neste material" />
    </div>
  );
}
