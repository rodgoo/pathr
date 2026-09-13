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
import { ACC, ACC4, C, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { IconButton } from "@/components/ui/IconButton";
import { Kicker, Panel } from "@/components/ui/primitives";
import { MASTERY_LABELS } from "./TechnologyRow";

const CHAVE = "pathr:tutorial-niveis:fechado";

/** O que cada nível quer dizer, com um exemplo do dia a dia, e o que o plano faz com ele. */
const NIVEIS: { exemplo: string; plano: string }[] = [
  { exemplo: "Ainda não usei, mas quero aprender.", plano: "Vira meta: o roadmap ensina do zero, e Cursos sugere certificados." },
  { exemplo: "Já vi em tutorial ou num projeto de estudo.", plano: "O roadmap começa pelos fundamentos, sem repetir o básico demais." },
  { exemplo: "Consigo usar, consultando documentação e exemplos.", plano: "O roadmap aprofunda até você fazer sozinho." },
  { exemplo: "Uso no trabalho sem ajuda, do começo ao fim.", plano: "Dominado: o roadmap não ensina de novo, só revisa. Conta como sua stack nas Vagas." },
  { exemplo: "Resolvo problemas difíceis e oriento outras pessoas.", plano: "Conta como ponto forte nas Vagas e nas sugestões de amigos." },
  { exemplo: "Referência no assunto: arquitetura, performance, detalhes internos.", plano: "Conta como ponto forte, e o plano usa como base para o que vem depois." },
];

function lerFechado(): boolean {
  try {
    return window.localStorage.getItem(CHAVE) === "1";
  } catch {
    return false;
  }
}

export function TutorialDeNiveis() {
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
        Como funcionam os níveis?
      </button>
    );
  }

  const ultimo = passo === NIVEIS.length;

  return (
    <Panel pad={16.8} style={{ boxShadow: `inset 0 0 0 1px ${tint(ACC, 40)}` }}>
      <section aria-label="Como funcionam os níveis">
        <div style={{ display: "flex", alignItems: "center", gap: 8.4, marginBottom: 8.4 }}>
          <Icon name="info" size={16} style={{ color: ACC4 }} />
          <Kicker>Como funcionam os níveis</Kicker>
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>
            {ultimo ? "resumo" : `${passo + 1} de ${NIVEIS.length}`}
          </span>
          <IconButton icon="x" label="Fechar tutorial" onClick={() => alternar(true)} style={{ marginLeft: "auto" }} />
        </div>

        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "72ch" }}>
          Para cada tecnologia, marque se ela entra no seu plano e escolha o nível que você tem hoje. Seja honesto:
          o nível decide o que o roadmap ensina e o que ele pula.
        </p>

        {/* A régua inteira, sempre à vista: cada nível é um botão que leva ao passo dele. */}
        <div role="tablist" aria-label="Níveis" style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginBottom: 11.2 }}>
          {MASTERY_LABELS.map((rotulo, nivel) => {
            const ativo = passo === nivel;
            const dominado = nivel >= 3;
            return (
              <button
                key={rotulo}
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
                <strong>N{nivel}</strong> · {rotulo}
              </button>
            );
          })}
        </div>

        {ultimo ? (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: TEXT.strong, lineHeight: 1.6 }}>
            <li>
              <strong>N0 a N2</strong>: o roadmap ensina e vira meta de estudo.
            </li>
            <li>
              <strong>N3 ou mais</strong>: dominado — o roadmap não ensina de novo, e a tecnologia conta como sua stack
              nas Vagas.
            </li>
            <li>Mudou de nível? Troque aqui a qualquer momento: o plano se ajusta na próxima semana.</li>
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
              <strong style={{ color: passo >= 3 ? C.verde : ACC4 }}>N{passo}</strong> · {MASTERY_LABELS[passo]}
            </div>
            <div style={{ fontSize: 13, color: TEXT.strong }}>{NIVEIS[passo].exemplo}</div>
            <div style={{ fontSize: 12.5, color: TEXT.muted, display: "flex", gap: 6, alignItems: "flex-start" }}>
              <Icon name="road" size={14} style={{ color: ACC4, flex: "none", marginTop: 2 }} />
              {NIVEIS[passo].plano}
            </div>
          </div>
        )}

        <div style={{ display: "flex", gap: 8.4, marginTop: 11.2, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-ghost" disabled={passo === 0} onClick={() => setPasso((p) => Math.max(0, p - 1))}>
            <Icon name="arrowLeft" size={15} />
            Anterior
          </button>
          {ultimo ? (
            <button type="button" className="btn btn-primary" onClick={() => alternar(true)}>
              <Icon name="check" size={15} />
              Entendi, vou marcar minhas skills
            </button>
          ) : (
            <>
              <button type="button" className="btn btn-secondary" onClick={() => setPasso((p) => p + 1)}>
                Próximo
                <Icon name="arrowRight" size={15} />
              </button>
              {/* Pular inteiro, de qualquer passo: quem já conhece os níveis não precisa percorrer seis telas. */}
              <button type="button" className="btn btn-ghost" style={{ marginLeft: "auto" }} onClick={() => alternar(true)}>
                Pular tutorial
              </button>
            </>
          )}
        </div>
      </section>
    </Panel>
  );
}
