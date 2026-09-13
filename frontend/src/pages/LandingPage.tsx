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
 */

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { ActivitySummary, Overview, PessoaCartao } from "@/api/types";
import { ConsistencyPanel } from "@/components/dashboard/ConsistencyPanel";
import { KpiCards } from "@/components/dashboard/KpiCards";
import { CartaoPessoa, type AcaoDeAmizade } from "@/components/social/CartaoPessoa";
import { Icon, type IconName } from "@/components/ui/icons";
import { Logo } from "@/components/ui/Logo";
import { Select } from "@/components/ui/Select";
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
function atividadeDeExemplo(): ActivitySummary {
  const hoje = new Date();
  const titulos: [string, string][] = [
    ["article", "Spring Boot: injeção de dependência na prática"],
    ["video", "JPA e Hibernate do zero"],
    ["doc", "Documentação oficial do Docker"],
    ["article", "Testes com JUnit 5 e Mockito"],
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
        { kind: "quiz_done", title: "Quiz do módulo", minutes: Math.round(minutos * 0.4) },
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

const PESSOAS: PessoaCartao[] = [
  {
    username: "marinacosta", name: "Marina Costa", has_avatar: false, city: "Vitória", state: "ES",
    objetivo: "Backend Java com Spring", cargo: "Desenvolvedora", senioridade: "pleno",
    stack: ["Java", "Spring Boot", "PostgreSQL", "Docker"], relacao: "nenhuma", friendship_id: null,
    em_comum: ["Java", "Spring Boot"],
  },
  {
    username: "lucas_rocha", name: "Lucas Rocha", has_avatar: false, city: "Vila Velha", state: "ES",
    objetivo: "Fullstack TypeScript", cargo: null, senioridade: "junior",
    stack: ["React", "TypeScript", "Node.js"], relacao: "recebido", friendship_id: "exemplo",
    em_comum: ["React", "TypeScript", "Node.js"], mesma_stack: true,
  },
];

/** A trilha de exemplo: 19 módulos no total, e estes cinco são a fase atual. */
const TOTAL_DE_MODULOS = 19;
const FEITOS_ANTES = 4;
const MODULOS = [
  { titulo: "Spring Boot: estrutura de um projeto", minutos: 90, tipo: "Artigo + quiz" },
  { titulo: "Injeção de dependência na prática", minutos: 60, tipo: "Vídeo + exercício" },
  { titulo: "JPA e Hibernate: mapeando entidades", minutos: 120, tipo: "Documentação + quiz" },
  { titulo: "Testes com JUnit 5 e Mockito", minutos: 75, tipo: "Exemplo guiado" },
  { titulo: "Docker para rodar a API localmente", minutos: 60, tipo: "Artigo + prática" },
];

const EXEMPLOS: Record<string, { rotulo: string; assunto: string; linhas: [string, string][] }> = {
  java: {
    rotulo: "Java",
    assunto: "streams e lambdas",
    linhas: [
      ["List<String> nomes = pessoas.stream()", "Abre um fluxo sobre a lista: nada é processado ainda."],
      ["    .filter(p -> p.idade() >= 18)", "Descarta quem tem menos de 18 antes de qualquer outra etapa."],
      ["    .map(Pessoa::nome)", "Troca cada pessoa pelo nome dela — referência de método."],
      ["    .toList();", "Só aqui o fluxo roda de verdade e vira uma lista imutável."],
    ],
  },
  typescript: {
    rotulo: "TypeScript",
    assunto: "tipos e async/await",
    linhas: [
      ["type Vaga = { titulo: string; nota: number };", "Descreve o formato que a API devolve."],
      ["const resposta = await fetch('/vagas');", "Espera a requisição sem travar a interface."],
      ["const vagas: Vaga[] = await resposta.json();", "O tipo garante que `nota` existe antes de usar."],
      ["vagas.sort((a, b) => b.nota - a.nota);", "Ordena da maior compatibilidade para a menor."],
    ],
  },
  python: {
    rotulo: "Python",
    assunto: "compreensão de listas",
    linhas: [
      ["notas = [7.5, 9.0, 4.0, 8.2]", "Uma lista comum de números."],
      ["aprovadas = [n for n in notas if n >= 7]", "Filtra e monta a nova lista numa linha só."],
      ["media = sum(aprovadas) / len(aprovadas)", "Soma e divide pela quantidade de aprovadas."],
      ["print(f'{media:.1f}')", "f-string com uma casa decimal: 8.2"],
    ],
  },
  go: {
    rotulo: "Go",
    assunto: "goroutines e canais",
    linhas: [
      ["canal := make(chan int)", "Cria um canal para as goroutines conversarem."],
      ["go func() { canal <- calcular() }()", "Roda o cálculo em paralelo, sem bloquear."],
      ["resultado := <-canal", "Espera o valor chegar pelo canal."],
      ["fmt.Println(resultado)", "Imprime quando a goroutine terminar."],
    ],
  },
};

const LINGUAGENS = Object.entries(EXEMPLOS).map(([id, exemplo]) => ({
  value: id,
  label: exemplo.rotulo,
  icon: iconeDaLinguagem(id),
}));

const PALAVRAS: Record<string, { ipa: string; traducao: string; sinonimos: string }> = {
  deploy: { ipa: "/dɪˈplɔɪ/", traducao: "implantar, publicar", sinonimos: "release, ship, roll out" },
  version: { ipa: "/ˈvɜːrʒən/", traducao: "versão", sinonimos: "release, build, edition" },
  team: { ipa: "/tiːm/", traducao: "equipe, time", sinonimos: "squad, crew, group" },
  Friday: { ipa: "/ˈfraɪdeɪ/", traducao: "sexta-feira", sinonimos: "fim da semana útil" },
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
            Experimente
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
      <nav aria-label="Seções" className="lp-secoes" style={{ marginLeft: 28, display: "flex", gap: 4 }}>
        {[["como-funciona", "Como funciona"], ["recursos", "Recursos"], ["cuidados", "Segurança"]].map(([id, rotulo]) => (
          <a key={id} href={`#${id}`} className="btn btn-ghost" style={{ color: TEXT.muted, fontSize: 13.5 }}
            onClick={(e) => { e.preventDefault(); irPara(id); }}>
            {rotulo}
          </a>
        ))}
      </nav>
      <nav aria-label="Conta" style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
        <a href="/entrar" className="btn btn-ghost" onClick={(e) => { e.preventDefault(); onNavigate("/entrar"); }}>
          Entrar
        </a>
        <a href="/cadastro" className="btn btn-primary" onClick={(e) => { e.preventDefault(); onNavigate("/cadastro"); }}>
          Criar conta
        </a>
      </nav>
    </header>
  );
}

const TOM_ACC = { "--tom": ACC } as CSSProperties;

function Heroi({ onNavigate, panorama }: { onNavigate: Navegar; panorama: Overview }) {
  return (
    <section style={{ textAlign: "center", paddingTop: "clamp(40px, 8vw, 96px)", position: "relative" }}>
      {/* O brilho de fundo: a única cor que vaza no preto, atrás do título. */}
      <div
        aria-hidden
        style={{
          position: "absolute", left: "-20%", right: "-20%", top: -120, height: 560, zIndex: -1, pointerEvents: "none",
          background: `radial-gradient(50% 55% at 50% 40%, ${tint(ACC, 26)}, transparent 70%), radial-gradient(30% 40% at 72% 30%, ${tint(C.verde, 12)}, transparent 70%)`,
        }}
      />
      <Revelar>
        <div
          style={{
            display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 14px", borderRadius: 999,
            background: tint(ACC, 10), boxShadow: `inset 0 0 0 1px ${tint(ACC, 30)}`, fontSize: 12.5, color: ACC3,
          }}
        >
          <Icon name="flame" size={14} style={{ color: C.ambar }} />
          Plano de estudos para quem trabalha com tecnologia
        </div>
        <h1
          style={{
            fontSize: "clamp(34px, 6vw, 62px)", lineHeight: 1.05, letterSpacing: "-.035em",
            fontWeight: 650, margin: "20px auto 20px", maxWidth: "16ch",
          }}
        >
          Do seu currículo a um plano que{" "}
          <span className="lp-gradiente" style={{ backgroundImage: `linear-gradient(90deg, ${ACC4}, ${C.verde}, ${ACC4})`, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
            se corrige toda semana
          </span>
        </h1>
        <p style={{ fontSize: "clamp(16px, 1.8vw, 19px)", lineHeight: 1.65, color: TEXT.muted, margin: "0 auto", maxWidth: "58ch" }}>
          Envie o currículo e diga aonde quer chegar. O PathR monta a trilha em fases, separa o material
          certo para cada módulo, mede o que você aprendeu de verdade e ajusta a rota com o que viu.
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 10, marginTop: 28 }}>
          <a href="/cadastro" className="btn btn-tom" style={{ ...TOM_ACC, padding: "12px 22px", fontSize: 15 }}
            onClick={(e) => { e.preventDefault(); onNavigate("/cadastro"); }}>
            Criar conta grátis
            <Icon name="arrowRight" size={16} />
          </a>
          <a href="/entrar" className="btn btn-secondary" style={{ padding: "12px 22px", fontSize: 15 }}
            onClick={(e) => { e.preventDefault(); onNavigate("/entrar"); }}>
            Já tenho conta
          </a>
        </div>
      </Revelar>
      <div style={{ marginTop: "clamp(40px, 7vw, 72px)", textAlign: "left" }}>
        <Revelar atraso={150}>
          <Janela interativa titulo="pathr.notter.com.br · Início" descricao="Painel inicial com sequência de estudo, progresso do plano e tempo estudado">
            <KpiCards overview={panorama} />
          </Janela>
          <p style={{ textAlign: "center", fontSize: 12.5, color: TEXT.faint, margin: "12px 0 0" }}>
            Passe o mouse nos cartões — e marque módulos na trilha mais abaixo para ver o progresso subir aqui.
          </p>
        </Revelar>
      </div>
    </section>
  );
}

const PASSOS: [IconName, string, string][] = [
  ["upload", "Envie o currículo", "A IA lê suas competências e o nível de cada uma. Nada de preencher uma lista de 200 tecnologias à mão."],
  ["road", "Receba a trilha", "Fases e módulos ordenados pelo que o seu objetivo exige, no tamanho das horas que você tem por semana."],
  ["refresh", "Estude e deixe ajustar", "Quiz, explicação com suas palavras e revisão espaçada movem o seu nível. A semana se remonta sozinha."],
];

function ComoFunciona() {
  const cores = [ACC, C.verde, C.ambar];
  return (
    <section id="como-funciona" style={{ scrollMarginTop: 80 }}>
      <Revelar>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <Rotulo>Como funciona</Rotulo>
          <h2 style={{ fontSize: "clamp(24px, 3vw, 32px)", margin: "12px 0 0", fontWeight: 600, letterSpacing: "-.02em" }}>
            Três passos, e o plano trabalha por você
          </h2>
        </div>
      </Revelar>
      <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))", gap: 14 }}>
        {PASSOS.map(([icone, titulo, texto], indice) => (
          <li key={titulo}>
            <Revelar atraso={indice * 110}>
              <div className="lp-cartao" style={{ padding: 22, borderRadius: 14, background: PANEL, boxShadow: `inset 0 0 0 1px ${HAIRLINE}`, height: "100%", boxSizing: "border-box", ["--lp-cor" as string]: cores[indice] }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ display: "inline-grid", placeItems: "center", width: 38, height: 38, borderRadius: 11, background: tint(cores[indice], 16), color: cores[indice] }}>
                    <Icon name={icone} size={19} />
                  </span>
                  <span style={{ fontSize: 12, color: TEXT.faint, fontFamily: "ui-monospace, Menlo, monospace" }}>0{indice + 1}</span>
                </div>
                <h3 style={{ fontSize: 17, margin: "14px 0 8px", fontWeight: 600 }}>{titulo}</h3>
                <p style={{ fontSize: 14, lineHeight: 1.6, color: TEXT.muted, margin: 0 }}>{texto}</p>
              </div>
            </Revelar>
          </li>
        ))}
      </ol>
    </section>
  );
}

