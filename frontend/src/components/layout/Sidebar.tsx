/**
 * A barra de navegação.
 *
 * Os contadores dos badges são reais: o número de módulos vem do roadmap, o
 * nível do idioma vem do módulo de idioma. Quando ainda não há plano, o badge
 * some em vez de mostrar zero — zero sugere um plano vazio, e o que existe é
 * um plano ainda não gerado.
 */

import { english as englishApi, roadmap as roadmapApi } from "@/api/endpoints";
import { useAppState } from "@/hooks/useAppState";
import { useAuth } from "@/hooks/useAuth";
import { useQuery } from "@/hooks/useApi";
import { ACC4, PANEL, SURF, TEXT } from "@/lib/tokens";
import type { Screen } from "@/types";
import { Icon, type IconName } from "@/components/ui/icons";
import { Logo } from "@/components/ui/Logo";
import { Kicker, Meter } from "@/components/ui/primitives";

interface NavEntry {
  label: string;
  screen: Screen;
  icon: IconName;
  badge?: string;
}

export function Sidebar() {
  const { state, dispatch } = useAppState();
  const { logout } = useAuth();

  const roadmap = useQuery(() => roadmapApi.current(), []);
  const english = useQuery(() => englishApi.profile(), []);

  // O material aberto pertence à tela de onde veio — ver MobileNav.
  const telaAtiva = state.screen === "material" ? state.resourceReturn : state.screen;
  const plan = roadmap.data;
  const languageBadge = english.data
    ? english.data.enabled
      ? english.data.cefr_level ?? "—"
      : "off"
    : undefined;

  const groups: { label: string; items: NavEntry[] }[] = [
    {
      label: "Geral",
      items: [
        { label: "Início", screen: "home", icon: "home" },
        {
          label: "Roadmap",
          screen: "roadmap",
          icon: "road",
          badge: plan ? String(plan.total_nodes) : undefined,
        },
        { label: "Trilha atual", screen: "modulo", icon: "book" },
      ],
    },
    {
      label: "Ferramentas",
      items: [
        { label: "Biblioteca", screen: "biblioteca", icon: "library" },
        { label: "Idiomas", screen: "ingles", icon: "flag", badge: languageBadge },
      ],
    },
    {
      label: "Conta",
      items: [
        { label: "Perfil e tags", screen: "perfil", icon: "user" },
        { label: "Currículo", screen: "cv", icon: "file" },
        { label: "Configurações", screen: "config", icon: "cog" },
      ],
    },
  ];

  return (
    <aside
      style={{
        flex: "1 1 200px",
        maxWidth: 226,
        minWidth: 186,
        display: "flex",
        flexDirection: "column",
        gap: 22.4,
        padding: "14px 11.2px",
        borderRadius: 14,
        background: PANEL,
        boxShadow: "0 0 0 1px #2b2e3d",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8.4 }}>
        <Logo size={28} />
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.15, minWidth: 0 }}>
          <span style={{ fontSize: 15, fontWeight: 500 }}>PathR</span>
          <span style={{ fontSize: 10, letterSpacing: ".06em", color: TEXT.faint }}>
            pathr.notter.com.br
          </span>
        </div>
      </div>

      <nav aria-label="Navegação principal" style={{ display: "contents" }}>
        {groups.map((group) => (
          <div key={group.label} style={{ display: "flex", flexDirection: "column", gap: 2.8 }}>
            <div
              style={{
                fontSize: 9.5,
                letterSpacing: ".12em",
                textTransform: "uppercase",
                color: "rgba(233,233,237,.35)",
                padding: "0 8.4px",
                marginBottom: 5.6,
              }}
            >
              {group.label}
            </div>
            {group.items.map((item) => (
              <NavButton
                key={item.screen}
                item={item}
                active={telaAtiva === item.screen}
                onClick={() => dispatch({ type: "navigate", screen: item.screen })}
              />
            ))}
          </div>
        ))}
      </nav>

      <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 8.4 }}>
        {plan ? (
          <div
            style={{
              padding: 11.2,
              borderRadius: 8,
              background: SURF,
              boxShadow: "0 0 0 1px #3f424d",
            }}
          >
            <Kicker style={{ display: "block", marginBottom: 5.6 }}>Meta</Kicker>
            <div style={{ fontSize: 12.5, lineHeight: 1.4, color: "rgba(233,233,237,.8)" }}>
              {plan.target_role || plan.title}
            </div>
            <Meter
              pct={plan.progress_pct}
              label="Progresso do roadmap"
              style={{ marginTop: 8.4 }}
            />
            <div style={{ marginTop: 5.6, fontSize: 11, color: TEXT.muted }}>
              {plan.progress_pct}% · {plan.done_nodes} de {plan.total_nodes} módulos
            </div>
          </div>
        ) : null}

        <button
          type="button"
          className="btn btn-ghost"
          style={{ fontSize: 12, justifyContent: "flex-start", gap: 9, paddingInline: 8.4 }}
          onClick={() => void logout()}
        >
          <Icon name="signOut" size={15} />
          Sair
        </button>
      </div>
    </aside>
  );
}

function NavButton({
  item,
  active,
  onClick,
}: {
  item: NavEntry;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      // A lateral também aparece no celular deitado, onde o alvo é o dedo.
      className="toque"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 9,
        padding: "7px 8.4px",
        border: 0,
        borderRadius: 8,
        font: "inherit",
        fontSize: 13.5,
        textAlign: "left",
        cursor: "pointer",
        background: active ? "rgba(145,132,217,.13)" : "transparent",
        color: active ? ACC4 : "rgba(233,233,237,.72)",
        boxShadow: active ? "inset 0 0 0 1px rgba(145,132,217,.35)" : "none",
      }}
    >
      <span style={{ width: 16, height: 16, flex: "none", display: "grid", placeItems: "center" }}>
        <Icon name={item.icon} size={16} filled={active} />
      </span>
      <span style={{ flex: 1, minWidth: 0 }}>{item.label}</span>
      {item.badge ? (
        <span
          style={{
            fontSize: 10,
            padding: "1px 6px",
            borderRadius: 5,
            background: active ? "rgba(145,132,217,.22)" : "rgba(233,233,237,.08)",
            color: active ? "#e7e5fe" : TEXT.muted,
          }}
        >
          {item.badge}
        </span>
      ) : null}
    </button>
  );
}
