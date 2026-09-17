/**
 * A barra de navegação.
 *
 * Os contadores dos badges são reais: o número de módulos vem do roadmap, o
 * nível do idioma vem do módulo de idioma. Quando ainda não há plano, o badge
 * some em vez de mostrar zero — zero sugere um plano vazio, e o que existe é
 * um plano ainda não gerado.
 */

import { useState } from "react";
import { english as englishApi, roadmap as roadmapApi, social } from "@/api/endpoints";
import { telaLiberada } from "@/lib/features";
import { useAppState } from "@/hooks/useAppState";
import { useT } from "@/lib/i18n";
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
  const t = useT();
  const { state, dispatch } = useAppState();
  const { user, logout } = useAuth();

  const roadmap = useQuery(() => roadmapApi.current(), []);
  const english = useQuery(() => englishApi.profile(), []);
  const amizades = useQuery(() => social.amigos(), []);
  const convites = amizades.data?.recebidos.length ?? 0;

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
      label: t("nav.grupoGeral"),
      items: [
        { label: t("nav.inicio"), screen: "home", icon: "home" },
        {
          label: t("nav.roadmap"),
          screen: "roadmap",
          icon: "road",
          badge: plan ? String(plan.total_nodes) : undefined,
        },
        { label: t("nav.trilha"), screen: "modulo", icon: "book" },
        { label: t("nav.cursos"), screen: "cursos", icon: "award" },
        { label: t("nav.vagas"), screen: "vagas", icon: "suitcase" },
        { label: t("nav.candidaturas"), screen: "candidaturas", icon: "send" },
        { label: t("nav.noticias"), screen: "noticias", icon: "clock" },
        // O contador é de convites RECEBIDOS: é o único número aqui que pede
        // uma ação, e sem ele o convite ficaria esperando alguém abrir a aba.
        {
          label: t("nav.amigos"),
          screen: "amigos",
          icon: "users",
          badge: convites ? String(convites) : undefined,
        },
      ],
    },
    {
      label: t("nav.grupoFerramentas"),
      items: [
        { label: t("nav.codigo"), screen: "codigo", icon: "code" },
        // "Idiomas" virou "Treino de idiomas": com o idioma do app agora
        // trocável em Configurações, o nome antigo prometia a outra coisa.
        { label: t("nav.treinoDeIdiomas"), screen: "ingles", icon: "flag", badge: languageBadge },
      ],
    },
    {
      label: t("nav.grupoConta"),
      items: [
        { label: t("nav.perfil"), screen: "perfil", icon: "user" },
        { label: t("nav.curriculo"), screen: "cv", icon: "file" },
        { label: t("nav.relatar"), screen: "relatar", icon: "flag" },
        { label: t("nav.manual"), screen: "manual", icon: "info" },
        { label: t("nav.config"), screen: "config", icon: "cog" },
      ],
    },
  ];

  return (
    <aside
      style={{
        flex: "1 1 200px",
        maxWidth: 226,
        minWidth: 186,
        // Presa na janela: a página rola, a barra fica. Sem isto o painel
        // subia junto com o conteúdo e META e Sair sumiam da tela.
        position: "sticky",
        top: 11.2,
        alignSelf: "flex-start",
        height: "calc(100dvh - 22.4px)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        gap: 22.4,
        padding: "14px 11.2px",
        borderRadius: 14,
        background: PANEL,
        boxShadow: "0 0 0 1px #222228",
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

      <nav
        aria-label="Navegação principal"
        // Só a lista rola, e só se não couber: META e Sair ficam presos embaixo.
        style={{ flex: 1, minHeight: 0, overflowY: "auto", display: "flex", flexDirection: "column", gap: 22.4 }}
      >
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
            {group.items.filter((item) => telaLiberada(item.screen, user?.features)).map((item) => (
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

      <div style={{ flex: "none", display: "flex", flexDirection: "column", gap: 8.4 }}>
        {plan ? (
          <div
            style={{
              padding: 11.2,
              borderRadius: 8,
              background: SURF,
              boxShadow: "0 0 0 1px #3f424d",
            }}
          >
            <Kicker style={{ display: "block", marginBottom: 5.6 }}>{t("sidebar.meta")}</Kicker>
            <div style={{ fontSize: 12.5, lineHeight: 1.4, color: "rgba(233,233,237,.8)" }}>
              {plan.target_role || plan.title}
            </div>
            <Meter
              pct={plan.progress_pct}
              label={t("sidebar.progresso")}
              style={{ marginTop: 8.4 }}
            />
            <div style={{ marginTop: 5.6, fontSize: 11, color: TEXT.muted }}>
              {t("sidebar.modulos", {
                pct: plan.progress_pct,
                feitos: plan.done_nodes,
                total: plan.total_nodes,
              })}
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
          {t("nav.sair")}
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
  // O contador só aparece com o mouse em cima (ou o foco do teclado): na
  // lista inteira ele distrai de onde a pessoa quer ir. O leitor de tela
  // continua ouvindo — ele vai no rótulo acessível, não só no visual.
  const [realce, setRealce] = useState(false);
  return (
    <button
      type="button"
      // A lateral também aparece no celular deitado, onde o alvo é o dedo.
      className="toque"
      onClick={onClick}
      onMouseEnter={() => setRealce(true)}
      onMouseLeave={() => setRealce(false)}
      onFocus={() => setRealce(true)}
      onBlur={() => setRealce(false)}
      aria-current={active ? "page" : undefined}
      aria-label={item.badge ? `${item.label} (${item.badge})` : undefined}
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
        transition: "background-color .2s ease, color .2s ease, box-shadow .2s ease",
      }}
    >
      <span style={{ width: 16, height: 16, flex: "none", display: "grid", placeItems: "center" }}>
        <Icon name={item.icon} size={16} filled={active} />
      </span>
      <span style={{ flex: 1, minWidth: 0 }}>{item.label}</span>
      {item.badge ? (
        <span
          aria-hidden
          style={{
            opacity: realce ? 1 : 0,
            transition: "opacity .15s ease",
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
