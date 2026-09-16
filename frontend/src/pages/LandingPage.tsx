/**
 * A apresentação do PathR, para quem ainda não tem conta.
 *
 * As telas de exemplo NÃO são imagens: são os componentes de verdade do app,
 * alimentados com dados de exemplo. Uma captura de tela envelhece no primeiro
 * ajuste de cor e passa a mostrar um produto que não existe mais; o componente
 * é o próprio produto, e muda junto.
 *
 * ## Dá para mexer — sem tocar na API
 *
 * O visitante passa o mouse no mapa do ano, marca módulos da trilha, troca a
 * linguagem do laboratório, toca nas palavras do inglês e adiciona as pessoas
 * de exemplo. Tudo isso é estado local desta página: nenhum componente aqui
 * chama o servidor. O cartão de pessoa vai com `somenteLeitura` + `onDemo` —
 * os botões respondem, mas o que muda é só a tela.
 *
 * ## Rolagem
 *
 * Cada seção entra com um fade curto quando chega à tela (IntersectionObserver),
 * e as âncoras do topo rolam suavemente. Com `prefers-reduced-motion`, nada se
 * move: tudo aparece de uma vez.
 *
 * ## Idioma
 *
 * Todo texto desta página sai de `t("landing.…")`, e o seletor flutuante no
 * canto inferior direito deixa o visitante trocar de idioma antes de criar
 * conta. O que fica em código é o que não se traduz: nomes de tecnologia, as
 * linhas dos exemplos e a frase em inglês do treino de idiomas.
 */

import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { ActivitySummary, Overview } from "@/api/types";
import { ConsistencyPanel } from "@/components/dashboard/ConsistencyPanel";
import { KpiCards } from "@/components/dashboard/KpiCards";
import { CartaoPessoa, type AcaoDeAmizade } from "@/components/social/CartaoPessoa";
import { Icon, type IconName } from "@/components/ui/icons";
import { Logo } from "@/components/ui/Logo";
import { Select } from "@/components/ui/Select";
import { SeletorDeIdioma } from "@/components/ui/SeletorDeIdioma";
import { pessoasDeExemplo } from "@/lib/lugaresDeExemplo";
import { useIdioma, useT, type Traduzir } from "@/lib/i18n";
import { iconeDaLinguagem } from "@/lib/linguagens";
import { isoLocal } from "@/lib/dashboard";
import { ACC, ACC3, ACC4, BG, C, HAIRLINE, PANEL, TEXT, tint } from "@/lib/tokens";

type Navegar = (path: string) => void;

// ---------------------------------------------------------------------------
// Dados de exemplo
// ---------------------------------------------------------------------------

/**
 * Um ano de estudo plausível até hoje: mais dias com estudo do que sem, com
 * buracos de verdade (fins de semana, uma semana parada no meio do ano).
 *
 * Determinístico — a mesma tela a cada visita — e espalhado pelo ano inteiro:
 * com só as últimas semanas, o mapa do ano de exemplo aparecia quase vazio.
 */
function atividadeDeExemplo(t: Traduzir): ActivitySummary {
  const hoje = new Date();
  const titulos: [string, string][] = [
    ["article", t("landing.atividade.artigoSpring")],
    ["video", t("landing.atividade.videoJpa")],
    ["doc", t("landing.atividade.docDocker")],
    ["article", t("landing.atividade.artigoTestes")],
  ];
  const dias: ActivitySummary["days"] = [];
  const inicio = new Date(hoje.getFullYear(), 0, 1);
  for (let data = new Date(inicio); data <= hoje; data.setDate(data.getDate() + 1)) {
    const n = Math.floor((data.getTime() - inicio.getTime()) / 86_400_000);
    // Pseudoaleatório estável a partir do número do dia.
    const sorteio = Math.abs(Math.sin(n * 12.9898) * 43758.5453) % 1;
    const fimDeSemana = data.getDay() === 0 || data.getDay() === 6;
    const semanaParada = n >= 120 && n < 128;
    if (semanaParada || sorteio < (fimDeSemana ? 0.7 : 0.3)) continue;
    const minutos = 15 + Math.round(sorteio * 90);
    const [kind, title] = titulos[n % titulos.length];
    dias.push({
      date: isoLocal(data),
      minutes: minutos,
      count: 2,
      xp: 35,
      items: [
        { kind: "resource_done", resource_kind: kind, title, minutes: Math.round(minutos * 0.6) },
        { kind: "quiz_done", title: t("landing.atividade.quiz"), minutes: Math.round(minutos * 0.4) },
      ],
    });
  }
  return {
    days: dias,
    active_days: dias.length,
    total_minutes: dias.reduce((soma, dia) => soma + dia.minutes, 0),
    total_xp: dias.length * 35,
  };
}

function panoramaDeExemplo(atividade: ActivitySummary, feitos: number, total: number): Overview {
  return {
    streak: { current: 4, longest: 9, last_active_date: isoLocal(new Date()), total_xp: 1240, total_minutes: atividade.total_minutes },
    english: { enabled: true, cefr_level: "B1", target_level: "B2" },
    roadmap: { progress_pct: Math.round((feitos / total) * 100), done_nodes: feitos, total_nodes: total },
    activity: atividade,
  } as unknown as Overview;
}


