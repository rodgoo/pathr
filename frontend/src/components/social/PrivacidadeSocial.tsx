/**
 * Aparecer ou não nas sugestões de outras contas.
 *
 * Ligado por padrão — sugerir quem estuda perto é o propósito da aba de
 * amigos —, e a frase embaixo diz exatamente o que desligar muda. Uma chave de
 * privacidade sem explicação faz a pessoa imaginar que está mais escondida do
 * que está: quem já tem o seu @ continua conseguindo te adicionar.
 */

import { useEffect, useState } from "react";
import { social } from "@/api/endpoints";
import { C, TEXT } from "@/lib/tokens";
import { Kicker, Panel } from "@/components/ui/primitives";

export function PrivacidadeSocial() {
  const [ligado, setLigado] = useState<boolean | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    social
      .privacidade()
      .then((dados) => vivo && setLigado(dados.discoverable))
      .catch(() => vivo && setLigado(true));
    return () => {
      vivo = false;
    };
  }, []);

  async function alternar() {
    if (ligado === null) return;
    const proximo = !ligado;
    setErro(null);
    setLigado(proximo);
    try {
      await social.gravarPrivacidade(proximo);
    } catch (caught) {
      setLigado(!proximo);
      setErro(caught instanceof Error ? caught.message : "Não consegui salvar.");
    }
  }

  return (
    <Panel pad={16.8}>
      <Kicker style={{ display: "block", marginBottom: 11.2 }}>Pessoas</Kicker>
      <label
        style={{
          display: "flex",
          gap: 11.2,
          alignItems: "flex-start",
          padding: "11.2px 14px",
          borderRadius: 8,
          background: "#1b1d2b",
          cursor: ligado === null ? "default" : "pointer",
        }}
      >
        <input
          type="checkbox"
          checked={Boolean(ligado)}
          disabled={ligado === null}
          onChange={() => void alternar()}
          style={{ marginTop: 2 }}
        />
        <span style={{ minWidth: 0 }}>
          <span style={{ display: "block", fontSize: 13.5 }}>Aparecer nas sugestões de amigos</span>
          <span style={{ display: "block", fontSize: 11.5, color: TEXT.faint, marginTop: 3 }}>
            Desligado, você não aparece nas sugestões nem na busca por nome. Quem já tem o seu @
            ainda consegue te encontrar e te convidar.
          </span>
        </span>
      </label>
      {erro ? <p style={{ margin: "8.4px 0 0", fontSize: 12.5, color: C.ambar }}>{erro}</p> : null}
    </Panel>
  );
}
