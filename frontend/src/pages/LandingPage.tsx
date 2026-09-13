/**
 * A apresentação do PathR, para quem ainda não tem conta.
 *
 * As telas de exemplo NÃO são imagens: são os componentes de verdade do app,
 * alimentados com dados de exemplo. Uma captura de tela envelhece no primeiro
 * ajuste de cor e passa a mostrar um produto que não existe mais; o componente
 * é o próprio produto, e muda junto.
 *
 * As prévias são `inert`: aparecem inteiras, mas não respondem a clique nem a
 * teclado. Um visitante sem conta apertando "Adicionar" num cartão de exemplo
 * não pode disparar uma chamada à API — nem ficar preso num controle que não
 * leva a lugar nenhum.
 */

import type { ReactNode } from "react";
import type { ActivitySummary, Overview, PessoaCartao } from "@/api/types";
import { ConsistencyPanel } from "@/components/dashboard/ConsistencyPanel";
import { KpiCards } from "@/components/dashboard/KpiCards";
import { CartaoPessoa } from "@/components/social/CartaoPessoa";
import { Logo } from "@/components/ui/Logo";
import { Select } from "@/components/ui/Select";
import { iconeDaLinguagem } from "@/lib/linguagens";
import { isoLocal } from "@/lib/dashboard";
import { ACC, ACC3, ACC4, BG, C, HAIRLINE, PANEL, TEXT } from "@/lib/tokens";

type Navegar = (path: string) => void;

// ---------------------------------------------------------------------------
// Dados de exemplo
// ---------------------------------------------------------------------------

/**
 * Um ano de estudo plausível até hoje: mais dias com estudo do que sem, com
 * buracos de verdade (fins de semana, uma semana parada no meio do ano).
 *
 * Determinístico — a mesma tela a cada visita — e espalhado pelo ano inteiro:
 * com só as últimas semanas, o mapa do ano de exemplo aparecia quase vazio, e
 * a prévia do recurso "veja o seu ano" mostrava um ano em branco.
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

function panoramaDeExemplo(atividade: ActivitySummary): Overview {
  return {
    streak: { current: 4, longest: 9, last_active_date: isoLocal(new Date()), total_xp: 1240, total_minutes: atividade.total_minutes },
    english: { enabled: true, cefr_level: "B1", target_level: "B2" },
    roadmap: { progress_pct: 32, done_nodes: 6, total_nodes: 19 },
    activity: atividade,
  } as unknown as Overview;
}

const PESSOAS: PessoaCartao[] = [
  {
    username: "marinacosta", name: "Marina Costa", has_avatar: false, city: "Vitória", state: "ES",
    objetivo: "Backend Java com Spring", cargo: "Desenvolvedora", senioridade: "pleno",
    stack: ["Java", "Spring Boot", "PostgreSQL", "Docker"], relacao: "nenhuma", friendship_id: null,
  },
  {
    username: "lucas_rocha", name: "Lucas Rocha", has_avatar: false, city: "Vila Velha", state: "ES",
    objetivo: "Fullstack TypeScript", cargo: null, senioridade: "junior",
    stack: ["React", "TypeScript", "Node.js"], relacao: "recebido", friendship_id: "exemplo",
  },
];

const LINGUAGENS = [
  ["java", "Java"], ["typescript", "TypeScript"], ["python", "Python"], ["go", "Go"],
].map(([id, rotulo]) => ({ value: id, label: rotulo, icon: iconeDaLinguagem(id) }));

// ---------------------------------------------------------------------------
// Peças
// ---------------------------------------------------------------------------

/** Uma tela de exemplo dentro de uma moldura de janela, sem responder a clique. */
function Janela({ titulo, descricao, children }: { titulo: string; descricao: string; children: ReactNode }) {
  return (
    <figure
      aria-label={descricao}
      style={{
        margin: 0,
        borderRadius: 16,
        background: PANEL,
        boxShadow: `0 24px 60px rgba(0,0,0,.45), 0 0 0 1px ${HAIRLINE}`,
        overflow: "hidden",
        minWidth: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "10px 14px", borderBottom: `1px solid ${HAIRLINE}` }}>
        {["#e5484d", "#f5a524", "#46a758"].map((cor) => (
          <span key={cor} aria-hidden style={{ width: 9, height: 9, borderRadius: "50%", background: cor, opacity: 0.55 }} />
        ))}
        <span style={{ marginLeft: 10, fontSize: 11.5, color: TEXT.faint }}>{titulo}</span>
      </div>
      {/* `inert` e não só pointer-events: tira também do teclado e do leitor de
          tela como controles — a descrição da figura diz o que ela mostra. */}
      <div {...({ inert: "" } as Record<string, string>)} style={{ padding: 16 }}>
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
        <Rotulo>{rotulo}</Rotulo>
        <h2 style={{ fontSize: "clamp(24px, 3vw, 32px)", lineHeight: 1.2, margin: "12px 0 14px", fontWeight: 600, letterSpacing: "-.02em" }}>
          {titulo}
        </h2>
        <p style={{ fontSize: 15.5, lineHeight: 1.7, color: TEXT.muted, margin: 0, maxWidth: "52ch" }}>{texto}</p>
        <ul style={{ listStyle: "none", padding: 0, margin: "18px 0 0", display: "flex", flexDirection: "column", gap: 9 }}>
          {pontos.map((ponto) => (
            <li key={ponto} style={{ display: "flex", gap: 10, fontSize: 14, color: TEXT.strong, lineHeight: 1.5 }}>
              <span aria-hidden style={{ color: C.verde, flex: "none" }}>✓</span>
              {ponto}
            </li>
          ))}
        </ul>
      </div>
      <div style={{ order: invertido ? 1 : 2, minWidth: 0 }}>{children}</div>
    </section>
  );
}