/** A trilha de exemplo: 19 módulos no total, e estes cinco são a fase atual. */
const TOTAL_DE_MODULOS = 19;
const FEITOS_ANTES = 4;
/** Cada módulo guarda só a duração e a chave do texto — título e tipo vêm do dicionário. */
const MODULOS: { chave: string; minutos: number }[] = [
  { chave: "estrutura", minutos: 90 },
  { chave: "injecao", minutos: 60 },
  { chave: "jpa", minutos: 120 },
  { chave: "testes", minutos: 75 },
  { chave: "docker", minutos: 60 },
];

/** As linhas de código não se traduzem; a explicação de cada uma vem do dicionário. */
const EXEMPLOS: Record<string, { rotulo: string; linhas: string[] }> = {
  java: {
    rotulo: "Java",
    linhas: [
      "List<String> nomes = pessoas.stream()",
      "    .filter(p -> p.idade() >= 18)",
      "    .map(Pessoa::nome)",
      "    .toList();",
    ],
  },
  typescript: {
    rotulo: "TypeScript",
    linhas: [
      "type Vaga = { titulo: string; nota: number };",
      "const resposta = await fetch('/vagas');",
      "const vagas: Vaga[] = await resposta.json();",
      "vagas.sort((a, b) => b.nota - a.nota);",
    ],
  },
  python: {
    rotulo: "Python",
    linhas: [
      "notas = [7.5, 9.0, 4.0, 8.2]",
      "aprovadas = [n for n in notas if n >= 7]",
      "media = sum(aprovadas) / len(aprovadas)",
      "print(f'{media:.1f}')",
    ],
  },
  go: {
    rotulo: "Go",
    linhas: [
      "canal := make(chan int)",
      "go func() { canal <- calcular() }()",
      "resultado := <-canal",
      "fmt.Println(resultado)",
    ],
  },
};

const LINGUAGENS = Object.entries(EXEMPLOS).map(([id, exemplo]) => ({
  value: id,
  label: exemplo.rotulo,
  icon: iconeDaLinguagem(id),
}));

/** A grafia fonética é a mesma em qualquer idioma; tradução e sinônimos vêm do dicionário. */
const PALAVRAS: Record<string, { ipa: string }> = {
  deploy: { ipa: "/dɪˈplɔɪ/" },
  version: { ipa: "/ˈvɜːrʒən/" },
  team: { ipa: "/tiːm/" },
  Friday: { ipa: "/ˈfraɪdeɪ/" },
};

// ---------------------------------------------------------------------------
// Movimento
// ---------------------------------------------------------------------------