function PreviaTrilha({ feitos, alternar }: { feitos: Set<number>; alternar: (indice: number) => void }) {
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
          <span style={{ fontSize: 13.5, color: TEXT.strong }}>Fase 2 · Backend com Spring</span>
          <span style={{ marginLeft: "auto", fontSize: 12, color: fechou ? C.verde : TEXT.faint }}>
            {feitos.size} de {MODULOS.length} módulos · <span style={{ color: fechou ? C.verde : ACC4 }}>{pctFase}%</span>
          </span>
        </div>
        <div role="progressbar" aria-label="Progresso da trilha de exemplo" aria-valuenow={pctFase} aria-valuemin={0} aria-valuemax={100}
          style={{ height: 6, borderRadius: 3, background: "rgba(233,233,237,.08)", marginTop: 8, overflow: "hidden" }}>
          <div style={{ width: `${pctFase}%`, height: "100%", borderRadius: 3, background: fechou ? C.verde : `linear-gradient(90deg, ${ACC}, ${C.verde})`, transition: "width .5s cubic-bezier(.2,.7,.2,1), background .3s" }} />
        </div>
        <div style={{ fontSize: 11.5, color: TEXT.faint, marginTop: 6 }}>
          Plano completo: {total} de {TOTAL_DE_MODULOS} módulos · {pctPlano}% — o cartão de progresso lá em cima acompanha.
        </div>
      </div>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
        {MODULOS.map((modulo, indice) => {
          const feito = feitos.has(indice);
          return (
            <li key={modulo.titulo}>
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
                    {modulo.titulo}
                  </span>
                  <span style={{ fontSize: 11.5, color: TEXT.faint }}>{modulo.tipo} · {modulo.minutos} min</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <div aria-live="polite" style={{ fontSize: 12.5, color: fechou ? C.verde : TEXT.faint }}>
        {fechou
          ? "Fase concluída — a próxima já foi montada um degrau acima."
          : `Faltam ${Math.floor(restantes / 60)}h${String(restantes % 60).padStart(2, "0")} nesta fase. Toque num módulo para marcar.`}
      </div>
    </div>
  );
}

function PreviaIdioma() {
  const [palavra, setPalavra] = useState<string>("deploy");
  const frase: (string | { p: string })[] = [
    "The ", { p: "team" }, " will ", { p: "deploy" }, " the new ", { p: "version" }, " on ", { p: "Friday" }, ". What happens on Friday?",
  ];
  const dados = PALAVRAS[palavra];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ fontSize: 11, color: ACC }}>reading · B1 · toque numa palavra sublinhada</div>
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
        <div style={{ color: ACC3, marginTop: 4 }}>{dados.traducao}</div>
        <div style={{ fontSize: 12, color: TEXT.faint, marginTop: 4 }}>sinônimos: {dados.sinonimos}</div>
        <div style={{ fontSize: 11.5, color: C.verde, marginTop: 8, display: "flex", alignItems: "center", gap: 5 }}>
          <Icon name="check" size={12} /> Entrou na sua revisão de vocabulário para hoje.
        </div>
      </div>
    </div>
  );
}

