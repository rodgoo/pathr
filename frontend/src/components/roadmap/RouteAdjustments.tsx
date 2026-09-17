/**
 * Os ajustes de rota, no topo do Roadmap.
 *
 * O plano se corrige sozinho toda virada de semana. Um plano que muda sem
 * dizer o quê nem por quê perde a confiança de quem o segue — por isso cada
 * mudança aparece com o motivo em texto, e com o antes e o depois.
 *
 * O botão existe para quem não quer esperar a segunda-feira: acabou de fazer
 * um quiz que provou domínio, ou teve uma semana perdida, e quer o plano
 * coerente com isso agora.
 */

import { useState } from "react";
import { plan as planApi } from "@/api/endpoints";
import type { RouteChange } from "@/api/types";
import { useQuery } from "@/hooks/useApi";
import { useIdioma, useT, type Traduzir } from "@/lib/i18n";
import { ACC4, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { ErrorState } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";

const COR_TIPO: Record<RouteChange["tipo"], string> = {
  compactar: C.verde,
  reforcar: C.ambar,
  reagendar: C.azul,
};

function antesDepois(mudanca: RouteChange, t: Traduzir): string {
  if ("horas" in mudanca.antes)
    return t("roadmap.ajustes.horas", { antes: mudanca.antes.horas, depois: mudanca.depois.horas });
  if ("fim_semana" in mudanca.antes)
    return t("roadmap.ajustes.reagenda", {
      antes: mudanca.antes.fim_semana,
      depois: mudanca.depois.fim_semana,
    });
  return "";
}

export function RouteAdjustments({ onAjustado }: { onAjustado?: () => void }) {
  const t = useT();
  const { idioma } = useIdioma();
  const historico = useQuery(() => planApi.adjustments(), []);
  const [ajustando, setAjustando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function ajustar() {
    setAjustando(true);
    setErro(null);
    setAviso(null);
    try {
      const resultado = await planApi.adjust();
      setAviso(
        resultado.mudancas.length === 0
          ? t("roadmap.ajustes.semAjuste")
          : resultado.mudancas.length === 1
            ? t("roadmap.ajustes.aplicadoUm", { n: resultado.mudancas.length })
            : t("roadmap.ajustes.aplicadoVarios", { n: resultado.mudancas.length }),
      );
      historico.reload();
      onAjustado?.();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : t("roadmap.ajustes.erroFallback"));
    } finally {
      setAjustando(false);
    }
  }

  const ultimo = historico.data?.[0];

  return (
    <Panel pad={16.8} style={{ marginBottom: 33.6 }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: 11.2 }}>
        <Kicker>{t("roadmap.ajustes.titulo")}</Kicker>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ marginLeft: "auto", fontSize: 12 }}
          onClick={() => void ajustar()}
          disabled={ajustando}
        >
          <Icon name="refresh" size={15} />
          {ajustando ? t("roadmap.ajustes.conferindo") : t("roadmap.ajustes.reajustar")}
        </button>
      </div>
      <p style={{ fontSize: 12, color: TEXT.faint, margin: "5.6px 0 0", maxWidth: "76ch" }}>
        {t("roadmap.ajustes.explicacao")}
      </p>

      {aviso ? (
        <p role="status" style={{ margin: "8.4px 0 0", fontSize: 12.5, color: ACC4 }}>
          {aviso}
        </p>
      ) : null}
      {erro ? <ErrorState message={erro} /> : null}

      {ultimo && ultimo.mudancas.length > 0 ? (
        <div style={{ marginTop: 11.2 }}>
          <div style={{ fontSize: 11.5, color: TEXT.faint, marginBottom: 5.6 }}>
            {t("roadmap.ajustes.ultimo", {
              semana: ultimo.semana,
              data: new Intl.DateTimeFormat(idioma).format(new Date(ultimo.em)),
            })}
          </div>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {ultimo.mudancas.map((mudanca, posicao) => (
              <li
                key={`${mudanca.tipo}-${mudanca.node_id ?? posicao}`}
                style={{ padding: "8.4px 0", borderTop: `1px solid ${HAIRLINE}` }}
              >
                <div style={{ fontSize: 13 }}>
                  <span style={{ color: COR_TIPO[mudanca.tipo] }}>
                    {t(`roadmap.ajustes.tipo.${mudanca.tipo}`)}
                  </span>{" "}
                  · {mudanca.titulo}
                  <span style={{ color: TEXT.faint, fontSize: 11.5 }}> · {antesDepois(mudanca, t)}</span>
                </div>
                <div style={{ fontSize: 12, color: TEXT.muted, marginTop: 3, lineHeight: 1.5 }}>
                  {mudanca.motivo}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Panel>
  );
}