function querMenosMovimento(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Entra com um fade curto quando chega à tela. Sem IntersectionObserver (jsdom,
 * navegador antigo) ou com movimento reduzido, aparece direto: o conteúdo
 * nunca depende da animação para ser visto.
 */
function Revelar({ children, atraso = 0 }: { children: ReactNode; atraso?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const semAnimacao = typeof IntersectionObserver === "undefined" || querMenosMovimento();
  const [visivel, setVisivel] = useState(semAnimacao);

  useEffect(() => {
    if (visivel || !ref.current) return undefined;
    const observador = new IntersectionObserver(
      (entradas) => {
        if (entradas.some((e) => e.isIntersecting)) {
          setVisivel(true);
          observador.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
    observador.observe(ref.current);
    return () => observador.disconnect();
  }, [visivel]);

  const curva = "cubic-bezier(.2,.7,.2,1)";
  return (
    <div
      ref={ref}
      style={{
        opacity: visivel ? 1 : 0,
        transform: visivel ? "none" : "translateY(28px)",
        transition: semAnimacao ? undefined : `opacity .7s ${curva} ${atraso}ms, transform .7s ${curva} ${atraso}ms`,
        height: "100%",
      }}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Peças
// ---------------------------------------------------------------------------

/**
 * Uma tela de exemplo numa moldura de janela.
 *
 * `interativa`: responde a mouse e teclado (estado local). Sem ela, a prévia é
 * `inert` — aparece inteira, mas fora do alcance de clique e do leitor de tela
 * como controle.
 */
function Janela({
  titulo, descricao, interativa = false, children,
}: { titulo: string; descricao: string; interativa?: boolean; children: ReactNode }) {
  const t = useT();
  const corpo = interativa ? {} : ({ inert: "" } as Record<string, string>);
  return (
    <figure
      aria-label={descricao}
      className="lp-janela"
      style={{
        margin: 0,
        borderRadius: 16,
        background: PANEL,
        boxShadow: `0 24px 60px rgba(0,0,0,.6), 0 0 0 1px ${HAIRLINE}`,
        overflow: "hidden",
        minWidth: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "10px 14px", borderBottom: `1px solid ${HAIRLINE}` }}>
        {["#e5484d", "#f5a524", "#46a758"].map((cor) => (
          <span key={cor} aria-hidden style={{ width: 9, height: 9, borderRadius: "50%", background: cor, opacity: 0.55, flex: "none" }} />
        ))}
        <span style={{ marginLeft: 10, fontSize: 11.5, color: TEXT.faint, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {titulo}
        </span>
        {interativa ? (
          <span
            style={{
              marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 5, flex: "none",
              fontSize: 11, color: C.verde, padding: "2px 8px", borderRadius: 999, background: tint(C.verde, 12),
            }}
          >
            <span aria-hidden className="lp-pulso" style={{ width: 6, height: 6, borderRadius: "50%", background: C.verde }} />
            {t("landing.janela.experimente")}
          </span>
        ) : null}
      </div>
      <div {...corpo} style={{ padding: 16 }}>
        {children}
      </div>
    </figure>
  );
}

function Rotulo({ children, cor = ACC4 }: { children: ReactNode; cor?: string }) {
  return (
    <div style={{ fontSize: 11.5, letterSpacing: ".14em", textTransform: "uppercase", color: cor, fontWeight: 600 }}>
      {children}
    </div>
  );
}

function Destaque({
  rotulo, titulo, texto, pontos, invertido = false, larga = false, children,
}: {
  rotulo: string; titulo: string; texto: string; pontos: string[]; invertido?: boolean;
  /** Tela embaixo, na largura toda — para o que não cabe em meia coluna (o mapa do ano). */
  larga?: boolean;
  children: ReactNode;
}) {
  return (
    <section
      style={{
        display: "grid",
        gridTemplateColumns: larga ? "minmax(0, 1fr)" : "repeat(auto-fit, minmax(min(100%, 380px), 1fr))",
        gap: "clamp(28px, 5vw, 64px)",
        alignItems: "center",
      }}
    >
      <div style={{ order: invertido ? 2 : 1, minWidth: 0 }}>
        <Revelar>
          <Rotulo>{rotulo}</Rotulo>
          <h2 style={{ fontSize: "clamp(24px, 3vw, 32px)", lineHeight: 1.2, margin: "12px 0 14px", fontWeight: 600, letterSpacing: "-.02em" }}>
            {titulo}
          </h2>
          <p style={{ fontSize: 15.5, lineHeight: 1.7, color: TEXT.muted, margin: 0, maxWidth: "52ch" }}>{texto}</p>
          <ul style={{ listStyle: "none", padding: 0, margin: "18px 0 0", display: "flex", flexDirection: "column", gap: 9 }}>
            {pontos.map((ponto) => (
              <li key={ponto} style={{ display: "flex", gap: 10, fontSize: 14, color: TEXT.strong, lineHeight: 1.5 }}>
                <Icon name="check" size={15} style={{ color: C.verde, flex: "none", marginTop: 2 }} />
                {ponto}
              </li>
            ))}
          </ul>
        </Revelar>
      </div>
      <div style={{ order: invertido ? 1 : 2, minWidth: 0 }}>
        <Revelar atraso={120}>{children}</Revelar>
      </div>
    </section>
  );
}

function irPara(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: querMenosMovimento() ? "auto" : "smooth", block: "start" });
}

function Topo({ onNavigate }: { onNavigate: Navegar }) {
  const t = useT();
  const [rolou, setRolou] = useState(false);
  useEffect(() => {
    const aoRolar = () => setRolou(window.scrollY > 12);
    aoRolar();
    window.addEventListener("scroll", aoRolar, { passive: true });
    return () => window.removeEventListener("scroll", aoRolar);
  }, []);

  return (
    <header
      style={{
        position: "sticky", top: 0, zIndex: 10,
        display: "flex", alignItems: "center", gap: 12,
        padding: "14px clamp(16px, 4vw, 40px)",
        background: rolou ? "rgba(0,0,0,.72)" : "transparent",
        backdropFilter: rolou ? "blur(14px) saturate(140%)" : "none",
        borderBottom: `1px solid ${rolou ? HAIRLINE : "transparent"}`,
        transition: "background .3s, border-color .3s",
      }}
    >
      <Logo size={30} />
      <span style={{ fontSize: 17, fontWeight: 600 }}>PathR</span>
      <nav aria-label={t("landing.topo.navSecoes")} className="lp-secoes" style={{ marginLeft: 28, display: "flex", gap: 4 }}>
        {[["como-funciona", t("landing.topo.comoFunciona")], ["recursos", t("landing.topo.recursos")], ["cuidados", t("landing.topo.seguranca")]].map(([id, rotulo]) => (
          <a key={id} href={`#${id}`} className="btn btn-ghost" style={{ color: TEXT.muted, fontSize: 13.5 }}
            onClick={(e) => { e.preventDefault(); irPara(id); }}>
            {rotulo}
          </a>
        ))}
      </nav>
      <nav aria-label={t("landing.topo.navConta")} style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
        <a href="/entrar" className="btn btn-ghost" onClick={(e) => { e.preventDefault(); onNavigate("/entrar"); }}>
          {t("landing.topo.entrar")}
        </a>
        <a href="/cadastro" className="btn btn-primary" onClick={(e) => { e.preventDefault(); onNavigate("/cadastro"); }}>
          {t("landing.topo.criarConta")}
        </a>
      </nav>
    </header>
  );
}

const TOM_ACC = { "--tom": ACC } as CSSProperties;

function Heroi({ onNavigate, panorama }: { onNavigate: Navegar; panorama: Overview }) {
  const t = useT();
  return (
    <section style={{ textAlign: "center", paddingTop: "clamp(40px, 8vw, 96px)" }}>
      <Revelar>
        <div
          style={{
            display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 14px", borderRadius: 999,
            background: tint(ACC, 10), boxShadow: `inset 0 0 0 1px ${tint(ACC, 30)}`, fontSize: 12.5, color: ACC3,
          }}
        >
          <Icon name="flame" size={14} style={{ color: C.ambar }} />
          {t("landing.hero.selo")}
        </div>
        <h1
          style={{
            fontSize: "clamp(34px, 6vw, 62px)", lineHeight: 1.05, letterSpacing: "-.035em",
            fontWeight: 650, margin: "20px auto 20px", maxWidth: "16ch",
          }}
        >
          {t("landing.hero.titulo")}{" "}
          <span className="lp-gradiente" style={{ backgroundImage: `linear-gradient(90deg, ${ACC4}, ${C.verde}, ${ACC4})`, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
            {t("landing.hero.tituloDestaque")}
          </span>
        </h1>
        <p style={{ fontSize: "clamp(16px, 1.8vw, 19px)", lineHeight: 1.65, color: TEXT.muted, margin: "0 auto", maxWidth: "58ch" }}>
          {t("landing.hero.sub")}
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 10, marginTop: 28 }}>
          <a href="/cadastro" className="btn btn-tom" style={{ ...TOM_ACC, padding: "12px 22px", fontSize: 15 }}
            onClick={(e) => { e.preventDefault(); onNavigate("/cadastro"); }}>
            {t("landing.hero.criarContaGratis")}
            <Icon name="arrowRight" size={16} />
          </a>
          <a href="/entrar" className="btn btn-secondary" style={{ padding: "12px 22px", fontSize: 15 }}
            onClick={(e) => { e.preventDefault(); onNavigate("/entrar"); }}>
            {t("landing.hero.jaTenhoConta")}
          </a>
        </div>
      </Revelar>
      <div style={{ marginTop: "clamp(40px, 7vw, 72px)", textAlign: "left" }}>
        <Revelar atraso={150}>
          <Janela interativa titulo={t("landing.hero.janelaTitulo")} descricao={t("landing.hero.janelaDescricao")}>
            <KpiCards overview={panorama} />
          </Janela>
          <p style={{ textAlign: "center", fontSize: 12.5, color: TEXT.faint, margin: "12px 0 0" }}>
            {t("landing.hero.dica")}
          </p>
        </Revelar>
      </div>
    </section>
  );
}

/** Ícone e chave do texto de cada passo. */
const PASSOS: [IconName, string][] = [
  ["upload", "curriculo"],
  ["road", "trilha"],
  ["refresh", "ajuste"],
];

function ComoFunciona() {
  const t = useT();
  const cores = [ACC, C.verde, C.ambar];
  return (
    <section id="como-funciona" style={{ scrollMarginTop: 80 }}>
      <Revelar>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <Rotulo>{t("landing.comoFunciona.rotulo")}</Rotulo>
          <h2 style={{ fontSize: "clamp(24px, 3vw, 32px)", margin: "12px 0 0", fontWeight: 600, letterSpacing: "-.02em" }}>
            {t("landing.comoFunciona.titulo")}
          </h2>
        </div>
      </Revelar>
      <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))", gap: 14 }}>
        {PASSOS.map(([icone, chave], indice) => (
          <li key={chave}>
            <Revelar atraso={indice * 110}>
              <div className="lp-cartao" style={{ padding: 22, borderRadius: 14, background: PANEL, boxShadow: `inset 0 0 0 1px ${HAIRLINE}`, height: "100%", boxSizing: "border-box", ["--lp-cor" as string]: cores[indice] }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ display: "inline-grid", placeItems: "center", width: 38, height: 38, borderRadius: 11, background: tint(cores[indice], 16), color: cores[indice] }}>
                    <Icon name={icone} size={19} />
                  </span>
                  <span style={{ fontSize: 12, color: TEXT.faint, fontFamily: "ui-monospace, Menlo, monospace" }}>0{indice + 1}</span>
                </div>
                <h3 style={{ fontSize: 17, margin: "14px 0 8px", fontWeight: 600 }}>{t(`landing.comoFunciona.${chave}.titulo`)}</h3>
                <p style={{ fontSize: 14, lineHeight: 1.6, color: TEXT.muted, margin: 0 }}>{t(`landing.comoFunciona.${chave}.texto`)}</p>
              </div>
            </Revelar>
          </li>
        ))}
      </ol>
    </section>
  );
}

function PreviaTrilha({ feitos, alternar }: { feitos: Set<number>; alternar: (indice: number) => void }) {
  const t = useT();
  const total = FEITOS_ANTES + feitos.size;
  // Duas medidas, e cada uma no seu lugar: a barra é da FASE (cinco módulos,
  // chega a 100% quando todos são marcados); a linha de baixo é do plano
  // inteiro. Com uma barra só do plano, fechar a fase parava em 47% e parecia
  // que faltava metade.
  const pctFase = Math.round((feitos.size / MODULOS.length) * 100);
  const pctPlano = Math.round((total / TOTAL_DE_MODULOS) * 100);
  const restantes = MODULOS.reduce((soma, m, i) => soma + (feitos.has(i) ? 0 : m.minutos), 0);
  const fechou = feitos.size === MODULOS.length;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 13.5, color: TEXT.strong }}>{t("landing.trilha.fase")}</span>
          <span style={{ marginLeft: "auto", fontSize: 12, color: fechou ? C.verde : TEXT.faint }}>
            {t("landing.trilha.contagem", { feitos: feitos.size, total: MODULOS.length })}{" "}
            <span style={{ color: fechou ? C.verde : ACC4 }}>{pctFase}%</span>
          </span>
        </div>
        <div role="progressbar" aria-label={t("landing.trilha.barraAria")} aria-valuenow={pctFase} aria-valuemin={0} aria-valuemax={100}
          style={{ height: 6, borderRadius: 3, background: "rgba(233,233,237,.08)", marginTop: 8, overflow: "hidden" }}>
          <div style={{ width: `${pctFase}%`, height: "100%", borderRadius: 3, background: fechou ? C.verde : `linear-gradient(90deg, ${ACC}, ${C.verde})`, transition: "width .5s cubic-bezier(.2,.7,.2,1), background .3s" }} />
        </div>
        <div style={{ fontSize: 11.5, color: TEXT.faint, marginTop: 6 }}>
          {t("landing.trilha.plano", { feitos: total, total: TOTAL_DE_MODULOS, pct: pctPlano })}
        </div>
      </div>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
        {MODULOS.map((modulo, indice) => {
          const feito = feitos.has(indice);
          return (
            <li key={modulo.chave}>
              <button
                type="button"
                aria-pressed={feito}
                onClick={() => alternar(indice)}
                className="lp-modulo"
                style={{
                  width: "100%", display: "flex", alignItems: "center", gap: 11, textAlign: "left",
                  padding: "10px 12px", borderRadius: 10, font: "inherit", cursor: "pointer", color: "inherit",
                  background: feito ? tint(C.verde, 8) : "transparent",
                  border: `1px solid ${feito ? tint(C.verde, 35) : HAIRLINE}`,
                  transition: "background .2s, border-color .2s",
                }}
              >
                <span
                  aria-hidden
                  style={{
                    width: 20, height: 20, borderRadius: 6, flex: "none", display: "grid", placeItems: "center",
                    border: `1.5px solid ${feito ? C.verde : "rgba(233,233,237,.3)"}`,
                    background: feito ? C.verde : "transparent", color: BG, transition: "all .2s",
                  }}
                >
                  {feito ? <Icon name="check" size={13} /> : null}
                </span>
                <span style={{ minWidth: 0, flex: 1 }}>
                  <span style={{ display: "block", fontSize: 13.5, color: feito ? TEXT.muted : TEXT.full, textDecoration: feito ? "line-through" : "none" }}>
                    {t(`landing.modulos.${modulo.chave}.titulo`)}
                  </span>
                  <span style={{ fontSize: 11.5, color: TEXT.faint }}>
                    {t("landing.trilha.tipoEDuracao", { tipo: t(`landing.modulos.${modulo.chave}.tipo`), minutos: modulo.minutos })}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <div aria-live="polite" style={{ fontSize: 12.5, color: fechou ? C.verde : TEXT.faint }}>
        {fechou
          ? t("landing.trilha.faseConcluida")
          : t("landing.trilha.faltam", { horas: Math.floor(restantes / 60), minutos: String(restantes % 60).padStart(2, "0") })}
      </div>
    </div>
  );
}

function PreviaIdioma() {
  const t = useT();
  const [palavra, setPalavra] = useState<string>("deploy");
  // A frase do treino é em inglês: é o conteúdo da atividade, não texto de interface.
  const frase: (string | { p: string })[] = [
    "The ", { p: "team" }, " will ", { p: "deploy" }, " the new ", { p: "version" }, " on ", { p: "Friday" }, ". What happens on Friday?",
  ];
  const dados = PALAVRAS[palavra];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ fontSize: 11, color: ACC }}>{t("landing.idioma.legenda")}</div>
      <p style={{ fontSize: 16, lineHeight: 1.9, margin: 0 }}>
        {frase.map((parte, i) =>
          typeof parte === "string" ? (
            <span key={i}>{parte}</span>
          ) : (
            <button
              key={i}
              type="button"
              aria-pressed={palavra === parte.p}
              onClick={() => setPalavra(parte.p)}
              onMouseEnter={() => setPalavra(parte.p)}
              style={{
                font: "inherit", cursor: "pointer", border: "none", padding: "0 3px", borderRadius: 4,
                color: palavra === parte.p ? ACC3 : TEXT.full,
                background: palavra === parte.p ? tint(ACC, 22) : "transparent",
                textDecoration: "underline dotted", textDecorationColor: tint(ACC, 70), textUnderlineOffset: 4,
                transition: "background .15s",
              }}
            >
              {parte.p}
            </button>
          ),
        )}
      </p>
      <div aria-live="polite" style={{ padding: "12px 14px", borderRadius: 10, background: BG, boxShadow: `0 0 0 1px ${HAIRLINE}`, maxWidth: 320 }}>
        <div style={{ fontSize: 14 }}>{palavra} <span style={{ color: TEXT.faint, fontSize: 12 }}>{dados.ipa}</span></div>
        <div style={{ color: ACC3, marginTop: 4 }}>{t(`landing.palavras.${palavra}.traducao`)}</div>
        <div style={{ fontSize: 12, color: TEXT.faint, marginTop: 4 }}>
          {t("landing.idioma.sinonimos", { lista: t(`landing.palavras.${palavra}.sinonimos`) })}
        </div>
        <div style={{ fontSize: 11.5, color: C.verde, marginTop: 8, display: "flex", alignItems: "center", gap: 5 }}>
          <Icon name="check" size={12} /> {t("landing.idioma.entrouNaRevisao")}
        </div>
      </div>
    </div>
  );
}

function PreviaCodigo() {
  const t = useT();
  const [linguagem, setLinguagem] = useState("java");
  const [linha, setLinha] = useState(1);
  const exemplo = EXEMPLOS[linguagem];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ width: 190 }}>
          <div style={{ fontSize: 11.5, color: TEXT.faint, marginBottom: 4 }}>{t("landing.codigo.linguagem")}</div>
          <Select id="lp-linguagem" value={linguagem} onChange={(v) => { setLinguagem(v); setLinha(1); }} options={LINGUAGENS} />
        </div>
        <div className="input" style={{ flex: 1, minWidth: 160, display: "flex", alignItems: "center", color: TEXT.muted }}>
          {t(`landing.exemplos.${linguagem}.assunto`)}
        </div>
      </div>
      <pre style={{ margin: 0, padding: "10px 0", borderRadius: 10, background: BG, fontSize: 13, lineHeight: 1.7, overflowX: "auto" }}>
        {exemplo.linhas.map((texto, i) => (
          <div
            key={`${linguagem}-${i}`}
            onMouseEnter={() => setLinha(i)}
            onClick={() => setLinha(i)}
            style={{
              padding: "0 14px", cursor: "pointer", color: TEXT.strong,
              background: linha === i ? tint(ACC, 14) : "transparent",
              boxShadow: linha === i ? `inset 2px 0 0 ${ACC}` : "none",
              transition: "background .15s",
            }}
          >
            <span style={{ color: TEXT.faint, marginRight: 14, userSelect: "none" }}>{i + 1}</span>{texto}
          </div>
        ))}
      </pre>
      <div aria-live="polite" style={{ fontSize: 13, color: TEXT.muted, minHeight: 40 }}>
        <span style={{ color: ACC4 }}>{t("landing.codigo.linha", { n: linha + 1 })}</span> · {t(`landing.exemplos.${linguagem}.linhas.${linha}`)}
      </div>
    </div>
  );
}

