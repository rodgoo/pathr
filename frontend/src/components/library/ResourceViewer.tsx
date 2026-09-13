/**
 * O material aberto dentro do PathR — vídeo ou artigo — com o progresso
 * saindo do próprio consumo.
 *
 * Este componente é a cola: escolhe entre player e leitor, e é o único que
 * fala com a API de progresso. Player e leitor só informam onde a pessoa
 * está; decidir o que gravar, quando gravar e quando marcar como concluído é
 * uma regra só, e mora aqui em vez de duplicada nos dois.
 *
 * Só o CONTEÚDO. Título, progresso e o botão de voltar são da tela que o
 * envolve (`pages/ResourcePage`). Antes ele desenhava a própria moldura e
 * abria dentro da lista: no celular virava uma caixa dentro de outra caixa,
 * e o vídeo terminava do tamanho de um selo.
 *
 * A gravação é preguiçosa de propósito: só sai quando o progresso AVANÇOU o
 * bastante para valer uma requisição. Sem isso, um vídeo de uma hora renderia
 * dezenas de escritas idênticas para dizer a mesma coisa.
 */

import { useRef, useState } from "react";
import { library as libraryApi } from "@/api/endpoints";
import type { Resource, ResourceState } from "@/api/types";
import { useQuery } from "@/hooks/useApi";
import { TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { ErrorState, Loading } from "@/components/ui/States";
import { ArticleReader } from "@/components/library/ArticleReader";
import {
  CONCLUIDO_A_PARTIR_DE,
  VideoPlayer,
  formatarTempo,
  idDoYoutube,
} from "@/components/library/VideoPlayer";

/** Só grava quando o progresso andou este tanto desde a última escrita. */
const PASSO_MINIMO = 0.03;

export function ResourceViewer({
  resource,
  onProgresso,
}: {
  resource: Resource;
  /** Avisa a lista para repintar sem ir ao servidor de novo. */
  onProgresso: (mudanca: {
    status: ResourceState;
    progress_pct: number;
    position_seconds: number | null;
  }) => void;
}) {
  const videoId = resource.kind === "video" ? idDoYoutube(resource.url) : null;
  const ultimoGravado = useRef(resource.user_progress_pct / 100);
  const [concluido, setConcluido] = useState(resource.user_status === "done");

  // Só busca o artigo quando NÃO é vídeo. A condição era `!videoId`, e por
  // isso um vídeo fora do YouTube — que não tem player nosso — caía nos dois
  // caminhos: o leitor dizia "ainda não busquei o texto" e o bloco de vídeo
  // dizia "não consigo tocar aqui", uma embaixo da outra, com dois botões
  // iguais para o mesmo lugar.
  const leitura = useQuery(() => libraryApi.reader(resource.id), [resource.id], {
    enabled: resource.kind !== "video",
  });

  async function gravar(fracao: number, segundos: number | null) {
    const virouConcluido = fracao >= CONCLUIDO_A_PARTIR_DE;
    const andouPouco = fracao - ultimoGravado.current < PASSO_MINIMO;
    // A conclusão sempre passa, mesmo andando pouco: é a escrita que mais
    // importa e a que menos pode esperar o próximo tique.
    if (andouPouco && !(virouConcluido && !concluido)) return;

    ultimoGravado.current = fracao;
    const status: ResourceState = virouConcluido ? "done" : "in_progress";
    const pct = Math.round(fracao * 100);
    if (virouConcluido) setConcluido(true);

    onProgresso({ status, progress_pct: pct, position_seconds: segundos });
    try {
      await libraryApi.setProgress(resource.id, {
        status,
        progress_pct: pct,
        position_seconds: segundos,
        minutes_spent: virouConcluido ? resource.duration_min ?? 0 : 0,
      });
    } catch {
      // Perder uma gravação de progresso não pode interromper a leitura nem
      // a reprodução. A próxima janela grava de novo, com o valor maior.
      ultimoGravado.current = Math.max(0, fracao - PASSO_MINIMO);
    }
  }

  return (
    <div>
      {videoId ? (
        <VideoPlayer
          videoId={videoId}
          comecarEm={resource.user_position_seconds ?? 0}
          onProgresso={(segundos, fracao) => void gravar(fracao, segundos)}
        />
      ) : leitura.loading ? (
        <Loading label="Buscando o texto do artigo…" />
      ) : leitura.error ? (
        <ErrorState message={leitura.error} onRetry={leitura.reload} />
      ) : leitura.data ? (
        <ArticleReader
          conteudo={leitura.data}
          comecarEm={resource.user_progress_pct / 100}
          onProgresso={(fracao) => void gravar(fracao, null)}
        />
      ) : null}

      {resource.kind === "video" && !videoId ? (
        /* Vídeo que não é do YouTube: não há player nosso para ele, e fingir
           que há seria pior que dizer a verdade e oferecer o link. */
        <div style={{ textAlign: "center", padding: 22.4 }}>
          <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 14px" }}>
            Este vídeo não é do YouTube, então não consigo tocá-lo aqui dentro.
          </p>
          <a
            className="btn btn-secondary"
            href={resource.url}
            target="_blank"
            rel="noreferrer noopener"
            style={{ textDecoration: "none" }}
          >
            <Icon name="externalLink" size={15} />
            Abrir no site original
          </a>
        </div>
      ) : null}

      {resource.user_position_seconds && videoId && !concluido ? (
        <p style={{ fontSize: 11, color: TEXT.faint, margin: "8.4px 0 0" }}>
          Última posição salva: {formatarTempo(resource.user_position_seconds)}
        </p>
      ) : null}
    </div>
  );
}
