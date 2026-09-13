/**
 * O checklist da semana, na tela inicial.
 *
 * Substitui o "A seguir", que mostrava os próximos módulos sem dizer o que
 * fazer com eles. Aqui cada linha é uma ação com tamanho (minutos), método
 * (o pilar) e motivo — e a lista inteira cabe nas horas que a pessoa tem.
 *
 * A ordem é a do servidor e não se reordena aqui: revisão primeiro, assuntos
 * alternados, extras no fim. É a ordem que o método pede, e deixá-la ao gosto
 * da tela desfaria a intercalação.
 *
 * A lista também se REMONTA sozinha: quando o nível sobe num quiz, ou a
 * semana acaba cedo, o servidor refaz o que está por fazer ao abrir a tela
 * (ver `plan.semana_atual`). Havia um botão "atualizar com meu nível atual"
 * para isso — que só servia a quem lembrasse de apertá-lo.
 *
 * Quiz e explicação se marcam sozinhos quando acontecem — o servidor confere o
 * rastro. Por isso a caixa deles fica travada depois de confirmada: desmarcar
 * algo que o banco comprova seria a tela mentindo para quem olha.
 */

import { useEffect, useState } from "react";
import { plan as planApi } from "@/api/endpoints";
import type { WeeklyItem, WeeklyPlan } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useQuery } from "@/hooks/useApi";
import type { ModuleTab } from "@/types";
import { ACC, ACC4, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { IconButton } from "@/components/ui/IconButton";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";

/** Em que aba do módulo cada tipo de item acontece. */
const ABA: Record<WeeklyItem["tipo"], ModuleTab> = {
  revisao: "quiz",
  material: "material",
  quiz: "quiz",
  feynman: "atividade",
  pratica: "atividade",
  desafio: "atividade",
};

const NIVEL: Record<string, string> = {
  iniciante: "iniciante",
  intermediario: "intermediário",
  avancado: "avançado",
};

function horas(minutos: number): string {
  const h = minutos / 60;
  return h >= 1 ? `${h.toFixed(h % 1 === 0 ? 0 : 1)}h` : `${minutos} min`;
}

export function WeeklyChecklist() {
  const { dispatch } = useAppState();
  const semana = useQuery(() => planApi.week(), []);
  const [plano, setPlano] = useState<WeeklyPlan | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (semana.data) setPlano(semana.data);
  }, [semana.data]);

  if (semana.loading && !plano) return <Loading label="Montando a sua semana…" />;
  if (semana.error && !plano) return <ErrorState message={semana.error} onRetry={semana.reload} />;
  if (!plano) return null;

  async function marcar(item: WeeklyItem) {
    const feito = !item.feito;
    setErro(null);
    // Otimista: a caixa responde ao clique. Se o servidor recusar, volta.
    setPlano((atual) => (atual ? trocar(atual, item.id, feito) : atual));
    try {
      const resposta = await planApi.mark(item.id, feito);
      setPlano((atual) => (atual ? { ...atual, resumo: resposta.resumo } : atual));
    } catch (caught) {
      setPlano((atual) => (atual ? trocar(atual, item.id, !feito) : atual));
      setErro(caught instanceof Error ? caught.message : "Não consegui salvar.");
    }
  }

  const { resumo } = plano;

  return (
    <Panel pad={16.8}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: 11.2 }}>
        <Kicker>Semana {plano.semana} do plano</Kicker>
        <span style={{ fontSize: 12, color: TEXT.muted }}>
          {resumo.feitos} de {resumo.total} feitos · {horas(resumo.minutos_feitos)} de{" "}
          {horas(resumo.minutos)}
        </span>
      </div>

      <p style={{ fontSize: 12, color: TEXT.faint, margin: "5.6px 0 11.2px", maxWidth: "76ch" }}>
        A lista segue o seu nível em cada módulo — quem está começando estuda antes de ser
        testado; quem já domina vai direto para explicar e aplicar — e cabe nas{" "}
        {horas(plano.orcamento_min)} que você tem para a semana.
      </p>

      {plano.ajustes.length > 0 ? (
        <div
          role="status"
          style={{
            marginBottom: 11.2,
            padding: "8.4px 11.2px",
            borderRadius: 8,
            background: "rgba(145,132,217,.1)",
            fontSize: 12.5,
            color: ACC4,
          }}
        >
          Sua rota foi ajustada nesta virada de semana ({plano.ajustes.length}{" "}
          {plano.ajustes.length === 1 ? "mudança" : "mudanças"}).{" "}
          <button
            type="button"
            onClick={() => dispatch({ type: "navigate", screen: "roadmap" })}
            style={{
              border: 0,
              background: "transparent",
              color: ACC,
              font: "inherit",
              textDecoration: "underline",
              cursor: "pointer",
              padding: 0,
            }}
          >
            Ver o que mudou
          </button>
        </div>
      ) : null}

      {plano.itens.length === 0 ? (
        <p style={{ fontSize: 13, color: TEXT.muted, margin: 0 }}>
          Nada pendente nesta semana. Os próximos módulos entram aqui assim que houver o que
          puxar.
        </p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {plano.itens.map((item) => (
            <li
              key={item.id}
              style={{
                display: "flex",
                gap: 11.2,
                alignItems: "flex-start",
                padding: "10px 0",
                borderTop: `1px solid ${HAIRLINE}`,
                opacity: item.feito ? 0.62 : 1,
              }}
            >
              <input
                type="checkbox"
                id={`semana-${item.id}`}
                checked={item.feito}
                disabled={item.verificado}
                onChange={() => void marcar(item)}
                style={{ marginTop: 3, flex: "none", accentColor: "#9184d9" }}
              />
              <div style={{ minWidth: 0, flex: 1 }}>
                <label
                  htmlFor={`semana-${item.id}`}
                  style={{
                    fontSize: 13.5,
                    cursor: item.verificado ? "default" : "pointer",
                    textDecoration: item.feito ? "line-through" : "none",
                  }}
                >
                  {item.titulo}
                </label>
                <div style={{ fontSize: 11.5, color: TEXT.faint, marginTop: 2 }}>
                  <span style={{ color: ACC4 }}>{item.pilar}</span> · {item.minutos} min
                  {item.nivel ? ` · nível ${NIVEL[item.nivel] ?? item.nivel}` : ""}
                  {item.verificado ? (
                    <span style={{ color: C.verde }}> · confirmado pelo que você fez</span>
                  ) : null}
                </div>
                {!item.feito ? (
                  <div style={{ fontSize: 12, color: TEXT.muted, marginTop: 4, lineHeight: 1.5 }}>
                    {item.detalhe}
                  </div>
                ) : null}
              </div>
              {!item.feito ? (
                <IconButton
                  icon="arrowRight"
                  label="Abrir"
                  onClick={() =>
                    dispatch({
                      type: "navigate",
                      screen: "modulo",
                      moduleTab: ABA[item.tipo],
                      nodeId: item.node_id,
                    })
                  }
                />
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {erro ? (
        <p role="alert" style={{ margin: "8.4px 0 0", fontSize: 12.5, color: C.ambar }}>
          {erro}
        </p>
      ) : null}
    </Panel>
  );
}

function trocar(plano: WeeklyPlan, id: string, feito: boolean): WeeklyPlan {
  return {
    ...plano,
    itens: plano.itens.map((item) => (item.id === id ? { ...item, feito } : item)),
  };
}
