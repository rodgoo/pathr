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
import { ACC4, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { ErrorState } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";

const ROTULO: Record<RouteChange["tipo"], { texto: string; cor: string }> = {
  compactar: { texto: "Compactado", cor: C.verde },
  reforcar: { texto: "Reforçado", cor: C.ambar },
  reagendar: { texto: "Cronograma", cor: C.azul },
};

function antesDepois(mudanca: RouteChange): string {
  if ("horas" in mudanca.antes) return `${mudanca.antes.horas}h → ${mudanca.depois.horas}h`;
  if ("fim_semana" in mudanca.antes)
    return `termina na semana ${mudanca.antes.fim_semana} → ${mudanca.depois.fim_semana}`;
  return "";
}

export function RouteAdjustments({ onAjustado }: { onAjustado?: () => void }) {
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
          ? "Nenhum ajuste necessário — o plano está coerente com o que foi medido."
          : `${resultado.mudancas.length} ${resultado.mudancas.length === 1 ? "ajuste aplicado" : "ajustes aplicados"}.`,
      );
      historico.reload();
      onAjustado?.();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : "Não consegui ajustar a rota.");
    } finally {
      setAjustando(false);
    }
  }

  const ultimo = historico.data?.[0];

  return (
    <Panel pad={16.8} style={{ marginBottom: 33.6 }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: 11.2 }}>
        <Kicker>Ajustes de rota</Kicker>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ marginLeft: "auto", fontSize: 12 }}
          onClick={() => void ajustar()}
          disabled={ajustando}
        >
          <Icon name="refresh" size={15} />
          {ajustando ? "Conferindo…" : "Reajustar agora"}
        </button>
      </div>
      <p style={{ fontSize: 12, color: TEXT.faint, margin: "5.6px 0 0", maxWidth: "76ch" }}>
        O plano se corrige toda semana com o que foi medido: domínio comprovado em quiz vira
        revisão curta, lacuna recorrente ganha mais tempo, e o cronograma segue o seu ritmo real.
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
            Último ajuste · semana {ultimo.semana} ·{" "}
            {new Date(ultimo.em).toLocaleDateString("pt-BR")}
          </div>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {ultimo.mudancas.map((mudanca, posicao) => (
              <li
                key={`${mudanca.tipo}-${mudanca.node_id ?? posicao}`}
                style={{ padding: "8.4px 0", borderTop: `1px solid ${HAIRLINE}` }}
              >
                <div style={{ fontSize: 13 }}>
                  <span style={{ color: ROTULO[mudanca.tipo].cor }}>
                    {ROTULO[mudanca.tipo].texto}
                  </span>{" "}
                  · {mudanca.titulo}
                  <span style={{ color: TEXT.faint, fontSize: 11.5 }}> · {antesDepois(mudanca)}</span>
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
