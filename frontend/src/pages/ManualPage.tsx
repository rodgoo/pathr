/**
 * Manual de bordo: o que é o PathR, por onde começar, e onde fica cada coisa.
 *
 * Duas partes. Os primeiros passos, em ordem e com o que já foi feito
 * marcado, porque um recurso depende do outro (sem skills, Cursos e Vagas não
 * têm o que sugerir). E o mapa das telas: o que cada uma faz, onde fica, e o
 * que precisa existir antes para ela mostrar alguma coisa.
 *
 * O texto descreve o app como ele é hoje. Ao mudar uma tela, mude aqui.
 */

import { useAppState } from "@/hooks/useAppState";
import { useT } from "@/lib/i18n";
import { ACC4, TEXT } from "@/lib/tokens";
import type { Screen, SettingsTab } from "@/types";
import { PrimeirosPassos } from "@/components/manual/PrimeirosPassos";
import { Icon, type IconName } from "@/components/ui/icons";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";

/** Cada campo de texto guarda a CHAVE de tradução, resolvida no render com
 * `t()`; ícone e destino não mudam com o idioma. */
interface Area {
  id: string;
  nomeChave: string;
  icone: IconName;
  destino: { screen: Screen; settingsTab?: SettingsTab };
  oQueFazChave: string;
  precisaDeChave?: string;
}

const AREAS: { grupoChave: string; itens: Area[] }[] = [
  {
    grupoChave: "manual.grupos.estudar",
    itens: [
      {
        id: "inicio",
        nomeChave: "manual.areas.inicio.nome",
        icone: "home",
        destino: { screen: "home" },
        oQueFazChave: "manual.areas.inicio.oQueFaz",
        precisaDeChave: "manual.areas.inicio.precisaDe",
      },
      {
        id: "roadmap",
        nomeChave: "manual.areas.roadmap.nome",
        icone: "road",
        destino: { screen: "roadmap" },
        oQueFazChave: "manual.areas.roadmap.oQueFaz",
        precisaDeChave: "manual.areas.roadmap.precisaDe",
      },
      {
        id: "trilha",
        nomeChave: "manual.areas.trilha.nome",
        icone: "book",
        destino: { screen: "modulo" },
        oQueFazChave: "manual.areas.trilha.oQueFaz",
        precisaDeChave: "manual.areas.trilha.precisaDe",
      },
      {
        id: "laboratorio",
        nomeChave: "manual.areas.laboratorio.nome",
        icone: "code",
        destino: { screen: "codigo" },
        oQueFazChave: "manual.areas.laboratorio.oQueFaz",
        precisaDeChave: "manual.areas.laboratorio.precisaDe",
      },
      {
        id: "idiomas",
        nomeChave: "manual.areas.idiomas.nome",
        icone: "flag",
        destino: { screen: "ingles" },
        oQueFazChave: "manual.areas.idiomas.oQueFaz",
      },
    ],
  },
  {
    grupoChave: "manual.grupos.carreira",
    itens: [
      {
        id: "cursos",
        nomeChave: "manual.areas.cursos.nome",
        icone: "award",
        destino: { screen: "cursos" },
        oQueFazChave: "manual.areas.cursos.oQueFaz",
        precisaDeChave: "manual.areas.cursos.precisaDe",
      },
      {
        id: "vagas",
        nomeChave: "manual.areas.vagas.nome",
        icone: "suitcase",
        destino: { screen: "vagas" },
        oQueFazChave: "manual.areas.vagas.oQueFaz",
        precisaDeChave: "manual.areas.vagas.precisaDe",
      },
      {
        id: "curriculo",
        nomeChave: "manual.areas.curriculo.nome",
        icone: "file",
        destino: { screen: "cv" },
        oQueFazChave: "manual.areas.curriculo.oQueFaz",
      },
      {
        id: "perfil",
        nomeChave: "manual.areas.perfil.nome",
        icone: "user",
        destino: { screen: "perfil" },
        oQueFazChave: "manual.areas.perfil.oQueFaz",
      },
    ],
  },
  {
    grupoChave: "manual.grupos.pessoas",
    itens: [
      {
        id: "amigos",
        nomeChave: "manual.areas.amigos.nome",
        icone: "users",
        destino: { screen: "amigos" },
        oQueFazChave: "manual.areas.amigos.oQueFaz",
        precisaDeChave: "manual.areas.amigos.precisaDe",
      },
      {
        id: "relatar",
        nomeChave: "manual.areas.relatar.nome",
        icone: "flag",
        destino: { screen: "relatar" },
        oQueFazChave: "manual.areas.relatar.oQueFaz",
      },
    ],
  },
  {
    grupoChave: "manual.grupos.configuracoes",
    itens: [
      {
        id: "conta",
        nomeChave: "manual.areas.conta.nome",
        icone: "cog",
        destino: { screen: "config", settingsTab: "conta" },
        oQueFazChave: "manual.areas.conta.oQueFaz",
      },
      {
        id: "objetivo",
        nomeChave: "manual.areas.objetivo.nome",
        icone: "flag",
        destino: { screen: "config", settingsTab: "objetivo" },
        oQueFazChave: "manual.areas.objetivo.oQueFaz",
      },
      {
        id: "skills",
        nomeChave: "manual.areas.skills.nome",
        icone: "code",
        destino: { screen: "config", settingsTab: "skills" },
        oQueFazChave: "manual.areas.skills.oQueFaz",
      },
      {
        id: "avisos",
        nomeChave: "manual.areas.avisos.nome",
        icone: "mail",
        destino: { screen: "config", settingsTab: "avisos" },
        oQueFazChave: "manual.areas.avisos.oQueFaz",
      },
      {
        id: "integracoes",
        nomeChave: "manual.areas.integracoes.nome",
        icone: "server",
        destino: { screen: "config", settingsTab: "integracoes" },
        oQueFazChave: "manual.areas.integracoes.oQueFaz",
      },
    ],
  },
];