function PreviaPessoas() {
  const t = useT();
  const { idioma } = useIdioma();
  const [pessoas, setPessoas] = useState(() => pessoasDeExemplo(idioma));
  const [aviso, setAviso] = useState<string | null>(null);

  // Trocou o idioma: outras pessoas, de outra cidade, com outra stack. O que
  // o visitante já tinha adicionado no exemplo volta ao começo junto — é um
  // exemplo novo, não o mesmo traduzido. Depende só do idioma: o dicionário
  // chega depois da primeira pintura, e reagir a ele apagaria o clique que o
  // visitante acabou de dar.
  useEffect(() => {
    setPessoas(pessoasDeExemplo(idioma));
    setAviso(null);
  }, [idioma]);

  // O objetivo vem como chave e é traduzido aqui, na hora de mostrar.
  const naTela = pessoas.map((pessoa) => ({ ...pessoa, objetivo: t(pessoa.objetivo ?? "") }));

  function simular(username: string, acao: AcaoDeAmizade) {
    setPessoas((atuais) =>
      atuais.map((p) => {
        if (p.username !== username) return p;
        if (acao === "convidar") return { ...p, relacao: "enviado", friendship_id: "exemplo" };
        if (acao === "aceitar") return { ...p, relacao: "amigos" };
        return { ...p, relacao: "nenhuma", friendship_id: null };
      }),
    );
    const nome = pessoas.find((p) => p.username === username)?.name.split(" ")[0] ?? "";
    setAviso(
      acao === "convidar"
        ? t("landing.pessoas.convite", { nome })
        : acao === "aceitar"
          ? t("landing.pessoas.amigos", { nome })
          : t("landing.pessoas.desfeito"),
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 230px), 1fr))", gap: 10 }}>
        {naTela.map((pessoa) => (
          <CartaoPessoa
            key={pessoa.username}
            pessoa={pessoa}
            onMudou={() => {}}
            somenteLeitura
            onDemo={(acao) => simular(pessoa.username, acao)}
          />
        ))}
      </div>
      <div aria-live="polite" style={{ fontSize: 12.5, color: C.verde, minHeight: 18 }}>{aviso}</div>
    </div>
  );
}

