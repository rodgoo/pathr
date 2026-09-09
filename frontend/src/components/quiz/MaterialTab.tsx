/**
 * O material do módulo: a curadoria filtrada pelas tags dele.
 *
 * Reaproveita a mesma linha da Biblioteca, porque é o mesmo objeto — o que
 * muda é só o recorte. Duas listas diferentes para a mesma coisa é como um
 * app passa a ter dois lugares onde marcar "concluído" e só um deles contar.
 */

import { library as libraryApi } from "@/api/endpoints";
import { KIND_LABEL } from "@/api/library-filters";
import type { RoadmapNode } from "@/api/types";
import { useEffect, useState } from "react";
import { useAppState } from "@/hooks/useAppState";
import { useQuery } from "@/hooks/useApi";
import { curarModulo } from "@/lib/curadoria";
import { TEXT } from "@/lib/tokens";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { CurateButton } from "@/components/library/CurateButton";
import { LibraryRow } from "@/components/library/LibraryRow";

export function MaterialTab({ node }: { node: RoadmapNode }) {
  const { dispatch } = useAppState();
  const [curando, setCurando] = useState(false);
  const resources = useQuery(() => libraryApi.list({ only_mine: true }), []);

  // O filtro por tag acontece no cliente porque a lista já veio filtrada pelo
  // perfil e é pequena — pedir ao servidor de novo, por tag, seria uma
  // requisição a mais para cortar dez linhas.
  const wanted = new Set(node.tag_ids);
  const matching = (resources.data ?? []).filter((resource) =>
    resource.tag_ids.some((tag) => wanted.has(tag)),
  );
  const vazio = !resources.loading && !resources.error && matching.length === 0;

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

  if (resources.loading) return <Loading label="Buscando material…" />;
  if (resources.error) return <ErrorState message={resources.error} onRetry={resources.reload} />;

  if (curando) {
    return <Loading label="Procurando material para este módulo…" />;
  }

  if (matching.length === 0) {
    return (
      <EmptyState
        title="Sem material para este módulo ainda"
        description="Já procurei nas tecnologias deste módulo e não achei nada que passasse na verificação. Tentar de novo mais tarde costuma trazer resultado."
        action={<CurateButton nodeId={node.id} onFound={resources.reload} />}
      />
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
      <p style={{ fontSize: 11.5, color: TEXT.faint, margin: 0 }}>
        {matching.length} {matching.length === 1 ? "material" : "materiais"} para as tecnologias
        deste módulo.
      </p>
      {matching.map((resource) => (
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
            // O status vai junto porque a rota o exige, e ele NÃO muda aqui:
            // anotar onde parou não conclui nem reabre nada.
            await libraryApi.setProgress(resource.id, {
              status: resource.user_status ?? "in_progress",
              position_note: nota,
            });
          }}
        />
      ))}
    </div>
  );
}