export function ManualPage() {
  const t = useT();
  const { dispatch } = useAppState();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16.8, ...SCREEN_IN }}>
      <header>
        <Kicker style={{ display: "block", marginBottom: 5.6 }}>{t("manual.kicker")}</Kicker>
        <h1 style={{ fontSize: 26, margin: 0 }}>{t("manual.titulo")}</h1>
        <p style={{ margin: "8.4px 0 0", fontSize: 13.5, color: TEXT.strong, maxWidth: "72ch", lineHeight: 1.55 }}>
          {t("manual.intro.p1")}
          <strong>{t("manual.intro.objetivo")}</strong>
          {t("manual.intro.e")}
          <strong>{t("manual.intro.skills")}</strong>
          {t("manual.intro.p2")}
        </p>
      </header>

      <PrimeirosPassos />

      {AREAS.map((grupo) => (
        <section key={grupo.grupoChave} aria-label={t(grupo.grupoChave)} style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
          <Kicker>{t(grupo.grupoChave)}</Kicker>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 280px), 1fr))", gap: 8.4 }}>
            {grupo.itens.map((area) => (
              <Panel key={area.id} pad={14} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Icon name={area.icone} size={16} style={{ color: ACC4 }} />
                  <span style={{ fontSize: 14, color: TEXT.full }}>{t(area.nomeChave)}</span>
                </div>
                <p style={{ margin: 0, fontSize: 12.5, color: TEXT.strong, lineHeight: 1.5 }}>{t(area.oQueFazChave)}</p>
                {area.precisaDeChave ? (
                  <p style={{ margin: 0, fontSize: 12, color: TEXT.muted }}>
                    <span style={{ color: TEXT.faint }}>{t("manual.precisaDe")} </span>
                    {t(area.precisaDeChave)}
                  </p>
                ) : null}
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ alignSelf: "flex-start", fontSize: 12, marginTop: "auto" }}
                  onClick={() => dispatch({ type: "navigate", screen: area.destino.screen, settingsTab: area.destino.settingsTab })}
                >
                  {t("manual.abrir", { nome: t(area.nomeChave) })}
                  <Icon name="arrowRight" size={14} />
                </button>
              </Panel>
            ))}
          </div>
        </section>
      ))}

      <p style={{ margin: 0, fontSize: 12, color: TEXT.faint }}>
        {t("manual.termos")}
      </p>
    </div>
  );
}
