/**
 * Os primeiros passos no PathR, na ordem em que um libera o outro — e se cada
 * um já foi feito, olhando os dados de verdade da pessoa.
 *
 * A ordem não é enfeite: o objetivo e as skills são o que o roadmap, os
 * cursos e as vagas usam. Quem gera o roadmap antes de dizer o que já sabe
 * recebe um plano que ensina o que ela já domina. Cada passo diz o que passa a
 * aparecer depois dele ("em seguida, X aparece aqui").
 *
 * Usado pelo Manual de bordo e pelo card "Primeiros passos" do Início.
 */

import { languages, profile, resumes, roadmap, social, tags } from "@/api/endpoints";
import { useQuery } from "@/hooks/useApi";
import { useT } from "@/lib/i18n";
import type { Screen, SettingsTab } from "@/types";

export interface Passo {
  id: string;
  titulo: string;
  onde: string;
  oQueFazer: string;
  depois: string;
  opcional?: boolean;
  /** null enquanto os dados carregam. */
  feito: boolean | null;
  destino: { screen: Screen; settingsTab?: SettingsTab };
}

const CATEGORIAS_FORA = new Set(["idioma", "dominio"]);

function estado<T>(consulta: { loading: boolean; data: T | null }, teste: (dado: T) => boolean): boolean | null {
  if (consulta.loading) return null;
  return consulta.data ? teste(consulta.data) : false;
}

export function usePrimeirosPassos(): { passos: Passo[]; feitos: number; obrigatorios: number; carregando: boolean } {
  const t = useT();
  const perfil = useQuery(() => profile.get(), []);
  const minhas = useQuery(() => tags.mine(), []);
  const curriculos = useQuery(() => resumes.list(), []);
  const plano = useQuery(() => roadmap.current(), []);
  const idioma = useQuery(() => languages.profile(), []);
  const amizades = useQuery(() => social.amigos(), []);

  const passos: Passo[] = [
    {
      id: "regiao",
      titulo: t("manual.passos.regiao.titulo"),
      onde: t("manual.passos.regiao.onde"),
      oQueFazer: t("manual.passos.regiao.oQueFazer"),
      depois: t("manual.passos.regiao.depois"),
      feito: estado(perfil, (p) => Boolean(p.city)),
      destino: { screen: "config", settingsTab: "objetivo" },
    },
    {
      id: "objetivo",
      titulo: t("manual.passos.objetivo.titulo"),
      onde: t("manual.passos.objetivo.onde"),
      oQueFazer: t("manual.passos.objetivo.oQueFazer"),
      depois: t("manual.passos.objetivo.depois"),
      feito: estado(perfil, (p) => Boolean(p.target_role) || (p.goals ?? []).length > 0),
      destino: { screen: "config", settingsTab: "objetivo" },
    },
    {
      id: "curriculo",
      titulo: t("manual.passos.curriculo.titulo"),
      onde: t("manual.passos.curriculo.onde"),
      oQueFazer: t("manual.passos.curriculo.oQueFazer"),
      depois: t("manual.passos.curriculo.depois"),
      opcional: true,
      feito: estado(curriculos, (lista) => lista.length > 0),
      destino: { screen: "cv" },
    },
    {
      id: "skills",
      titulo: t("manual.passos.skills.titulo"),
      onde: t("manual.passos.skills.onde"),
      oQueFazer: t("manual.passos.skills.oQueFazer"),
      depois: t("manual.passos.skills.depois"),
      feito: estado(minhas, (lista) => lista.some((tag) => !CATEGORIAS_FORA.has(tag.category))),
      destino: { screen: "config", settingsTab: "skills" },
    },
    {
      id: "roadmap",
      titulo: t("manual.passos.roadmap.titulo"),
      onde: t("manual.passos.roadmap.onde"),
      oQueFazer: t("manual.passos.roadmap.oQueFazer"),
      depois: t("manual.passos.roadmap.depois"),
      feito: plano.loading ? null : Boolean(plano.data),
      destino: { screen: "roadmap" },
    },
    {
      id: "idioma",
      titulo: t("manual.passos.idioma.titulo"),
      onde: t("manual.passos.idioma.onde"),
      oQueFazer: t("manual.passos.idioma.oQueFazer"),
      depois: t("manual.passos.idioma.depois"),
      opcional: true,
      feito: estado(idioma, (p) => Boolean(p.cefr_level)),
      destino: { screen: "ingles" },
    },
    {
      id: "amigos",
      titulo: t("manual.passos.amigos.titulo"),
      onde: t("manual.passos.amigos.onde"),
      oQueFazer: t("manual.passos.amigos.oQueFazer"),
      depois: t("manual.passos.amigos.depois"),
      opcional: true,
      feito: estado(amizades, (a) => a.amigos.length > 0),
      destino: { screen: "amigos" },
    },
  ];

  const obrigatorios = passos.filter((p) => !p.opcional);
  return {
    passos,
    feitos: obrigatorios.filter((p) => p.feito).length,
    obrigatorios: obrigatorios.length,
    carregando: passos.some((p) => p.feito === null),
  };
}
