/**
 * O aria-label dos "últimos N dias" dos KpiCards precisa passar por i18n.
 *
 * Era texto fixo em português (`Últimos ${n} dias`), enquanto o aria-label
 * vizinho e o resto do arquivo já passavam por `t()`. Numa conta configurada
 * para outro idioma, leitores de tela anunciavam esse grupo em português no
 * meio de uma tela traduzida.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KpiCards } from "@/components/dashboard/KpiCards";
import { IdiomaProvider } from "@/lib/i18n";
import type { Overview } from "@/api/types";

const overview: Overview = {
  profile: {
    user_id: "user-1",
    headline: null,
    current_role: "Desenvolvedor frontend",
    target_role: null,
    seniority: "pleno",
    years_experience: 3,
    weekly_hours: 8,
    learning_style: null,
    goals: [],
    bio: null,
    linkedin_url: null,
    github_url: null,
  },
  streak: { current: 3, longest: 12, last_active_date: "2026-09-09", total_xp: 240, total_minutes: 480 },
  english: { enabled: true, cefr_level: "B1", target_level: "B2" },
  roadmap: null,
  activity: { days: [], active_days: 0, total_minutes: 480, total_xp: 240 },
};

describe("KpiCards: aria-label traduzido", () => {
  it("em inglês, o grupo dos últimos dias anuncia em inglês, não em português", async () => {
    render(
      <IdiomaProvider idioma="en">
        <KpiCards overview={overview} />
      </IdiomaProvider>,
    );

    // O dicionário de outro idioma carrega de forma assíncrona (import
    // dinâmico); até ele chegar, a tela mostra o português de reserva.
    expect((await screen.findAllByRole("group", { name: /Last \d+ days/ })).length).toBeGreaterThan(0);
    expect(screen.queryByRole("group", { name: /Últimos \d+ dias/ })).not.toBeInTheDocument();
  });
});