/** Ícone e chave do texto de cada cuidado. */
const CUIDADOS: [IconName, string][] = [
  ["download", "dados"],
  ["eyeOff", "visibilidade"],
  ["flag", "sessao"],
];

function Cuidados({ onNavigate }: { onNavigate: Navegar }) {
  const t = useT();
  const cores = [C.verde, ACC, C.ambar];
  return (
    <section id="cuidados" style={{ scrollMarginTop: 80 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))", gap: 14 }}>
        {CUIDADOS.map(([icone, chave], indice) => (
          <Revelar key={chave} atraso={indice * 110}>
            <div className="lp-cartao" style={{ padding: 20, borderRadius: 14, boxShadow: `inset 0 0 0 1px ${HAIRLINE}`, height: "100%", boxSizing: "border-box", ["--lp-cor" as string]: cores[indice] }}>
              <span style={{ display: "inline-grid", placeItems: "center", width: 34, height: 34, borderRadius: 10, background: tint(cores[indice], 14), color: cores[indice] }}>
                <Icon name={icone} size={17} />
              </span>
              <h3 style={{ fontSize: 15.5, margin: "12px 0 6px", fontWeight: 600 }}>{t(`landing.cuidados.${chave}.titulo`)}</h3>
              <p style={{ fontSize: 13.5, lineHeight: 1.6, color: TEXT.muted, margin: 0 }}>{t(`landing.cuidados.${chave}.texto`)}</p>
            </div>
          </Revelar>
        ))}
      </div>
      <p style={{ textAlign: "center", fontSize: 13, color: TEXT.faint, margin: "16px 0 0" }}>
        {t("landing.cuidados.detalhesAntes")}{" "}
        <a href="/privacidade" onClick={(e) => { e.preventDefault(); onNavigate("/privacidade"); }} style={{ color: ACC4 }}>{t("landing.cuidados.linkPrivacidade")}</a>
        {" "}{t("landing.cuidados.detalhesMeio")}{" "}
        <a href="/seguranca" onClick={(e) => { e.preventDefault(); onNavigate("/seguranca"); }} style={{ color: ACC4 }}>{t("landing.cuidados.linkSeguranca")}</a>.
      </p>
    </section>
  );
}

