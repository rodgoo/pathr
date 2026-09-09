/**
 * Perfil e competências.
 *
 * Os dois grupos de tags são a ideia do produto tornada visível: o que já
 * está comprovado (contorno cheio) contra o que o plano ainda deve
 * (tracejado). Clicar em qualquer um marca ou desmarca como meta de estudo —
 * e isso muda o roadmap na próxima geração.
 */

import type { CSSProperties } from "react";
import { profile as profileApi, tags as tagsApi } from "@/api/endpoints";
import type { UserTag } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useAuth } from "@/hooks/useAuth";
import { useQuery } from "@/hooks/useApi";
import { ACC4, TEXT } from "@/lib/tokens";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Meter, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { Avatar } from "@/components/profile/Avatar";
import { TagButton } from "@/components/profile/TagButton";
import { MASTERY_LABELS } from "@/components/profile/TechnologyRow";

export function ProfilePage() {
  const { user } = useAuth();
  const { dispatch } = useAppState();
  const overview = useQuery((signal) => profileApi.overview(signal), []);
  const tags = useQuery(() => tagsApi.mine(), []);

  if (overview.loading || tags.loading) return <Loading label="Carregando seu perfil…" />;
  if (overview.error) return <ErrorState message={overview.error} onRetry={overview.reload} />;
  if (tags.error) return <ErrorState message={tags.error} onRetry={tags.reload} />;
  if (!overview.data || !tags.data) return null;

  const { profile, streak, roadmap } = overview.data;
  const proven = tags.data.filter((tag) => tag.proficiency > 0);
  const planned = tags.data.filter((tag) => tag.proficiency === 0);

  const toggle = async (tagId: string, next: boolean) => {
    // Atualiza a tela antes da resposta: a escrita é pequena e previsível, e
    // esperar o servidor para pintar um botão já clicado faz a interface
    // parecer travada.
    tags.set((current) =>
      current.map((tag) => (tag.id === tagId ? { ...tag, is_target: next } : tag)),
    );
    await tagsApi.update(tagId, { is_target: next });
  };

  return (
    <div style={SCREEN_IN}>
      <h1 style={{ fontSize: 28, margin: "0 0 5.6px" }}>Perfil e tags</h1>
      <p
        style={{
          margin: "0 0 16.8px",
          fontSize: 13.5,
          color: "rgba(233,233,237,.6)",
          maxWidth: "62ch",
        }}
      >
        O que está marcado aqui alimenta o roadmap. Desmarcar uma tag tira os módulos ligados a ela
        da próxima geração; marcar uma nova recalcula o prazo.
      </p>

      <IdentityCard
        name={user?.name ?? ""}
        profile={profile}
        streak={streak}
        roadmap={roadmap}
        onEdit={() => dispatch({ type: "navigate", screen: "config", settingsTab: "conta" })}
      />

      {tags.data.length === 0 ? (
        <EmptyState
          title="Nenhuma competência ainda"
          description="Envie seu currículo para eu extrair as tecnologias, ou adicione uma a uma em Configurações, aba Skills."
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
        <Panel pad={16.8}>
          <TagGroup
            title={`Domínio atual · ${proven.length}`}
            hint="o que o currículo comprovou ou o quiz confirmou"
            tags={proven}
            onToggle={toggle}
          />
          <TagGroup
            title={`No plano · ${planned.length}`}
            hint="ainda em N0 — é o que o roadmap vai cobrir"
            tags={planned}
            dashed
            onToggle={toggle}
            style={{ marginTop: 16.8 }}
          />
          <ScaleLegend />
        </Panel>
      )}
    </div>
  );
}


function IdentityCard({
  name,
  profile,
  streak,
  roadmap,
  onEdit,
}: {
  name: string;
  profile: import("@/api/types").Profile;
  streak: import("@/api/types").Streak;
  roadmap: import("@/api/types").RoadmapSummary | null;
  onEdit: () => void;
}) {
  const fields = [
    { label: "Cargo", value: profile.current_role },
    { label: "Senioridade", value: profile.seniority },
    {
      label: "Experiência",
      value: profile.years_experience ? `${profile.years_experience} anos` : null,
    },
    { label: "Disponibilidade", value: `${profile.weekly_hours}h por semana` },
    { label: "Sequência", value: `${streak.current} dias` },
    { label: "XP", value: String(streak.total_xp) },
  ].filter((field) => field.value);

  return (
    <Panel
      tone="section"
      pad={16.8}
      style={{
        marginBottom: 11.2,
        display: "flex",
        flexWrap: "wrap",
        gap: 16.8,
        alignItems: "flex-start",
      }}
    >
      <Avatar nome={name} editavel />

      <div style={{ flex: 1, minWidth: 220, display: "flex", flexDirection: "column", gap: 11.2 }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: 8.4 }}>
          <span style={{ fontSize: 22 }}>{name}</span>
          <button
            type="button"
            className="btn btn-ghost"
            style={{ marginLeft: "auto", fontSize: 12.5 }}
            onClick={onEdit}
          >
            Editar perfil
          </button>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(128px,1fr))",
            gap: 11.2,
          }}
        >
          {fields.map((field) => (
            <div key={field.label} style={{ minWidth: 0 }}>
              <div style={{ fontSize: 10.5, color: TEXT.muted }}>{field.label}</div>
              <div style={{ fontSize: 14 }}>{field.value}</div>
            </div>
          ))}
        </div>

        {roadmap ? (
          <div style={{ paddingTop: 11.2, borderTop: "1px solid rgba(233,233,237,.14)" }}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "baseline",
                gap: 8.4,
                marginBottom: 5.6,
              }}
            >
              <span style={{ fontSize: 12.5, color: "rgba(233,233,237,.7)" }}>{roadmap.title}</span>
              <span style={{ marginLeft: "auto", fontSize: 11.5, color: TEXT.muted }}>
                {roadmap.done_nodes} de {roadmap.total_nodes} · {roadmap.progress_pct}%
              </span>
            </div>
            <Meter pct={roadmap.progress_pct} color={ACC4} height={4} label="Progresso do plano" />
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function TagGroup({
  title,
  hint,
  tags,
  dashed,
  onToggle,
  style,
}: {
  title: string;
  hint: string;
  tags: UserTag[];
  dashed?: boolean;
  onToggle: (tagId: string, next: boolean) => void;
  style?: CSSProperties;
}) {
  return (
    <div style={style}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "baseline",
          gap: 8.4,
          marginBottom: 11.2,
        }}
      >
        <Kicker>{title}</Kicker>
        <span style={{ fontSize: 11.5, color: TEXT.faint }}>{hint}</span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6 }}>
        {tags.map((tag) => (
          <TagButton
            key={tag.id}
            tag={tag}
            dashed={dashed}
            onToggle={() => onToggle(tag.id, !tag.is_target)}
          />
        ))}
      </div>
    </div>
  );
}

function ScaleLegend() {
  return (
    <div style={{ marginTop: 16.8, paddingTop: 14, borderTop: "1px solid rgba(233,233,237,.12)" }}>
      <Kicker tone="muted" style={{ display: "block", marginBottom: 8.4 }}>
        Escala de domínio
      </Kicker>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))",
          gap: 8.4,
        }}
      >
        {MASTERY_LABELS.map((label, level) => (
          <div key={label} style={{ display: "flex", alignItems: "baseline", gap: 6, minWidth: 0 }}>
            <span
              style={{ fontSize: 11, fontFamily: "ui-monospace, Menlo, monospace", color: ACC4 }}
            >
              N{level}
            </span>
            <span style={{ fontSize: 12.5 }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
