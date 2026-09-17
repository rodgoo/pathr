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
import { useT } from "@/lib/i18n";
import { C, TEXT } from "@/lib/tokens";
import { Kicker, Panel } from "@/components/ui/primitives";

export function PrivacidadeSocial() {
  const t = useT();
  const [ligado, setLigado] = useState<boolean | null>(null);
  const [mostrarPresenca, setMostrarPresenca] = useState<boolean | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    social
      .privacidade()
      .then((dados) => {
        if (!vivo) return;
        setLigado(dados.discoverable);
        setMostrarPresenca(dados.show_attendance);
      })
      .catch(() => {
        if (!vivo) return;
        setLigado(true);
        setMostrarPresenca(true);
      });
    return () => {
      vivo = false;
    };
  }, []);

  async function alternar() {
    if (ligado === null || mostrarPresenca === null) return;
    const proximo = !ligado;
    setErro(null);
    setLigado(proximo);
    try {
      await social.gravarPrivacidade(proximo, mostrarPresenca);
    } catch (caught) {
      setLigado(!proximo);
      setErro(caught instanceof Error ? caught.message : t("amigos.privacidade.erroSalvar"));
    }
  }

  async function alternarPresenca() {
    if (ligado === null || mostrarPresenca === null) return;
    const proximo = !mostrarPresenca;
    setErro(null);
    setMostrarPresenca(proximo);
    try {
      await social.gravarPrivacidade(ligado, proximo);
    } catch (caught) {
      setMostrarPresenca(!proximo);
      setErro(caught instanceof Error ? caught.message : t("amigos.privacidade.erroSalvar"));
    }
  }

  return (
    <Panel pad={16.8}>
      <Kicker style={{ display: "block", marginBottom: 11.2 }}>{t("amigos.privacidade.titulo")}</Kicker>
      <label
        style={{
          display: "flex",
          gap: 11.2,
          alignItems: "flex-start",
          padding: "11.2px 14px",
          borderRadius: 8,
          background: "#0c0c10",
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
          <span style={{ display: "block", fontSize: 13.5 }}>{t("amigos.privacidade.aparecer")}</span>
          <span style={{ display: "block", fontSize: 11.5, color: TEXT.faint, marginTop: 3 }}>
            {t("amigos.privacidade.explicacao")}
          </span>
        </span>
      </label>

      <label
        style={{
          display: "flex",
          gap: 11.2,
          alignItems: "flex-start",
          padding: "11.2px 14px",
          borderRadius: 8,
          background: "#0c0c10",
          marginTop: 8.4,
          cursor: mostrarPresenca === null ? "default" : "pointer",
        }}
      >
        <input
          type="checkbox"
          checked={Boolean(mostrarPresenca)}
          disabled={mostrarPresenca === null}
          onChange={() => void alternarPresenca()}
          style={{ marginTop: 2 }}
        />
        <span style={{ minWidth: 0 }}>
          <span style={{ display: "block", fontSize: 13.5 }}>{t("amigos.privacidade.mostrarPresenca")}</span>
          <span style={{ display: "block", fontSize: 11.5, color: TEXT.faint, marginTop: 3 }}>
            {t("amigos.privacidade.mostrarPresencaExplicacao")}
          </span>
        </span>
      </label>
      {erro ? <p style={{ margin: "8.4px 0 0", fontSize: 12.5, color: C.ambar }}>{erro}</p> : null}
    </Panel>
  );
}