function Topo({ onNavigate }: { onNavigate: Navegar }) {
  return (
    <header
      style={{
        position: "sticky", top: 0, zIndex: 10,
        display: "flex", alignItems: "center", gap: 12,
        padding: "14px clamp(16px, 4vw, 40px)",
        background: "rgba(22,24,38,.82)", backdropFilter: "blur(10px)",
        borderBottom: `1px solid ${HAIRLINE}`,
      }}
    >
      <Logo size={30} />
      <span style={{ fontSize: 17, fontWeight: 600 }}>PathR</span>
      <nav style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
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

function Heroi({ onNavigate, panorama }: { onNavigate: Navegar; panorama: Overview }) {
  return (
    <section style={{ textAlign: "center", paddingTop: "clamp(48px, 9vw, 104px)" }}>
      <Rotulo>Plano de estudos para quem trabalha com tecnologia</Rotulo>
      <h1
        style={{
          fontSize: "clamp(34px, 6vw, 60px)", lineHeight: 1.05, letterSpacing: "-.035em",
          fontWeight: 650, margin: "18px auto 20px", maxWidth: "16ch",
        }}
      >
        Do seu currículo a um plano que{" "}
        <span style={{ background: `linear-gradient(90deg, ${ACC4}, ${C.verde})`, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
          se corrige toda semana
        </span>
      </h1>
      <p style={{ fontSize: "clamp(16px, 1.8vw, 19px)", lineHeight: 1.65, color: TEXT.muted, margin: "0 auto", maxWidth: "58ch" }}>
        Envie o currículo e diga aonde quer chegar. O PathR monta a trilha em fases, separa o material
        certo para cada módulo, mede o que você aprendeu de verdade e ajusta a rota com o que viu.
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 10, marginTop: 28 }}>
        <a href="/cadastro" className="btn btn-primary" style={{ padding: "12px 22px", fontSize: 15 }}
          onClick={(e) => { e.preventDefault(); onNavigate("/cadastro"); }}>
          Criar conta grátis
        </a>
        <a href="/entrar" className="btn btn-secondary" style={{ padding: "12px 22px", fontSize: 15 }}
          onClick={(e) => { e.preventDefault(); onNavigate("/entrar"); }}>
          Já tenho conta
        </a>
      </div>
      <div style={{ marginTop: "clamp(40px, 7vw, 72px)", textAlign: "left" }}>
        <Janela titulo="pathr.notter.com.br · Início" descricao="Painel inicial com sequência de estudo, progresso do plano e tempo estudado">
          <KpiCards overview={panorama} />
        </Janela>
      </div>
    </section>
  );
}

const PASSOS = [
  ["Envie o currículo", "A IA lê suas competências e o nível de cada uma. Nada de preencher uma lista de 200 tecnologias à mão."],
  ["Receba a trilha", "Fases e módulos ordenados pelo que o seu objetivo exige, no tamanho das horas que você tem por semana."],
  ["Estude e deixe ajustar", "Quiz, explicação com suas palavras e revisão espaçada movem o seu nível. A semana se remonta sozinha."],
];

function ComoFunciona() {
  return (
    <section>
      <div style={{ textAlign: "center", marginBottom: 32 }}>
        <Rotulo>Como funciona</Rotulo>
        <h2 style={{ fontSize: "clamp(24px, 3vw, 32px)", margin: "12px 0 0", fontWeight: 600, letterSpacing: "-.02em" }}>
          Três passos, e o plano trabalha por você
        </h2>
      </div>
      <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))", gap: 14 }}>
        {PASSOS.map(([titulo, texto], indice) => (
          <li key={titulo} style={{ padding: 22, borderRadius: 14, background: PANEL, boxShadow: `inset 0 0 0 1px ${HAIRLINE}` }}>
            <span style={{ display: "inline-grid", placeItems: "center", width: 32, height: 32, borderRadius: 10, background: "rgba(145,132,217,.16)", color: ACC3, fontWeight: 600 }}>
              {indice + 1}
            </span>
            <h3 style={{ fontSize: 17, margin: "14px 0 8px", fontWeight: 600 }}>{titulo}</h3>
            <p style={{ fontSize: 14, lineHeight: 1.6, color: TEXT.muted, margin: 0 }}>{texto}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function PreviaIdioma() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ fontSize: 11, color: ACC }}>reading · B1</div>
      <p style={{ fontSize: 16, lineHeight: 1.6, margin: 0 }}>
        The team will{" "}
        <span style={{ color: "#d2cefd", background: "rgba(145,132,217,.18)", borderRadius: 3, padding: "0 2px" }}>deploy</span>{" "}
        the new version on Friday. What happens on Friday?
      </p>
      <div style={{ padding: "10px 14px", borderRadius: 8, background: BG, boxShadow: `0 0 0 1px ${HAIRLINE}`, maxWidth: 300 }}>
        <div style={{ fontSize: 13.5 }}>deploy <span style={{ color: TEXT.faint, fontSize: 12 }}>/dɪˈplɔɪ/</span></div>
        <div style={{ color: ACC3, marginTop: 4 }}>implantar, publicar</div>
        <div style={{ fontSize: 12, color: TEXT.faint, marginTop: 4 }}>sinônimos: release, ship, roll out</div>
        <div style={{ fontSize: 11.5, color: ACC, marginTop: 8 }}>Entrou na sua revisão de vocabulário para hoje.</div>
      </div>
    </div>
  );
}

function PreviaCodigo() {
  const linhas = [
    ["// Um exemplo pronto, percorrido linha a linha", TEXT.faint],
    ["List<String> nomes = pessoas.stream()", TEXT.strong],
    ["    .filter(p -> p.idade() >= 18)", TEXT.strong],
    ["    .map(Pessoa::nome)", TEXT.strong],
    ["    .toList();", TEXT.strong],
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ width: 190 }}>
          <div style={{ fontSize: 11.5, color: TEXT.faint, marginBottom: 4 }}>Linguagem</div>
          <Select id="lp-linguagem" value="java" onChange={() => {}} options={LINGUAGENS} />
        </div>
        <div className="input" style={{ flex: 1, minWidth: 160, display: "flex", alignItems: "center", color: TEXT.muted }}>streams e lambdas</div>
      </div>
      <pre style={{ margin: 0, padding: 14, borderRadius: 10, background: BG, fontSize: 13, lineHeight: 1.7, overflowX: "auto" }}>
        {linhas.map(([texto, cor], i) => (
          <div key={i} style={{ color: cor as string }}>
            <span style={{ color: TEXT.faint, marginRight: 14 }}>{i + 1}</span>{texto}
          </div>
        ))}
      </pre>
      <div style={{ fontSize: 13, color: TEXT.muted }}>
        <span style={{ color: ACC4 }}>Linha 3</span> · o filtro descarta quem tem menos de 18 antes de qualquer outra etapa.
      </div>
    </div>
  );
}

