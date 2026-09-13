/**
 * "Mídia anexada": o aviso de que o relato tem foto, e o caminho para abri-la.
 *
 * A foto NÃO aparece embutida na lista. Espremida numa caixa de altura fixa,
 * um print de celular ou uma foto larga ficava fora de proporção, e quem
 * modera não conseguia ler o que o print mostrava. Ao clicar, a imagem abre
 * numa aba nova, no tamanho real — o visualizador do navegador cuida de
 * zoom e rolagem melhor do que qualquer caixa daqui.
 *
 * A foto sai pela API com a sessão (e decifrada no servidor), então não há
 * URL pública para pôr num link: os bytes chegam como blob e a aba recebe um
 * `blob:` desta origem. A aba é aberta ANTES da busca, ainda dentro do
 * clique — aberta depois de um `await`, o bloqueador de pop-up a barraria.
 */

import { useState } from "react";
import { relatos } from "@/api/endpoints";
import { Icon } from "@/components/ui/icons";
import { C, TEXT, tint } from "@/lib/tokens";

export function MidiaAnexada({ relatoId }: { relatoId: string }) {
  const [abrindo, setAbrindo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function abrir() {
    setErro(null);
    setAbrindo(true);
    const aba = window.open("", "_blank");
    try {
      const blob = await relatos.foto(relatoId);
      const url = URL.createObjectURL(blob);
      if (aba) {
        aba.location.href = url;
      } else {
        // Pop-up bloqueado mesmo assim: um link clicado por código ainda abre.
        const link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener";
        link.click();
      }
      // A aba já carregou a imagem; o blob pode sair da memória depois.
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      aba?.close();
      setErro("Não consegui abrir a mídia agora.");
    } finally {
      setAbrindo(false);
    }
  }

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      <button
        type="button"
        onClick={() => void abrir()}
        disabled={abrindo}
        title="Abrir a foto em tamanho real numa nova aba"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          padding: "4px 10px",
          borderRadius: 999,
          font: "inherit",
          fontSize: 12.5,
          cursor: abrindo ? "progress" : "pointer",
          color: C.azul,
          background: tint(C.azul, 10),
          border: `1px solid ${tint(C.azul, 35)}`,
        }}
      >
        <Icon name="camera" size={14} />
        {abrindo ? "Abrindo…" : "Mídia anexada"}
        <Icon name="externalLink" size={12} style={{ opacity: 0.7 }} />
      </button>
      {erro ? <span role="alert" style={{ fontSize: 12, color: C.ambar }}>{erro}</span> : null}
      {!erro && abrindo ? <span style={{ fontSize: 11.5, color: TEXT.faint }}>carregando a foto…</span> : null}
    </span>
  );
}