// Estilos que inline não expressa: hover, animação e o menu que some no celular.
const CSS = `
.lp-cartao { transition: transform .25s cubic-bezier(.2,.7,.2,1), box-shadow .25s; }
.lp-cartao:hover { transform: translateY(-3px); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--lp-cor) 45%, transparent), 0 14px 40px rgba(0,0,0,.5) !important; }
.lp-modulo:hover { border-color: color-mix(in srgb, ${ACC} 45%, transparent) !important; }
.lp-janela { transition: box-shadow .3s; }
.lp-janela:hover { box-shadow: 0 30px 70px rgba(0,0,0,.7), 0 0 0 1px color-mix(in srgb, ${ACC} 35%, transparent) !important; }
.lp-gradiente { background-size: 200% 100%; animation: lp-brilho 8s linear infinite; }
@keyframes lp-brilho { to { background-position: 200% 0; } }
.lp-pulso { animation: lp-pulso 1.8s ease-in-out infinite; }
@keyframes lp-pulso { 50% { opacity: .35; } }
@media (max-width: 760px) { .lp-secoes { display: none !important; } }
@media (prefers-reduced-motion: reduce) {
  .lp-gradiente, .lp-pulso { animation: none; }
  .lp-cartao, .lp-janela { transition: none; }
  .lp-cartao:hover { transform: none; }
}
`;