const CUIDADOS = [
  ["Seus dados são seus", "Exporte tudo em um arquivo ou exclua a conta quando quiser."],
  ["Você decide quem te acha", "Aparecer nas sugestões é opcional, e e-mail nunca é mostrado a outra conta."],
  ["Sessão protegida", "Senha forte, segundo fator e chave de acesso do aparelho, se você preferir."],
];

function Cuidados() {
  return (
    <section>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))", gap: 14 }}>
        {CUIDADOS.map(([titulo, texto]) => (
          <div key={titulo} style={{ padding: 20, borderRadius: 14, boxShadow: `inset 0 0 0 1px ${HAIRLINE}` }}>
            <h3 style={{ fontSize: 15.5, margin: "0 0 6px", fontWeight: 600 }}>{titulo}</h3>
            <p style={{ fontSize: 13.5, lineHeight: 1.6, color: TEXT.muted, margin: 0 }}>{texto}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function LandingPage({ onNavigate }: { onNavigate: Navegar }) {
  const atividade = atividadeDeExemplo();
  const panorama = panoramaDeExemplo(atividade);

  return (
    <div style={{ minHeight: "100dvh", background: BG, color: TEXT.full, fontFamily: "Inter, system-ui, sans-serif" }}>
      <Topo onNavigate={onNavigate} />

      <main style={{ maxWidth: 1120, margin: "0 auto", padding: "0 clamp(16px, 4vw, 40px)", display: "flex", flexDirection: "column", gap: "clamp(48px, 7vw, 88px)" }}>
        <Heroi onNavigate={onNavigate} panorama={panorama} />

        <ComoFunciona />

        <Destaque
          larga
          rotulo="Constância"
          titulo="Um mapa do ano que mostra o que você estudou em cada dia"
          texto="Cada quadrado é um dia. Passe o mouse e veja o que foi feito — o artigo, o vídeo, o quiz — e quanto tempo levou. O buraco na sequência aparece antes de virar abandono."
          pontos={["Sequência e recorde que você protege", "Tempo de estudo medido pelo que foi lido e assistido", "Semana, mês e ano no mesmo painel"]}
        >
          <Janela titulo="Início · Sua constância" descricao="Mapa de calor do ano com os dias de estudo">
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
          <Janela titulo="Laboratório de código" descricao="Gerador de exemplos com seleção de linguagem e explicação por linha">
            <PreviaCodigo />
          </Janela>
        </Destaque>

        <Destaque
          rotulo="Idiomas"
          titulo="Inglês para o trabalho, no seu nível de verdade"
          texto="Um nivelamento CEFR que se adapta às respostas. Travou numa palavra? Toque nela: a tradução e os sinônimos aparecem, e a palavra entra na sua revisão."
          pontos={["Nivelamento adaptativo, de A1 a C2", "Consulta de palavra que vira revisão espaçada", "Treinos diários de leitura, escuta e escrita"]}
        >
          <Janela titulo="Idiomas · Nivelamento" descricao="Pergunta de nivelamento com a tradução de uma palavra consultada">
            <PreviaIdioma />
          </Janela>
        </Destaque>

        <Destaque
          invertido
          rotulo="Pessoas"
          titulo="Estude com quem está perto e quer chegar no mesmo lugar"
          texto="O PathR sugere contas da sua cidade e de quem estuda as mesmas tecnologias. Cada cartão mostra objetivo e stack — nunca e-mail."
          pontos={["Seu @ próprio para ser encontrado", "Sugestões por cidade, stack e objetivo", "Aparecer nas sugestões é escolha sua"]}
        >
          <Janela titulo="Amigos · Sugestões" descricao="Cartões de pessoas sugeridas com cidade, objetivo e tecnologias">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 230px), 1fr))", gap: 10 }}>
              {PESSOAS.map((pessoa) => (
                <CartaoPessoa key={pessoa.username} pessoa={pessoa} onMudou={() => {}} somenteLeitura />
              ))}
            </div>
          </Janela>
        </Destaque>

        <Cuidados />

        <section style={{ textAlign: "center", padding: "clamp(40px, 7vw, 80px) 24px", borderRadius: 24, background: `radial-gradient(120% 140% at 50% 0%, rgba(145,132,217,.22), transparent 60%), ${PANEL}`, boxShadow: `inset 0 0 0 1px ${HAIRLINE}` }}>
          <h2 style={{ fontSize: "clamp(26px, 4vw, 40px)", margin: 0, fontWeight: 650, letterSpacing: "-.025em" }}>
            Seu próximo nível começa pelo currículo que você já tem
          </h2>
          <p style={{ fontSize: 16, color: TEXT.muted, margin: "14px auto 26px", maxWidth: "48ch", lineHeight: 1.6 }}>
            Crie a conta, envie o currículo e veja o plano sair pronto em poucos minutos.
          </p>
          <a href="/cadastro" className="btn btn-primary" style={{ padding: "13px 26px", fontSize: 15.5 }}
            onClick={(e) => { e.preventDefault(); onNavigate("/cadastro"); }}>
            Criar conta grátis
          </a>
        </section>
      </main>

      <footer style={{ maxWidth: 1120, margin: "0 auto", padding: "40px clamp(16px, 4vw, 40px) 48px", display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center", color: TEXT.faint, fontSize: 13 }}>
        <Logo size={22} />
        <span>PathR · plano de estudos</span>
        <span style={{ marginLeft: "auto" }}>pathr.notter.com.br</span>
      </footer>
    </div>
  );
}
