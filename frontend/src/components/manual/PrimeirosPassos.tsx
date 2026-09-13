/**
 * Os primeiros passos, em ordem, com o que já foi feito marcado.
 *
 * No Manual aparece sempre, completo. No Início aparece compacto e só
 * enquanto falta algum passo obrigatório — quem já montou tudo não precisa de
 * um lembrete a cada abertura — e dá para dispensar.
 */

import { useState } from "react";
import { useAppState } from "@/hooks/useAppState";
import { usePrimeirosPassos, type Passo } from "@/lib/primeirosPassos";
import { ACC, ACC4, C, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { Kicker, Panel } from "@/components/ui/primitives";

const DISPENSADO = "pathr:primeiros-passos:dispensado";

function lerDispensado(): boolean {
  try {
    return window.localStorage.getItem(DISPENSADO) === "1";
  } catch {
    return false;
  }
}

export function PrimeirosPassos({ compacto = false }: { compacto?: boolean }) {
  const { dispatch } = useAppState();
  const { passos, feitos, obrigatorios, carregando } = usePrimeirosPassos();
  const [dispensado, setDispensado] = useState(lerDispensado);

  if (compacto && (carregando || feitos === obrigatorios || dispensado)) return null;

  const proximo = passos.find((passo) => passo.feito === false && !passo.opcional) ?? passos.find((p) => p.feito === false);
  const lista = compacto ? passos.filter((p) => !p.opcional) : passos;

  function ir(passo: Passo) {
    dispatch({ type: "navigate", screen: passo.destino.screen, settingsTab: passo.destino.settingsTab });
  }

  return (
    <Panel pad={16.8} style={compacto ? { boxShadow: `inset 0 0 0 1px ${tint(ACC, 38)}` } : undefined}>
      <section aria-label="Primeiros passos">
        <div style={{ display: "flex", alignItems: "center", gap: 8.4, flexWrap: "wrap", marginBottom: 8.4 }}>
          <Icon name="road" size={16} style={{ color: ACC4 }} />
          <Kicker>Primeiros passos</Kicker>
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>
            {carregando ? "conferindo…" : `${feitos} de ${obrigatorios} essenciais feitos`}
          </span>
          {compacto ? (
            <span style={{ marginLeft: "auto", display: "inline-flex", gap: 4 }}>
              <button
                type="button"
                className="btn btn-ghost"
                style={{ fontSize: 12 }}
                onClick={() => dispatch({ type: "navigate", screen: "manual" })}
              >
                <Icon name="book" size={14} />
                Manual de bordo
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                style={{ fontSize: 12 }}
                onClick={() => {
                  setDispensado(true);
                  try {
                    window.localStorage.setItem(DISPENSADO, "1");
                  } catch {
                    // vale só nesta visita
                  }
                }}
              >
                Pular
                <Icon name="x" size={14} />
              </button>
            </span>
          ) : null}
        </div>

        {proximo && !carregando ? (
          <p style={{ margin: "0 0 11.2px", fontSize: 12.5, color: TEXT.muted }}>
            Próximo passo: <strong style={{ color: TEXT.strong }}>{proximo.titulo}</strong>.
          </p>
        ) : null}

        <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
          {lista.map((passo, posicao) => {
            const eProximo = passo === proximo;
            const cor = passo.feito ? C.verde : eProximo ? ACC4 : TEXT.faint;
            return (
              <li
                key={passo.id}
                style={{
                  display: "flex",
                  gap: 10,
                  alignItems: "flex-start",
                  padding: "9px 11px",
                  borderRadius: 9,
                  background: eProximo ? tint(ACC, 10) : "rgba(233,233,237,.03)",
                }}
              >
                <span
                  aria-hidden
                  style={{
                    flex: "none",
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    display: "grid",
                    placeItems: "center",
                    fontSize: 11.5,
                    color: passo.feito ? "#08130d" : cor,
                    background: passo.feito ? C.verde : "transparent",
                    border: passo.feito ? "none" : `1px solid ${cor}`,
                  }}
                >
                  {passo.feito ? <Icon name="check" size={13} /> : posicao + 1}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, color: TEXT.full, display: "flex", gap: 6, flexWrap: "wrap", alignItems: "baseline" }}>
                    {passo.titulo}
                    {passo.opcional ? <span style={{ fontSize: 11, color: TEXT.faint }}>opcional</span> : null}
                    {passo.feito ? <span style={{ fontSize: 11, color: C.verde }}>feito</span> : null}
                  </div>
                  <div style={{ fontSize: 11.5, color: TEXT.faint }}>{passo.onde}</div>
                  {!compacto || eProximo ? (
                    <>
                      <div style={{ fontSize: 12.5, color: TEXT.strong, marginTop: 4 }}>{passo.oQueFazer}</div>
                      <div style={{ fontSize: 12, color: TEXT.muted, marginTop: 2, display: "flex", gap: 5 }}>
                        <Icon name="arrowRight" size={13} style={{ color: ACC4, flex: "none", marginTop: 2 }} />
                        <span>
                          <span style={{ color: TEXT.faint }}>Em seguida: </span>
                          {passo.depois}
                        </span>
                      </div>
                    </>
                  ) : null}
                </div>
                {!passo.feito ? (
                  <button
                    type="button"
                    className={eProximo ? "btn btn-primary" : "btn btn-ghost"}
                    style={{ fontSize: 12, flex: "none" }}
                    onClick={() => ir(passo)}
                    aria-label={`Ir para: ${passo.titulo}`}
                  >
                    Ir
                    <Icon name="arrowRight" size={14} />
                  </button>
                ) : null}
              </li>
            );
          })}
        </ol>
      </section>
    </Panel>
  );
}
