/**
 * O mini tutorial dos níveis, no topo de Skills.
 *
 * "N2" não quer dizer nada para quem chega. E o nível é a decisão mais
 * importante desta tela: é por ele que o roadmap sabe o que ensinar e o que
 * pular, e que Cursos e Vagas sabem o que sugerir. Por isso a explicação fica
 * na própria tela, em passos, e não num texto de ajuda escondido.
 *
 * Aberto na primeira visita; fechado, vira um botão "Como funcionam os
 * níveis?" — quem já entendeu não precisa ler de novo toda vez.
 */

import { useState } from "react";
import { useT } from "@/lib/i18n";
import { ACC, ACC4, C, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { IconButton } from "@/components/ui/IconButton";
import { Kicker, Panel } from "@/components/ui/primitives";
import { MASTERY_KEYS } from "./TechnologyRow";

const CHAVE = "pathr:tutorial-niveis:fechado";

/** O que cada nível quer dizer: as CHAVES do exemplo e do que o plano faz, na
 * ordem N0..N5. Resolvidas no render com `t()`. */
const NIVEIS: { exemplo: string; plano: string }[] = [
  { exemplo: "perfil.tutorial.n0.exemplo", plano: "perfil.tutorial.n0.plano" },
  { exemplo: "perfil.tutorial.n1.exemplo", plano: "perfil.tutorial.n1.plano" },
  { exemplo: "perfil.tutorial.n2.exemplo", plano: "perfil.tutorial.n2.plano" },
  { exemplo: "perfil.tutorial.n3.exemplo", plano: "perfil.tutorial.n3.plano" },
  { exemplo: "perfil.tutorial.n4.exemplo", plano: "perfil.tutorial.n4.plano" },
  { exemplo: "perfil.tutorial.n5.exemplo", plano: "perfil.tutorial.n5.plano" },
];

function lerFechado(): boolean {
  try {
    return window.localStorage.getItem(CHAVE) === "1";
  } catch {
    return false;
  }
}

export function TutorialDeNiveis() {
  const t = useT();
  const [fechado, setFechado] = useState(lerFechado);
  const [passo, setPasso] = useState(0);

  function alternar(valor: boolean) {
    setFechado(valor);
    try {
      if (valor) window.localStorage.setItem(CHAVE, "1");
      else window.localStorage.removeItem(CHAVE);
    } catch {
      // Sem armazenamento: vale só nesta visita.
    }
  }

  if (fechado) {
    return (
      <button
        type="button"
        className="btn btn-ghost"
        style={{ alignSelf: "flex-start", fontSize: 12.5 }}
        onClick={() => {
          setPasso(0);
          alternar(false);
        }}
      >
        <Icon name="info" size={15} />
        {t("perfil.tutorial.comoFunciona")}
      </button>
    );
  }

  const ultimo = passo === NIVEIS.length;

  return (
    <Panel pad={16.8} style={{ boxShadow: `inset 0 0 0 1px ${tint(ACC, 40)}` }}>
      <section aria-label={t("perfil.tutorial.titulo")}>
        <div style={{ display: "flex", alignItems: "center", gap: 8.4, marginBottom: 8.4 }}>
          <Icon name="info" size={16} style={{ color: ACC4 }} />
          <Kicker>{t("perfil.tutorial.titulo")}</Kicker>
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>
            {ultimo ? t("perfil.tutorial.resumo") : t("perfil.tutorial.contador", { atual: passo + 1, total: NIVEIS.length })}
          </span>
          <IconButton icon="x" label={t("perfil.tutorial.fechar")} onClick={() => alternar(true)} style={{ marginLeft: "auto" }} />
        </div>

        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "72ch" }}>
          {t("perfil.tutorial.introducao")}
        </p>

        {/* A régua inteira, sempre à vista: cada nível é um botão que leva ao passo dele. */}
        <div role="tablist" aria-label={t("perfil.tutorial.niveisLabel")} style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginBottom: 11.2 }}>
          {MASTERY_KEYS.map((chave, nivel) => {
            const ativo = passo === nivel;
            const dominado = nivel >= 3;
            return (
              <button
                key={chave}
                type="button"
                role="tab"
                aria-selected={ativo}
                onClick={() => setPasso(nivel)}
                style={{
                  padding: "5px 10px",
                  borderRadius: 7,
                  font: "inherit",
                  fontSize: 12,
                  cursor: "pointer",
                  border: `1px solid ${ativo ? ACC : "rgba(233,233,237,.14)"}`,
                  background: ativo ? tint(ACC, 16) : "transparent",
                  color: ativo ? ACC4 : dominado ? C.verde : TEXT.muted,
                }}
              >
                <strong>N{nivel}</strong> · {t(chave)}
              </button>
            );
          })}
        </div>

        {ultimo ? (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: TEXT.strong, lineHeight: 1.6 }}>
            <li>
              <strong>{t("perfil.tutorial.resumoN0N2Rotulo")}</strong>{t("perfil.tutorial.resumoN0N2Texto")}
            </li>
            <li>
              <strong>{t("perfil.tutorial.resumoN3Rotulo")}</strong>{t("perfil.tutorial.resumoN3Texto")}
            </li>
            <li>{t("perfil.tutorial.resumoMudou")}</li>
          </ul>
        ) : (
          <div
            style={{
              display: "grid",
              gap: 6,
              padding: "11.2px 12.6px",
              borderRadius: 9,
              background: "rgba(233,233,237,.04)",
            }}
          >
            <div style={{ fontSize: 14, color: TEXT.full }}>
              <strong style={{ color: passo >= 3 ? C.verde : ACC4 }}>N{passo}</strong> · {t(MASTERY_KEYS[passo])}
            </div>
            <div style={{ fontSize: 13, color: TEXT.strong }}>{t(NIVEIS[passo].exemplo)}</div>
            <div style={{ fontSize: 12.5, color: TEXT.muted, display: "flex", gap: 6, alignItems: "flex-start" }}>
              <Icon name="road" size={14} style={{ color: ACC4, flex: "none", marginTop: 2 }} />
              {t(NIVEIS[passo].plano)}
            </div>
          </div>
        )}

        <div style={{ display: "flex", gap: 8.4, marginTop: 11.2, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-ghost" disabled={passo === 0} onClick={() => setPasso((p) => Math.max(0, p - 1))}>
            <Icon name="arrowLeft" size={15} />
            {t("perfil.tutorial.anterior")}
          </button>
          {ultimo ? (
            <button type="button" className="btn btn-primary" onClick={() => alternar(true)}>
              <Icon name="check" size={15} />
              {t("perfil.tutorial.entendi")}
            </button>
          ) : (
            <>
              <button type="button" className="btn btn-secondary" onClick={() => setPasso((p) => p + 1)}>
                {t("perfil.tutorial.proximo")}
                <Icon name="arrowRight" size={15} />
              </button>
              {/* Pular inteiro, de qualquer passo: quem já conhece os níveis não precisa percorrer seis telas. */}
              <button type="button" className="btn btn-ghost" style={{ marginLeft: "auto" }} onClick={() => alternar(true)}>
                {t("perfil.tutorial.pular")}
              </button>
            </>
          )}
        </div>
      </section>
    </Panel>
  );
}
