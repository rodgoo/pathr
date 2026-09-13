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
import { ACC4, TEXT } from "@/lib/tokens";
import type { Screen, SettingsTab } from "@/types";
import { PrimeirosPassos } from "@/components/manual/PrimeirosPassos";
import { Icon, type IconName } from "@/components/ui/icons";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";

interface Area {
  nome: string;
  icone: IconName;
  destino: { screen: Screen; settingsTab?: SettingsTab };
  oQueFaz: string;
  precisaDe?: string;
}

const AREAS: { grupo: string; itens: Area[] }[] = [
  {
    grupo: "Estudar",
    itens: [
      {
        nome: "Início",
        icone: "home",
        destino: { screen: "home" },
        oQueFaz: "Seu painel do dia: o módulo para continuar, a lista da semana, a sequência de dias e o mapa de constância.",
        precisaDe: "Um roadmap gerado para mostrar o que continuar.",
      },
      {
        nome: "Roadmap",
        icone: "road",
        destino: { screen: "roadmap" },
        oQueFaz: "O plano inteiro em fases e módulos, com as horas de cada um. Toda semana ele se reajusta pelo que você fez (Ajustes de rota).",
        precisaDe: "Objetivo e skills preenchidos antes de gerar.",
      },
      {
        nome: "Trilha atual",
        icone: "book",
        destino: { screen: "modulo" },
        oQueFaz: "O módulo em que você está: material para estudar, quiz para provar o que aprendeu e atividade prática.",
        precisaDe: "Um roadmap gerado.",
      },
      {
        nome: "Laboratório de código",
        icone: "code",
        destino: { screen: "codigo" },
        oQueFaz: "Exemplos de código percorridos linha a linha, com o valor das variáveis a cada passo. Sugere exemplos pelo seu roadmap e nível.",
        precisaDe: "Linguagens marcadas em Skills.",
      },
      {
        nome: "Idiomas",
        icone: "flag",
        destino: { screen: "ingles" },
        oQueFaz: "Nivelamento de inglês (A1 a C2), treino diário no seu nível e tradução de palavras com um toque.",
      },
    ],
  },
  {
    grupo: "Carreira",
    itens: [
      {
        nome: "Cursos",
        icone: "award",
        destino: { screen: "cursos" },
        oQueFaz: "Cursos com certificado para o LinkedIn, gratuitos primeiro, com o quanto o assunto é procurado. Marque \"já possuo\" para aparecer no seu perfil.",
        precisaDe: "Metas marcadas em Skills ou um objetivo.",
      },
      {
        nome: "Vagas",
        icone: "suitcase",
        destino: { screen: "vagas" },
        oQueFaz: "Vagas reais na sua região ou remotas, da que mais combina com você para a que menos, com o que falta para cada uma e cursos para chegar lá.",
        precisaDe: "Skills marcadas e a cidade em Configurações › Objetivo.",
      },
      {
        nome: "Currículo",
        icone: "file",
        destino: { screen: "cv" },
        oQueFaz: "Envie o currículo: a IA lê e sugere suas tecnologias com nível, para você revisar e importar.",
      },
      {
        nome: "Perfil e tags",
        icone: "user",
        destino: { screen: "perfil" },
        oQueFaz: "O resumo de quem você é no app: o que domina, o que está aprendendo, o que quer aprender e seus certificados.",
      },
    ],
  },
  {
    grupo: "Pessoas",
    itens: [
      {
        nome: "Amigos",
        icone: "users",
        destino: { screen: "amigos" },
        oQueFaz: "Convites, sugestões de quem mora perto ou estuda o mesmo, e a sequência de estudos em dupla — com card para compartilhar aos 7, 30, 60 e 90 dias.",
        precisaDe: "Um @ (escolhido no cadastro, editável em Configurações › Conta).",
      },
      {
        nome: "Relatar",
        icone: "flag",
        destino: { screen: "relatar" },
        oQueFaz: "Mande uma reclamação ou sugestão, com foto se quiser, e acompanhe a resposta da moderação.",
      },
    ],
  },
  {
    grupo: "Configurações",
    itens: [
      {
        nome: "Conta",
        icone: "cog",
        destino: { screen: "config", settingsTab: "conta" },
        oQueFaz: "Nome, @, foto, senha, chave de acesso (passkey) e segundo fator.",
      },
      {
        nome: "Objetivo",
        icone: "flag",
        destino: { screen: "config", settingsTab: "objetivo" },
        oQueFaz: "Onde você quer chegar, as horas por semana e a região das vagas (cidade e raio em km).",
      },
      {
        nome: "Skills",
        icone: "code",
        destino: { screen: "config", settingsTab: "skills" },
        oQueFaz: "As tecnologias do seu plano e o nível de cada uma, de N0 (quero aprender) a N5 (especialista).",
      },
      {
        nome: "Avisos e privacidade",
        icone: "mail",
        destino: { screen: "config", settingsTab: "avisos" },
        oQueFaz: "Quais e-mails receber, se aparece nas sugestões de amigos, exportar todos os seus dados ou excluir a conta.",
      },
      {
        nome: "Integrações",
        icone: "server",
        destino: { screen: "config", settingsTab: "integracoes" },
        oQueFaz: "O estado dos serviços que o app usa (IA, vagas, tradução, e-mail) — útil quando algo parece fora do ar.",
      },
    ],
  },
];

