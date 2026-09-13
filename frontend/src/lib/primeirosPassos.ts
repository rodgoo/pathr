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
  const perfil = useQuery(() => profile.get(), []);
  const minhas = useQuery(() => tags.mine(), []);
  const curriculos = useQuery(() => resumes.list(), []);
  const plano = useQuery(() => roadmap.current(), []);
  const idioma = useQuery(() => languages.profile(), []);
  const amizades = useQuery(() => social.amigos(), []);

  const passos: Passo[] = [
    {
      id: "regiao",
      titulo: "Diga onde você mora",
      onde: "Configurações › Objetivo › Região e abrangência das vagas",
      oQueFazer: "Escolha sua cidade e até quantos km você aceita ir para uma vaga presencial.",
      depois: "Vagas passa a mostrar só presenciais no seu raio (remotas sempre), e o seu dia de estudo segue o seu fuso.",
      feito: estado(perfil, (p) => Boolean(p.city)),
      destino: { screen: "config", settingsTab: "objetivo" },
    },
    {
      id: "objetivo",
      titulo: "Escolha o seu objetivo",
      onde: "Configurações › Objetivo",
      oQueFazer: "Escolha um destino pronto ou descreva em texto livre onde quer chegar, e as horas por semana.",
      depois: "O roadmap é montado para esse destino, e Vagas e Cursos priorizam o que ele pede.",
      feito: estado(perfil, (p) => Boolean(p.target_role) || (p.goals ?? []).length > 0),
      destino: { screen: "config", settingsTab: "objetivo" },
    },
    {
      id: "curriculo",
      titulo: "Envie seu currículo",
      onde: "Currículo",
      oQueFazer: "Suba o PDF ou DOCX: a IA lê e sugere suas tecnologias com um nível estimado, para você revisar.",
      depois: "As skills chegam preenchidas no passo seguinte — você só confere os níveis.",
      opcional: true,
      feito: estado(curriculos, (lista) => lista.length > 0),
      destino: { screen: "cv" },
    },
    {
      id: "skills",
      titulo: "Marque suas skills e os níveis",
      onde: "Configurações › Skills",
      oQueFazer: "Marque as tecnologias do seu plano e o nível de cada uma (N0 = quero aprender … N5 = especialista).",
      depois: "Cursos passa a sugerir certificados, Vagas compara sua stack, e o Laboratório mostra as suas linguagens.",
      feito: estado(minhas, (lista) => lista.some((t) => !CATEGORIAS_FORA.has(t.category))),
      destino: { screen: "config", settingsTab: "skills" },
    },
    {
      id: "roadmap",
      titulo: "Gere o seu roadmap",
      onde: "Roadmap",
      oQueFazer: "Gere o plano: fases e módulos do que você sabe até o objetivo, no seu ritmo semanal.",
      depois: "Aparecem a Trilha atual, a lista da semana e o progresso no Início, e o plano se reajusta toda semana.",
      feito: plano.loading ? null : Boolean(plano.data),
      destino: { screen: "roadmap" },
    },
    {
      id: "idioma",
      titulo: "Faça o nivelamento de inglês",
      onde: "Idiomas",
      oQueFazer: "Responda o teste de nível: ele mede o seu CEFR (A1 a C2) de verdade.",
      depois: "Vagas compara o inglês pedido com o seu, e os treinos diários ficam no seu nível.",
      opcional: true,
      feito: estado(idioma, (p) => Boolean(p.cefr_level)),
      destino: { screen: "ingles" },
    },
    {
      id: "amigos",
      titulo: "Adicione amigos",
      onde: "Amigos",
      oQueFazer: "Procure pelo @ ou veja as sugestões de quem mora perto ou estuda o mesmo que você.",
      depois: "Estudando no mesmo dia, vocês formam uma sequência juntos — com card para compartilhar a cada marco.",
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