export function LandingPage({ onNavigate }: { onNavigate: Navegar }) {
  const t = useT();
  // Determinística: refazer ao trocar de idioma só muda os títulos dos itens.
  const atividade = useMemo(() => atividadeDeExemplo(t), [t]);
  const [feitos, setFeitos] = useState<Set<number>>(() => new Set([0]));
  const panorama = panoramaDeExemplo(atividade, FEITOS_ANTES + feitos.size, TOTAL_DE_MODULOS);

  function alternar(indice: number) {
    setFeitos((atual) => {
      const novo = new Set(atual);
      if (novo.has(indice)) novo.delete(indice);
      else novo.add(indice);
      return novo;
    });
  }

  const link = (path: string, rotulo: string) => (
    <a href={path} onClick={(e) => { e.preventDefault(); onNavigate(path); }} style={{ color: TEXT.muted, textDecoration: "none" }}>
      {rotulo}
    </a>
  );

  return (
    <div style={{ minHeight: "100dvh", background: BG, color: TEXT.full, fontFamily: "Inter, system-ui, sans-serif", overflowX: "clip" }}>
      <style>{CSS}</style>
      <SeletorDeIdioma flutuante />
      <Topo onNavigate={onNavigate} />

      <main style={{ maxWidth: 1120, margin: "0 auto", padding: "0 clamp(16px, 4vw, 40px)", display: "flex", flexDirection: "column", gap: "clamp(64px, 9vw, 120px)", position: "relative", zIndex: 0 }}>
        <Heroi onNavigate={onNavigate} panorama={panorama} />

        <ComoFunciona />

        <div id="recursos" style={{ display: "flex", flexDirection: "column", gap: "clamp(64px, 9vw, 120px)", scrollMarginTop: 80 }}>
          <Destaque
            rotulo={t("landing.recursos.trilha.rotulo")}
            titulo={t("landing.recursos.trilha.titulo")}
            texto={t("landing.recursos.trilha.texto")}
            pontos={[t("landing.recursos.trilha.ponto1"), t("landing.recursos.trilha.ponto2"), t("landing.recursos.trilha.ponto3")]}
          >
            <Janela interativa titulo={t("landing.recursos.trilha.janelaTitulo")} descricao={t("landing.recursos.trilha.janelaDescricao")}>
              <PreviaTrilha feitos={feitos} alternar={alternar} />
            </Janela>
          </Destaque>

          <Destaque
            larga
            rotulo={t("landing.recursos.constancia.rotulo")}
            titulo={t("landing.recursos.constancia.titulo")}
            texto={t("landing.recursos.constancia.texto")}
            pontos={[t("landing.recursos.constancia.ponto1"), t("landing.recursos.constancia.ponto2"), t("landing.recursos.constancia.ponto3")]}
          >
            <Janela interativa titulo={t("landing.recursos.constancia.janelaTitulo")} descricao={t("landing.recursos.constancia.janelaDescricao")}>
              <ConsistencyPanel activity={atividade} />
            </Janela>
          </Destaque>

          <Destaque
            invertido
            rotulo={t("landing.recursos.codigo.rotulo")}
            titulo={t("landing.recursos.codigo.titulo")}
            texto={t("landing.recursos.codigo.texto")}
            pontos={[t("landing.recursos.codigo.ponto1"), t("landing.recursos.codigo.ponto2"), t("landing.recursos.codigo.ponto3")]}
          >
            <Janela interativa titulo={t("landing.recursos.codigo.janelaTitulo")} descricao={t("landing.recursos.codigo.janelaDescricao")}>
              <PreviaCodigo />
            </Janela>
          </Destaque>

          <Destaque
            rotulo={t("landing.recursos.idiomas.rotulo")}
            titulo={t("landing.recursos.idiomas.titulo")}
            texto={t("landing.recursos.idiomas.texto")}
            pontos={[t("landing.recursos.idiomas.ponto1"), t("landing.recursos.idiomas.ponto2"), t("landing.recursos.idiomas.ponto3")]}
          >
            <Janela interativa titulo={t("landing.recursos.idiomas.janelaTitulo")} descricao={t("landing.recursos.idiomas.janelaDescricao")}>
              <PreviaIdioma />
            </Janela>
          </Destaque>

          <Destaque
            invertido
            rotulo={t("landing.recursos.pessoas.rotulo")}
            titulo={t("landing.recursos.pessoas.titulo")}
            texto={t("landing.recursos.pessoas.texto")}
            pontos={[t("landing.recursos.pessoas.ponto1"), t("landing.recursos.pessoas.ponto2"), t("landing.recursos.pessoas.ponto3")]}
          >
            <Janela interativa titulo={t("landing.recursos.pessoas.janelaTitulo")} descricao={t("landing.recursos.pessoas.janelaDescricao")}>
              <PreviaPessoas />
            </Janela>
          </Destaque>
        </div>

        <Cuidados onNavigate={onNavigate} />

        <Revelar>
          <section style={{ textAlign: "center", padding: "clamp(40px, 7vw, 80px) 24px", borderRadius: 24, background: `radial-gradient(120% 140% at 50% 0%, ${tint(ACC, 24)}, transparent 60%), ${PANEL}`, boxShadow: `inset 0 0 0 1px ${HAIRLINE}` }}>
            <h2 style={{ fontSize: "clamp(26px, 4vw, 40px)", margin: 0, fontWeight: 650, letterSpacing: "-.025em" }}>
              {t("landing.chamada.titulo")}
            </h2>
            <p style={{ fontSize: 16, color: TEXT.muted, margin: "14px auto 26px", maxWidth: "48ch", lineHeight: 1.6 }}>
              {t("landing.chamada.texto")}
            </p>
            <a href="/cadastro" className="btn btn-tom" style={{ ...TOM_ACC, padding: "13px 26px", fontSize: 15.5 }}
              onClick={(e) => { e.preventDefault(); onNavigate("/cadastro"); }}>
              {t("landing.chamada.botao")}
              <Icon name="arrowRight" size={16} />
            </a>
          </section>
        </Revelar>
      </main>

      <footer style={{ maxWidth: 1120, margin: "0 auto", padding: "40px clamp(16px, 4vw, 40px) 48px", display: "flex", flexWrap: "wrap", gap: "12px 20px", alignItems: "center", color: TEXT.faint, fontSize: 13 }}>
        <Logo size={22} />
        <span>{t("landing.rodape.marca")}</span>
        <nav aria-label={t("landing.rodape.nav")} style={{ marginLeft: "auto", display: "flex", flexWrap: "wrap", gap: "8px 18px" }}>
          {link("/termos", t("landing.rodape.termos"))}
          {link("/privacidade", t("landing.rodape.privacidade"))}
          {link("/seguranca", t("landing.rodape.seguranca"))}
        </nav>
      </footer>
    </div>
  );
}
