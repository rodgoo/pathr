/**
 * O botão que manda o servidor procurar material.
 *
 * Existe porque a busca é cara em cota, não em dinheiro: a YouTube Data API
 * dá ~99 buscas por dia para o app inteiro. Disparar a curadoria sozinho, ao
 * abrir a tela, gastaria a cota do dia com quem só passou os olhos na lista.
 * Um clique é a diferença entre "quero material disto" e "abri o módulo".
 *
 * O resultado é dito com o número junto ("6 materiais novos"), e não com um
 * "pronto!": a pessoa acabou de esperar por uma busca e o que ela quer saber
 * é se valeu. Quando não veio nada, o servidor manda o motivo — buscamos há
 * pouco, nenhum link passou na verificação, nenhuma fonte configurada — e ele
 * aparece como está, porque cada um desses pede uma reação diferente dela.
 */

import { useState } from "react";
import { library as libraryApi } from "@/api/endpoints";
import { useT } from "@/lib/i18n";
import { C, SIZE, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";

interface CurateButtonProps {
  /** Sem isto, busca pelas tags do perfil inteiro. */
  nodeId?: string;
  /** Chamado depois de uma busca que trouxe material, para recarregar a lista. */
  onFound: () => void;
  label?: string;
}

export function CurateButton({ nodeId, onFound, label }: CurateButtonProps) {
  const t = useT();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const rotulo = label ?? t("modulo.curar.procurarMaterial");

  async function run() {
    setPending(true);
    setMessage(null);
    setFailed(false);
    try {
      const result = await libraryApi.curate(nodeId);
      if (result.novos > 0) {
        setMessage(
          `${result.novos} ${result.novos === 1 ? t("modulo.curar.materialNovo") : t("modulo.curar.materiaisNovos")}.`,
        );
        onFound();
      } else {
        setMessage(result.motivo ?? t("modulo.curar.nadaNovo"));
      }
    } catch (caught) {
      setFailed(true);
      setMessage(caught instanceof Error ? caught.message : t("modulo.curar.buscaFalhou"));
    } finally {
      setPending(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8.4 }}>
      <button
        type="button"
        className="btn btn-primary"
        onClick={() => void run()}
        disabled={pending}
      >
        {/* A espera é de segundos (duas APIs mais a verificação de cada link),
            então o rótulo precisa dizer que algo está acontecendo — um botão
            só desabilitado parece travado. */}
        <Icon name="search" size={15} />
        {pending ? t("modulo.curar.procurando") : rotulo}
      </button>
      {message ? (
        <span
          role="status"
          style={{ fontSize: SIZE.apoio, color: failed ? C.ambar : TEXT.muted, textAlign: "center" }}
        >
          {message}
        </span>
      ) : null}
    </div>
  );
}
