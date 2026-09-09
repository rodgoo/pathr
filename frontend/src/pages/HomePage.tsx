/**
 * O painel.
 *
 * Uma requisição só (`GET /profile/overview`) traz tudo que a tela mostra —
 * streak, atividade, resumo do plano e nível de idioma. Cinco chamadas
 * paralelas colocariam o tempo da tela no pior caso das cinco, e nenhuma
 * delas é reaproveitada em outro lugar.
 *
 * Sem plano gerado, a tela vira convite para o onboarding em vez de um painel
 * de zeros.
 */

import { profile as profileApi, roadmap as roadmapApi } from "@/api/endpoints";
import { useAppState } from "@/hooks/useAppState";
import { useAuth } from "@/hooks/useAuth";
import { useQuery } from "@/hooks/useApi";
import { TEXT } from "@/lib/tokens";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { SCREEN_IN } from "@/components/ui/primitives";
import { ConsistencyPanel } from "@/components/dashboard/ConsistencyPanel";
import { ContinueCard } from "@/components/dashboard/ContinueCard";
import { KpiCards } from "@/components/dashboard/KpiCards";
import { StreakCard } from "@/components/dashboard/StreakCard";
import { TodayPlan } from "@/components/dashboard/TodayPlan";
import { TrackProgress } from "@/components/dashboard/TrackProgress";

const TODAY = new Intl.DateTimeFormat("pt-BR", {
  weekday: "short",
  day: "numeric",
  month: "long",
});

export function HomePage() {
  const { user } = useAuth();
  const { dispatch } = useAppState();
  const overview = useQuery((signal) => profileApi.overview(signal), []);
  // O plano completo só é buscado quando existe — sem isso, toda abertura do
  // painel de quem ainda não gerou nada bateria num 404 previsível.
  const plan = useQuery(() => roadmapApi.current(), [overview.data?.roadmap?.id], {
    enabled: Boolean(overview.data?.roadmap),
  });

  if (overview.loading) return <Loading label="Carregando seu painel…" />;
  if (overview.error) return <ErrorState message={overview.error} onRetry={overview.reload} />;
  if (!overview.data) return null;

  const { streak, activity, roadmap } = overview.data;
  const firstName = user?.name.split(" ")[0] ?? "";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16.8, ...SCREEN_IN }}>

      <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: 11.2 }}>
        <div>
          <div style={{ fontSize: 12.5, color: TEXT.muted }}>
            Bem-vindo de volta{firstName ? `, ${firstName}` : ""}
          </div>
          <h1 style={{ fontSize: 26, lineHeight: 1.2, margin: 0 }}>{TODAY.format(new Date())}</h1>
        </div>
        {roadmap?.current_node ? (
          <button
            type="button"
            className="btn btn-primary"
            style={{ marginLeft: "auto" }}
            onClick={() =>
              dispatch({ type: "navigate", screen: "modulo", nodeId: roadmap.current_node!.id })
            }
          >
            Retomar estudo
          </button>
        ) : null}
      </header>

      {!roadmap ? (
        <EmptyState
          title="Seu plano ainda não existe"
          description="Envie seu currículo e eu monto o roadmap a partir do que você já sabe — você revisa tudo antes de eu gerar."
          action={
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => dispatch({ type: "navigate", screen: "cv" })}
            >
              Enviar currículo
            </button>
          }
        />
      ) : (
        <>
          <KpiCards overview={overview.data} />
          <ConsistencyPanel activity={activity} />

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(210px,1fr))",
              gap: 11.2,
              alignItems: "stretch",
            }}
          >
            <StreakCard streak={streak} activity={activity} />
            {plan.data ? <TrackProgress roadmap={plan.data} /> : null}
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))",
              gap: 11.2,
              alignItems: "stretch",
            }}
          >
            <ContinueCard roadmap={roadmap} />
            {plan.data ? <TodayPlan roadmap={plan.data} /> : null}
          </div>
        </>
      )}
    </div>
  );
}