function PreviaCodigo() {
  const [linguagem, setLinguagem] = useState("java");
  const [linha, setLinha] = useState(1);
  const exemplo = EXEMPLOS[linguagem];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ width: 190 }}>
          <div style={{ fontSize: 11.5, color: TEXT.faint, marginBottom: 4 }}>Linguagem</div>
          <Select id="lp-linguagem" value={linguagem} onChange={(v) => { setLinguagem(v); setLinha(1); }} options={LINGUAGENS} />
        </div>
        <div className="input" style={{ flex: 1, minWidth: 160, display: "flex", alignItems: "center", color: TEXT.muted }}>{exemplo.assunto}</div>
      </div>
      <pre style={{ margin: 0, padding: "10px 0", borderRadius: 10, background: BG, fontSize: 13, lineHeight: 1.7, overflowX: "auto" }}>
        {exemplo.linhas.map(([texto], i) => (
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
        <span style={{ color: ACC4 }}>Linha {linha + 1}</span> · {exemplo.linhas[linha][1]}
      </div>
    </div>
  );
}

function PreviaPessoas() {
  const [pessoas, setPessoas] = useState(PESSOAS);
  const [aviso, setAviso] = useState<string | null>(null);

  function simular(username: string, acao: AcaoDeAmizade) {
    setPessoas((atuais) =>
      atuais.map((p) => {
        if (p.username !== username) return p;
        if (acao === "convidar") return { ...p, relacao: "enviado", friendship_id: "exemplo" };
        if (acao === "aceitar") return { ...p, relacao: "amigos" };
        return { ...p, relacao: "nenhuma", friendship_id: null };
      }),
    );
    const nome = PESSOAS.find((p) => p.username === username)?.name.split(" ")[0] ?? "";
    setAviso(
      acao === "convidar"
        ? `Convite enviado para ${nome} — de exemplo. Crie a conta para valer.`
        : acao === "aceitar"
          ? `Agora você e ${nome} são amigos.`
          : "Desfeito.",
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 230px), 1fr))", gap: 10 }}>
        {pessoas.map((pessoa) => (
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

const CUIDADOS: [IconName, string, string][] = [
  ["download", "Seus dados são seus", "Exporte tudo em um arquivo ou exclua a conta quando quiser."],
  ["eyeOff", "Você decide quem te acha", "Aparecer nas sugestões é opcional, e e-mail nunca é mostrado a outra conta."],
  ["flag", "Sessão protegida", "Senha forte, segundo fator e chave de acesso do aparelho, se você preferir."],
];

function Cuidados({ onNavigate }: { onNavigate: Navegar }) {
  const cores = [C.verde, ACC, C.ambar];
  return (
    <section id="cuidados" style={{ scrollMarginTop: 80 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))", gap: 14 }}>
        {CUIDADOS.map(([icone, titulo, texto], indice) => (
          <Revelar key={titulo} atraso={indice * 110}>
            <div className="lp-cartao" style={{ padding: 20, borderRadius: 14, boxShadow: `inset 0 0 0 1px ${HAIRLINE}`, height: "100%", boxSizing: "border-box", ["--lp-cor" as string]: cores[indice] }}>
              <span style={{ display: "inline-grid", placeItems: "center", width: 34, height: 34, borderRadius: 10, background: tint(cores[indice], 14), color: cores[indice] }}>
                <Icon name={icone} size={17} />
              </span>
              <h3 style={{ fontSize: 15.5, margin: "12px 0 6px", fontWeight: 600 }}>{titulo}</h3>
              <p style={{ fontSize: 13.5, lineHeight: 1.6, color: TEXT.muted, margin: 0 }}>{texto}</p>
            </div>
          </Revelar>
        ))}
      </div>
      <p style={{ textAlign: "center", fontSize: 13, color: TEXT.faint, margin: "16px 0 0" }}>
        Os detalhes estão na{" "}
        <a href="/privacidade" onClick={(e) => { e.preventDefault(); onNavigate("/privacidade"); }} style={{ color: ACC4 }}>política de privacidade</a>
        {" "}e na página de{" "}
        <a href="/seguranca" onClick={(e) => { e.preventDefault(); onNavigate("/seguranca"); }} style={{ color: ACC4 }}>segurança</a>.
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
  const [atividade] = useState(atividadeDeExemplo);
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
      <Topo onNavigate={onNavigate} />

      <main style={{ maxWidth: 1120, margin: "0 auto", padding: "0 clamp(16px, 4vw, 40px)", display: "flex", flexDirection: "column", gap: "clamp(64px, 9vw, 120px)", position: "relative", zIndex: 0 }}>
        <Heroi onNavigate={onNavigate} panorama={panorama} />

        <ComoFunciona />

        <div id="recursos" style={{ display: "flex", flexDirection: "column", gap: "clamp(64px, 9vw, 120px)", scrollMarginTop: 80 }}>
          <Destaque
            rotulo="Trilha"
            titulo="Uma trilha em fases que mostra quanto falta"
            texto="Cada módulo traz o material certo — artigo, vídeo, documentação ou exemplo guiado — e o tempo que leva. Marque o que terminou e veja o progresso andar."
            pontos={["Ordem pelo que o seu objetivo exige", "Tempo por módulo no tamanho da sua semana", "Fase concluída monta a próxima um degrau acima"]}
          >
            <Janela interativa titulo="Trilha · Fase atual" descricao="Módulos da fase atual que podem ser marcados como concluídos">
              <PreviaTrilha feitos={feitos} alternar={alternar} />
            </Janela>
          </Destaque>

          <Destaque
            larga
            rotulo="Constância"
            titulo="Um mapa do ano que mostra o que você estudou em cada dia"
            texto="Cada quadrado é um dia. Passe o mouse e veja o que foi feito — o artigo, o vídeo, o quiz — e quanto tempo levou. Troque entre semana, mês e ano."
            pontos={["Sequência e recorde que você protege", "Tempo de estudo medido pelo que foi lido e assistido", "Semana, mês e ano no mesmo painel"]}
          >
            <Janela interativa titulo="Início · Sua constância" descricao="Mapa de calor do ano com os dias de estudo">
              <ConsistencyPanel activity={atividade} />
            </Janela>
          </Destaque>

          <Destaque
            invertido
            rotulo="Laboratório de código"
            titulo="Exemplos prontos, explicados linha a linha"
            texto="Escolha a linguagem e o assunto. O PathR escreve um programa curto e mostra o que cada linha faz — sem precisar de um ambiente instalado para entender a ideia."
            pontos={["As linguagens do seu perfil, com o logo de cada uma", "O passo a passo do que acontece na execução", "Sugestões a partir do módulo que você está estudando"]}
          >
            <Janela interativa titulo="Laboratório de código" descricao="Gerador de exemplos com seleção de linguagem e explicação por linha">
              <PreviaCodigo />
            </Janela>
          </Destaque>

          <Destaque
            rotulo="Idiomas"
            titulo="Inglês para o trabalho, no seu nível de verdade"
            texto="Um nivelamento CEFR que se adapta às respostas. Travou numa palavra? Toque nela: a tradução e os sinônimos aparecem, e a palavra entra na sua revisão."
            pontos={["Nivelamento adaptativo, de A1 a C2", "Consulta de palavra que vira revisão espaçada", "Treinos diários de leitura, escuta e escrita"]}
          >
            <Janela interativa titulo="Idiomas · Nivelamento" descricao="Pergunta de nivelamento com a tradução de uma palavra consultada">
              <PreviaIdioma />
            </Janela>
          </Destaque>

          <Destaque
            invertido
            rotulo="Pessoas"
            titulo="Estude com quem está perto e quer chegar no mesmo lugar"
            texto="O PathR sugere contas da sua cidade e de quem estuda as mesmas tecnologias. Cada cartão mostra objetivo, stack e o que vocês têm em comum — nunca e-mail."
            pontos={["Seu @ próprio para ser encontrado", "Sugestões por cidade, stack e objetivo", "Aparecer nas sugestões é escolha sua"]}
          >
            <Janela interativa titulo="Amigos · Sugestões" descricao="Cartões de pessoas sugeridas com cidade, objetivo e tecnologias">
              <PreviaPessoas />
            </Janela>
          </Destaque>
        </div>

        <Cuidados onNavigate={onNavigate} />

        <Revelar>
          <section style={{ textAlign: "center", padding: "clamp(40px, 7vw, 80px) 24px", borderRadius: 24, background: `radial-gradient(120% 140% at 50% 0%, ${tint(ACC, 24)}, transparent 60%), ${PANEL}`, boxShadow: `inset 0 0 0 1px ${HAIRLINE}` }}>
            <h2 style={{ fontSize: "clamp(26px, 4vw, 40px)", margin: 0, fontWeight: 650, letterSpacing: "-.025em" }}>
              Seu próximo nível começa pelo currículo que você já tem
            </h2>
            <p style={{ fontSize: 16, color: TEXT.muted, margin: "14px auto 26px", maxWidth: "48ch", lineHeight: 1.6 }}>
              Crie a conta, envie o currículo e veja o plano sair pronto em poucos minutos.
            </p>
            <a href="/cadastro" className="btn btn-tom" style={{ ...TOM_ACC, padding: "13px 26px", fontSize: 15.5 }}
              onClick={(e) => { e.preventDefault(); onNavigate("/cadastro"); }}>
              Criar conta grátis
              <Icon name="arrowRight" size={16} />
            </a>
          </section>
        </Revelar>
      </main>

      <footer style={{ maxWidth: 1120, margin: "0 auto", padding: "40px clamp(16px, 4vw, 40px) 48px", display: "flex", flexWrap: "wrap", gap: "12px 20px", alignItems: "center", color: TEXT.faint, fontSize: 13 }}>
        <Logo size={22} />
        <span>PathR · plano de estudos</span>
        <nav aria-label="Termos e políticas" style={{ marginLeft: "auto", display: "flex", flexWrap: "wrap", gap: "8px 18px" }}>
          {link("/termos", "Termos de uso")}
          {link("/privacidade", "Privacidade")}
          {link("/seguranca", "Segurança")}
        </nav>
      </footer>
    </div>
  );
}
