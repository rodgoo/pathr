/**
 * Ajustes do módulo de idioma dentro das Configurações.
 *
 * Mesma verdade da tela de idioma, editada aqui: o interruptor, a meta e o
 * tempo diário. Não duplica estado — as duas telas leem
 * `GET /english/profile`.
 */

import { english as englishApi } from "@/api/endpoints";
import { useMutation, useQuery } from "@/hooks/useApi";
import { ACC, TEXT } from "@/lib/tokens";
import { Segmented } from "@/components/ui/Segmented";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";

const TARGETS = [
  { value: "B1", label: "B1" },
  { value: "B2", label: "B2" },
  { value: "C1", label: "C1" },
] as const;

const GOALS = [
  { value: "10", label: "10 min" },
  { value: "15", label: "15 min" },
  { value: "30", label: "30 min" },
] as const;

export function LanguageSettings() {
  const profile = useQuery(() => englishApi.profile(), []);
  const update = useMutation((body: Parameters<typeof englishApi.update>[0]) =>
    englishApi.update(body),
  );

  if (profile.loading) return <Loading />;
  if (profile.error) return <ErrorState message={profile.error} onRetry={profile.reload} />;
  if (!profile.data) return null;

  const data = profile.data;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <Panel pad={16.8}>
        <Kicker style={{ display: "block", marginBottom: 11.2 }}>Módulo de idioma</Kicker>
        <label
          style={{
            display: "flex",
            gap: 11.2,
            alignItems: "flex-start",
            fontSize: 13.5,
            cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={data.enabled}
            onChange={async () => {
              profile.set((current) => ({ ...current, enabled: !current.enabled }));
              await update.run({ enabled: !data.enabled });
            }}
            style={{ marginTop: 3, accentColor: ACC }}
          />
          <span>
            Incluir {data.daily_goal_min} min de inglês no plano diário.
            <span style={{ display: "block", fontSize: 11.5, color: TEXT.faint, marginTop: 2 }}>
              Desligar não apaga seu nível nem o histórico — só tira o bloco do dia.
            </span>
          </span>
        </label>
      </Panel>

      <Panel pad={16.8}>
        <Kicker style={{ display: "block", marginBottom: 5.6 }}>Meta de nível</Kicker>
        <p style={{ fontSize: 12, color: TEXT.muted, margin: "0 0 11.2px" }}>
          A meta define quanto tempo o plano de idioma reserva e quais práticas são liberadas. Seu
          nível medido ({data.cefr_level ?? "ainda sem nivelamento"}) não muda com isso.
        </p>
        <Segmented
          name="english-target"
          label="Meta de nível"
          value={data.target_level}
          options={TARGETS}
          onChange={async (target_level) => {
            profile.set((current) => ({ ...current, target_level }));
            await update.run({ target_level });
          }}
        />
      </Panel>

      <Panel pad={16.8}>
        <Kicker style={{ display: "block", marginBottom: 5.6 }}>Tempo por dia</Kicker>
        <p style={{ fontSize: 12, color: TEXT.muted, margin: "0 0 11.2px" }}>
          Quanto do seu dia de estudo vai para o idioma. Sai do mesmo orçamento de horas do roadmap.
        </p>
        <Segmented
          name="english-goal"
          label="Minutos por dia"
          value={String(data.daily_goal_min)}
          options={GOALS}
          onChange={async (value) => {
            const daily_goal_min = Number(value);
            profile.set((current) => ({ ...current, daily_goal_min }));
            await update.run({ daily_goal_min });
          }}
        />
      </Panel>
    </div>
  );
}