export function ManualPage() {
  const { dispatch } = useAppState();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16.8, ...SCREEN_IN }}>
      <header>
        <Kicker style={{ display: "block", marginBottom: 5.6 }}>Manual de bordo</Kicker>
        <h1 style={{ fontSize: 26, margin: 0 }}>Como o PathR funciona</h1>
        <p style={{ margin: "8.4px 0 0", fontSize: 13.5, color: TEXT.strong, maxWidth: "72ch", lineHeight: 1.55 }}>
          O PathR monta um plano de estudos do que você já sabe até onde quer chegar, e em volta dele junta cursos com
          certificado, vagas que combinam com você, idiomas e pessoas para estudar junto. Quase tudo depende de duas
          coisas que só você pode dizer: <strong>o seu objetivo</strong> e <strong>as suas skills com o nível</strong>.
          Comece por elas.
        </p>
      </header>

      <PrimeirosPassos />

      {AREAS.map((grupo) => (
        <section key={grupo.grupo} aria-label={grupo.grupo} style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
          <Kicker>{grupo.grupo}</Kicker>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 280px), 1fr))", gap: 8.4 }}>
            {grupo.itens.map((area) => (
              <Panel key={area.nome} pad={14} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Icon name={area.icone} size={16} style={{ color: ACC4 }} />
                  <span style={{ fontSize: 14, color: TEXT.full }}>{area.nome}</span>
                </div>
                <p style={{ margin: 0, fontSize: 12.5, color: TEXT.strong, lineHeight: 1.5 }}>{area.oQueFaz}</p>
                {area.precisaDe ? (
                  <p style={{ margin: 0, fontSize: 12, color: TEXT.muted }}>
                    <span style={{ color: TEXT.faint }}>Precisa de: </span>
                    {area.precisaDe}
                  </p>
                ) : null}
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ alignSelf: "flex-start", fontSize: 12, marginTop: "auto" }}
                  onClick={() => dispatch({ type: "navigate", screen: area.destino.screen, settingsTab: area.destino.settingsTab })}
                >
                  Abrir {area.nome}
                  <Icon name="arrowRight" size={14} />
                </button>
              </Panel>
            ))}
          </div>
        </section>
      ))}

      <p style={{ margin: 0, fontSize: 12, color: TEXT.faint }}>
        Termos de uso, privacidade e segurança ficam em pathr.notter.com.br/termos, /privacidade e /seguranca.
      </p>
    </div>
  );
}
