/**
 * Configurações, em três seções.
 *
 * Agrupadas pelo que mudam, não por tipo de dado: a conta, as competências
 * que alimentam o plano, e o módulo de idioma. O que era "objetivo" virou a
 * própria geração do roadmap, que agora mora na tela do plano — o objetivo só
 * existe no momento em que um plano é gerado.
 */

import { useAppState } from "@/hooks/useAppState";
import type { SettingsTab } from "@/types";
import { Chip } from "@/components/ui/Chip";
import type { IconName } from "@/components/ui/icons";
import { SCREEN_IN } from "@/components/ui/primitives";
import { LanguageSettings } from "@/components/english/LanguageSettings";
import { AccountTab } from "@/components/profile/AccountTab";
import { ApiStatusTab } from "@/components/profile/ApiStatusTab";
import { NoticesTab } from "@/components/profile/NoticesTab";
import { ObjectiveTab } from "@/components/profile/ObjectiveTab";
import { SkillsTab } from "@/components/profile/SkillsTab";
import { ModeracaoRelatos } from "@/components/relatos/ModeracaoRelatos";
import { ModeracaoUsuarios } from "@/components/moderacao/ModeracaoUsuarios";
import { useAuth } from "@/hooks/useAuth";

const ABAS: readonly { value: SettingsTab; label: string; icon: IconName }[] = [
  { value: "conta", label: "Conta", icon: "user" },
  { value: "objetivo", label: "Objetivo", icon: "flag" },
  { value: "skills", label: "Skills", icon: "code" },
  { value: "idiomas", label: "Idiomas", icon: "globe" },
  { value: "avisos", label: "Avisos e privacidade", icon: "cog" },
  { value: "integracoes", label: "Status das APIs", icon: "server" },
];

/**
 * A aba de moderação só existe para quem modera. Esconder a aba não protege
 * nada — o servidor responde 404 em /relatos/moderacao para qualquer outra
 * conta —, mas mostrar uma aba vazia a todo mundo anunciaria que ela existe.
 */
const ABA_MODERACAO = { value: "moderacao" as const, label: "Moderação", icon: "flag" as IconName };

export function SettingsPage() {
  const { state, dispatch } = useAppState();
  const { user } = useAuth();
  const TABS = user?.is_moderator || user?.is_super_admin ? [...ABAS, ABA_MODERACAO] : ABAS;
  // As cinco abas do desenho têm tela. "objetivo" e "avisos" ficaram meses
  // caindo aqui em "conta" por não terem uma — era por isso que a pessoa
  // clicava e nada mudava.
  const tab: SettingsTab = TABS.some((entrada) => entrada.value === state.settingsTab)
    ? state.settingsTab
    : "conta";

  return (
    <div style={{ maxWidth: 900, ...SCREEN_IN }}>
      <h1 style={{ fontSize: 28, margin: "0 0 5.6px" }}>Configurações</h1>
      <p
        style={{
          margin: "0 0 16.8px",
          fontSize: 13.5,
          color: "rgba(233,233,237,.6)",
          maxWidth: "62ch",
        }}
      >
        Conta, objetivo de estudo, competências, idiomas, avisos e o status das integrações. Tudo o que muda aqui recalcula o plano na próxima geração.
      </p>

      <div
        role="tablist"
        aria-label="Seções das configurações"
        style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginBottom: 16.8 }}
      >
        {TABS.map((entry) => (
          <Chip
            key={entry.value}
            icon={entry.icon}
            active={tab === entry.value}
            onClick={() => dispatch({ type: "setSettingsTab", tab: entry.value })}
            style={{ borderRadius: 8, fontSize: 13 }}
          >
            {entry.label}
          </Chip>
        ))}
      </div>

      {tab === "conta" ? <AccountTab /> : null}
      {tab === "objetivo" ? <ObjectiveTab /> : null}
      {tab === "skills" ? <SkillsTab /> : null}
      {tab === "idiomas" ? <LanguageSettings /> : null}
      {tab === "avisos" ? <NoticesTab /> : null}
      {tab === "integracoes" ? <ApiStatusTab /> : null}
      {/* Contas primeiro (só o super admin), relatos depois (quem modera). */}
      {tab === "moderacao" && user?.is_super_admin ? <ModeracaoUsuarios /> : null}
      {tab === "moderacao" && user?.is_moderator ? <ModeracaoRelatos /> : null}

      {/* Em aba nova: o documento é longo, e voltar dele não deve custar a
          posição em que a pessoa estava nas configurações. */}
      <nav
        aria-label="Documentos legais"
        style={{ margin: "28px 0 0", display: "flex", flexWrap: "wrap", gap: "6px 16px", fontSize: 12.5 }}
      >
        {[
          ["/termos", "Termos de uso"],
          ["/privacidade", "Política de privacidade"],
          ["/seguranca", "Segurança"],
        ].map(([href, rotulo]) => (
          <a key={href} href={href} target="_blank" rel="noopener" style={{ color: "rgba(233,233,237,.6)" }}>
            {rotulo}
          </a>
        ))}
      </nav>

      {/* A licença dos ícones (CC BY 4.0) pede crédito visível — um
          comentário no código não conta, porque quem usa o app nunca o lê. */}
      <p style={{ margin: "12px 0 0", fontSize: 11.5, color: "rgba(233,233,237,.4)" }}>
        Ícones:{" "}
        <a
          href="https://github.com/krystonschwarze/coolicons"
          target="_blank"
          rel="noreferrer noopener"
          style={{ color: "inherit" }}
        >
          coolicons
        </a>
        , de Kryston Schwarze, sob{" "}
        <a
          href="https://creativecommons.org/licenses/by/4.0/deed.pt-br"
          target="_blank"
          rel="noreferrer noopener"
          style={{ color: "inherit" }}
        >
          CC BY 4.0
        </a>
        ; chama e medalha do{" "}
        <a href="https://lucide.dev" target="_blank" rel="noreferrer noopener" style={{ color: "inherit" }}>
          Lucide
        </a>
        , sob licença ISC.
      </p>
    </div>
  );
}
