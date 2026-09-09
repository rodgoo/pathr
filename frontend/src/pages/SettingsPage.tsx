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
import { SCREEN_IN } from "@/components/ui/primitives";
import { LanguageSettings } from "@/components/english/LanguageSettings";
import { AccountTab } from "@/components/profile/AccountTab";
import { NoticesTab } from "@/components/profile/NoticesTab";
import { ObjectiveTab } from "@/components/profile/ObjectiveTab";
import { SkillsTab } from "@/components/profile/SkillsTab";

const TABS: readonly { value: SettingsTab; label: string }[] = [
  { value: "conta", label: "Conta" },
  { value: "objetivo", label: "Objetivo" },
  { value: "skills", label: "Skills" },
  { value: "idiomas", label: "Idiomas" },
  { value: "avisos", label: "Avisos e privacidade" },
];

export function SettingsPage() {
  const { state, dispatch } = useAppState();
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
        Conta, objetivo de estudo, competências, idiomas e avisos. Tudo o que muda aqui recalcula o plano na próxima geração.
      </p>

      <div
        role="tablist"
        aria-label="Seções das configurações"
        style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginBottom: 16.8 }}
      >
        {TABS.map((entry) => (
          <Chip
            key={entry.value}
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
    </div>
  );
}
