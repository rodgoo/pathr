/**
 * Vagas reais para o perfil, e o que falta para cada uma.
 *
 * ## O que a tela promete
 *
 * - **Vaga real, de fonte confiável, com a fonte dita.** Gupy, Remotive,
 *   Adzuna e sites de vaga encontrados por buscador. O nome da fonte vai em
 *   cada cartão — é também o crédito que a Remotive pede.
 * - **A nota só existe quando o anúncio foi lido.** Resultado de buscador traz
 *   só o título; ali a tela diz "anúncio não lido" em vez de inventar número.
 * - **Toda lacuna tem um caminho.** "O que falta" separa obrigatório de
 *   desejável e, para cada lacuna, oferece curso com certificado (gratuito
 *   primeiro) e o botão de marcá-la como meta — o que alimenta Cursos e o
 *   ajuste do roadmap.
 *
 * O LinkedIn não entra por integração: não há API de vagas para terceiros. A
 * vaga do LinkedIn aparece quando o buscador a encontra, ou colando o texto.
 */

import { useState, type FormEvent } from "react";
import { jobs as jobsApi, tags as tagsApi } from "@/api/endpoints";
import type { Job, JobAnalysis, JobGap, JobList, JobRequirement } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useMutation, useQuery } from "@/hooks/useApi";
import { ACC, ACC4, C, HAIRLINE, SIZE, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";

type Filtro = "todas" | "remotas";

const FILTROS: readonly { value: Filtro; label: string }[] = [
  { value: "todas", label: "Todas" },
  { value: "remotas", label: "Remotas" },
];

const NOME_DA_FONTE: Record<keyof JobList["fontes"], string> = {
  gupy: "Gupy",
  remotive: "Remotive",
  adzuna: "Adzuna",
  busca: "Sites de vaga (LinkedIn, Vagas.com, Indeed…)",
};

const ESTADO_DA_FONTE = { ok: "ativa", erro: "fora do ar agora", sem_chave: "sem chave configurada" } as const;

const NIVEL = { junior: "Júnior", pleno: "Pleno", senior: "Sênior" } as const;

const SITUACAO: Record<JobRequirement["situacao"], { rotulo: string; cor: string }> = {
  tem: { rotulo: "você tem", cor: C.verde },
  parcial: { rotulo: "começando", cor: C.ambar },
  falta: { rotulo: "falta", cor: C.rosa },
  desconhecido: { rotulo: "fora do catálogo", cor: TEXT.faint },
};

function corDaNota(nota: number): string {
  return nota >= 70 ? C.verde : nota >= 40 ? C.ambar : C.rosa;
}

function haQuanto(dias: number | null): string | null {
  if (dias === null) return null;
  if (dias === 0) return "hoje";
  return dias === 1 ? "há 1 dia" : `há ${dias} dias`;
}

export function JobsPage() {
  const [filtro, setFiltro] = useState<Filtro>("todas");
  const [busca, setBusca] = useState("");
  const [termo, setTermo] = useState("");
  const lista = useQuery(() => jobsApi.list({ q: termo, remotas: filtro === "remotas" }), [termo, filtro]);

  function buscar(evento: FormEvent) {
    evento.preventDefault();
    setTermo(busca.trim());
  }

  return (
    <div style={SCREEN_IN}>
      <header style={{ marginBottom: 16.8 }}>
        <h1 style={{ fontSize: 28, margin: 0 }}>Vagas para você</h1>
        <p style={{ margin: "5.6px 0 0", fontSize: SIZE.corpo, color: TEXT.strong, maxWidth: "72ch" }}>
          Vagas reais de fontes confiáveis, ordenadas pelo quanto combinam com as suas competências. Em
          cada uma, veja o que falta e como chegar lá.
        </p>
      </header>

      <AnalisarVaga />

      <form
        onSubmit={buscar}
        style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "center", margin: "22.4px 0 11.2px" }}
      >
        <input
          className="input"
          aria-label="Buscar outro cargo ou tecnologia"
          placeholder="Outro cargo ou tecnologia (ex.: Desenvolvedor Java)"
          value={busca}
          onChange={(evento) => setBusca(evento.target.value)}
          style={{ flex: "1 1 260px" }}
        />
        <button type="submit" className="btn btn-secondary">
          <Icon name="search" size={15} />
          Buscar
        </button>
        {termo ? (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              setBusca("");
              setTermo("");
            }}
          >
            Voltar ao meu perfil
          </button>
        ) : null}
        <Segmented
          name="vagas-filtro"
          label="Tipo de vaga"
          value={filtro}
          options={FILTROS}
          onChange={setFiltro}
          style={{ marginLeft: "auto" }}
        />
      </form>

      {lista.loading ? <Loading label="Procurando vagas nas fontes…" /> : null}
      {lista.error ? <ErrorState message={lista.error} onRetry={lista.reload} /> : null}
      {lista.data && !lista.loading ? <Resultado dados={lista.data} /> : null}
    </div>
  );
}

function Resultado({ dados }: { dados: JobList }) {
  const { dispatch } = useAppState();

  if (dados.sem_perfil) {
    return (
      <EmptyState
        title="Diga o que você faz ou quer fazer"
        description="As vagas saem das suas competências e do seu objetivo. Cadastre suas tecnologias — ou busque um cargo acima."
        action={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => dispatch({ type: "navigate", screen: "config", settingsTab: "skills" })}
          >
            Cadastrar tecnologias
          </button>
        }
      />
    );
  }

  const fontes = Object.keys(dados.fontes) as (keyof JobList["fontes"])[];

  return (
    <>
      <div style={{ fontSize: 12, color: TEXT.muted, marginBottom: 11.2, lineHeight: 1.6 }}>
        Buscando por <span style={{ color: TEXT.full }}>{dados.termos.join(" · ")}</span> ·{" "}
        {dados.vagas.length} {dados.vagas.length === 1 ? "vaga" : "vagas"}
        <div style={{ color: TEXT.faint }}>
          Fontes:{" "}
          {fontes.map((fonte, posicao) => {
            const estado = dados.fontes[fonte] ?? "erro";
            return (
              <span key={fonte}>
                {posicao > 0 ? " · " : ""}
                {NOME_DA_FONTE[fonte]}{" "}
                <span style={{ color: estado === "ok" ? C.verde : C.ambar }}>({ESTADO_DA_FONTE[estado]})</span>
              </span>
            );
          })}
        </div>
      </div>

      {dados.vagas.length === 0 ? (
        <EmptyState
          title="Nenhuma vaga encontrada agora"
          description="As fontes não trouxeram vagas para estes termos. Tente outro cargo ou tecnologia na busca."
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
          {dados.vagas.map((vaga) => (
            <CartaoDaVaga key={vaga.id} vaga={vaga} />
          ))}
        </div>
      )}
    </>
  );
}

function CartaoDaVaga({ vaga }: { vaga: Job }) {
  const [aberta, setAberta] = useState(false);
  const analise = useMutation(() => jobsApi.analyze({ vaga_id: vaga.id }));
  const [resultado, setResultado] = useState<JobAnalysis | null>(null);
  const { nota, tem, falta, parcial } = vaga.compatibilidade;

  async function oQueFalta() {
    if (aberta) {
      setAberta(false);
      return;
    }
    setAberta(true);
    if (!resultado) {
      const achado = await analise.run();
      if (achado) setResultado(achado);
    }
  }

  const detalhes = [vaga.empresa, vaga.local, vaga.nivel ? NIVEL[vaga.nivel] : null, haQuanto(vaga.publicada_ha_dias)]
    .filter(Boolean)
    .join(" · ");

  return (
    <Panel pad={16.8}>
      <article aria-label={vaga.titulo}>
        <div style={{ display: "flex", gap: 14, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 280px", minWidth: 0 }}>
            <h2 style={{ fontSize: 15.5, fontWeight: 500, margin: 0, lineHeight: 1.35 }}>{vaga.titulo}</h2>
            <div style={{ fontSize: 12, color: TEXT.muted, marginTop: 3 }}>
              {detalhes ? `${detalhes} · ` : ""}via {vaga.fonte}
              {vaga.na_sua_regiao ? <span style={{ color: C.verde }}> · na sua região</span> : null}
            </div>
          </div>
          <Nota nota={nota} />
        </div>

        {nota !== null ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginTop: 11.2 }}>
            {tem.slice(0, 6).map((nome) => (
              <Pilula key={`t-${nome}`} cor={C.verde} texto={nome} comCheck />
            ))}
            {parcial.slice(0, 4).map((nome) => (
              <Pilula key={`p-${nome}`} cor={C.ambar} texto={nome} />
            ))}
            {falta.slice(0, 6).map((nome) => (
              <Pilula key={`f-${nome}`} cor={C.rosa} texto={`falta ${nome}`} />
            ))}
          </div>
        ) : (
          <p style={{ margin: "8.4px 0 0", fontSize: 12, color: TEXT.faint }}>
            Encontrada por buscador: o anúncio não foi lido aqui. Abra a vaga, ou peça a análise para lermos a
            página.
          </p>
        )}

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, marginTop: 11.2 }}>
          <a
            className="btn btn-primary"
            href={vaga.url}
            target="_blank"
            rel="noreferrer noopener"
            style={{ textDecoration: "none" }}
          >
            Ver vaga
            <Icon name="externalLink" size={14} />
          </a>
          <button type="button" className="btn btn-secondary" aria-expanded={aberta} onClick={() => void oQueFalta()}>
            {aberta ? "Esconder análise" : "O que falta para esta vaga"}
          </button>
        </div>

        {aberta ? (
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: `1px solid ${HAIRLINE}` }}>
            {analise.pending ? <Loading label="Lendo os requisitos da vaga…" /> : null}
            {analise.error ? <ErrorState message={analise.error} /> : null}
            {resultado ? <Analise analise={resultado} /> : null}
          </div>
        ) : null}
      </article>
    </Panel>
  );
}

function Nota({ nota }: { nota: number | null }) {
  if (nota === null) {
    return <span style={{ fontSize: 11.5, color: TEXT.faint, whiteSpace: "nowrap" }}>anúncio não lido</span>;
  }
  const cor = corDaNota(nota);
  return (
    <div
      role="meter"
      aria-label="Compatibilidade com o seu perfil"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={nota}
      style={{ minWidth: 120, textAlign: "right" }}
    >
      <div style={{ fontSize: 20, lineHeight: 1, color: cor }}>{nota}%</div>
      <div style={{ fontSize: 11, color: TEXT.faint, margin: "3px 0 5px" }}>combina com você</div>
      <div style={{ height: 5, borderRadius: 3, background: "rgba(233,233,237,.1)" }}>
        <div style={{ width: `${nota}%`, height: "100%", borderRadius: 3, background: cor }} />
      </div>
    </div>
  );
}

function Pilula({ cor, texto, comCheck }: { cor: string; texto: string; comCheck?: boolean }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 11.5,
        padding: "2px 8px",
        borderRadius: 5,
        background: tint(cor, 12),
        color: cor,
      }}
    >
      {comCheck ? <Icon name="check" size={11} /> : null}
      {texto}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Analisar uma vaga de fora da lista
// ---------------------------------------------------------------------------

function AnalisarVaga() {
  const [entrada, setEntrada] = useState("");
  const [resultado, setResultado] = useState<JobAnalysis | null>(null);
  const analise = useMutation((valor: string) =>
    /^https?:\/\/\S+$/i.test(valor) ? jobsApi.analyze({ url: valor }) : jobsApi.analyze({ texto: valor }),
  );

  async function analisar(evento: FormEvent) {
    evento.preventDefault();
    setResultado(null);
    const achado = await analise.run(entrada.trim());
    if (achado) setResultado(achado);
  }

  return (
    <Panel pad={16.8}>
      <Kicker style={{ display: "block", marginBottom: 5.6 }}>Analisar uma vaga específica</Kicker>
      <p style={{ margin: "0 0 11.2px", fontSize: 12.5, color: TEXT.muted }}>
        Cole o link ou o texto do anúncio. Vaga do LinkedIn costuma pedir login para abrir — nesse caso, cole o
        texto.
      </p>
      <form onSubmit={analisar} style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
        <textarea
          className="input"
          rows={3}
          aria-label="Link ou texto da vaga"
          placeholder="https://… ou o texto completo da vaga"
          value={entrada}
          onChange={(evento) => setEntrada(evento.target.value)}
          style={{ width: "100%", resize: "vertical" }}
        />
        <div>
          <button type="submit" className="btn btn-primary" disabled={analise.pending || entrada.trim().length < 8}>
            {analise.pending ? "Analisando…" : "Ver o que falta"}
          </button>
        </div>
      </form>
      {analise.error ? (
        <p role="alert" style={{ margin: "8.4px 0 0", fontSize: 12.5, color: C.ambar }}>
          {analise.error}
        </p>
      ) : null}
      {resultado ? (
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: `1px solid ${HAIRLINE}` }}>
          <Analise analise={resultado} mostrarTitulo />
        </div>
      ) : null}
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// O resultado da análise
// ---------------------------------------------------------------------------

function Analise({ analise, mostrarTitulo }: { analise: JobAnalysis; mostrarTitulo?: boolean }) {
  const { dispatch } = useAppState();
  const obrigatorios = analise.requisitos.filter((r) => r.obrigatorio);
  const desejaveis = analise.requisitos.filter((r) => !r.obrigatorio);

  return (
    <section aria-label="O que falta para a vaga">
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div style={{ flex: "1 1 280px" }}>
          {mostrarTitulo ? (
            <div style={{ fontSize: 15, fontWeight: 500 }}>
              {analise.titulo}
              {analise.empresa ? (
                <span style={{ color: TEXT.muted, fontWeight: 400 }}> · {analise.empresa}</span>
              ) : null}
            </div>
          ) : null}
          {analise.resumo ? (
            <p style={{ margin: "3px 0 0", fontSize: 12.5, color: TEXT.strong }}>{analise.resumo}</p>
          ) : null}
          {!analise.usou_ia ? (
            <p style={{ margin: "3px 0 0", fontSize: 11.5, color: TEXT.faint }}>
              Análise simplificada: as tecnologias citadas no anúncio, todas tratadas como obrigatórias.
            </p>
          ) : null}
        </div>
        <Nota nota={analise.nota} />
      </div>

      <Requisitos titulo="Obrigatórios" lista={obrigatorios} />
      <Requisitos titulo="Desejáveis" lista={desejaveis} />

      <Kicker style={{ display: "block", margin: "16.8px 0 8.4px" }}>
        {analise.lacunas.length ? "O que falta, e como chegar lá" : "Nada falta no que o catálogo reconhece"}
      </Kicker>
      <div style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
        {analise.lacunas.map((lacuna) => (
          <Lacuna key={lacuna.nome} lacuna={lacuna} />
        ))}
      </div>
      {analise.lacunas.some((l) => l.cursos.length > 0) ? (
        <button
          type="button"
          className="btn btn-ghost"
          style={{ marginTop: 8.4, fontSize: SIZE.apoio }}
          onClick={() => dispatch({ type: "navigate", screen: "cursos" })}
        >
          Ver todos os cursos com certificado
        </button>
      ) : null}
    </section>
  );
}

function Requisitos({ titulo, lista }: { titulo: string; lista: JobRequirement[] }) {
  if (!lista.length) return null;
  return (
    <div style={{ marginTop: 11.2 }}>
      <div style={{ fontSize: 11.5, color: TEXT.faint, marginBottom: 5.6 }}>{titulo}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6 }}>
        {lista.map((req) => {
          const { rotulo, cor } = SITUACAO[req.situacao];
          return (
            <span
              key={req.nome}
              style={{
                fontSize: 12,
                padding: "3px 8px",
                borderRadius: 5,
                background: "rgba(233,233,237,.06)",
                color: cor,
              }}
            >
              {req.nome} <span style={{ opacity: 0.75 }}>· {rotulo}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

function Lacuna({ lacuna }: { lacuna: JobGap }) {
  const [meta, setMeta] = useState(lacuna.e_meta);
  const marcar = useMutation(async () => {
    if (lacuna.user_tag_id) return tagsApi.update(lacuna.user_tag_id, { is_target: true });
    if (lacuna.tag_id) return tagsApi.add({ tag_id: lacuna.tag_id, proficiency: 0, is_target: true });
    return null;
  });

  return (
    <div style={{ padding: "11.2px 12.6px", borderRadius: 8, background: "rgba(233,233,237,.04)" }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8.4 }}>
        <span style={{ fontSize: 14, color: TEXT.full }}>{lacuna.nome}</span>
        <span style={{ fontSize: 11, color: lacuna.obrigatorio ? C.rosa : TEXT.faint }}>
          {lacuna.obrigatorio ? "obrigatório" : "desejável"}
          {lacuna.situacao === "parcial" ? " · você está começando" : ""}
        </span>
        <span style={{ marginLeft: "auto", fontSize: 12 }}>
          {lacuna.no_roadmap ? (
            <span style={{ color: ACC4 }}>já está no seu roadmap</span>
          ) : meta ? (
            <span style={{ color: C.verde }}>meta marcada</span>
          ) : lacuna.tag_id ? (
            <button
              type="button"
              className="btn btn-ghost"
              disabled={marcar.pending}
              style={{ fontSize: 12 }}
              onClick={async () => {
                const feito = await marcar.run();
                if (feito) setMeta(true);
              }}
            >
              {marcar.pending ? "Marcando…" : "Marcar como meta"}
            </button>
          ) : null}
        </span>
      </div>
      {marcar.error ? <div style={{ fontSize: 12, color: C.ambar, marginTop: 4 }}>{marcar.error}</div> : null}
      {lacuna.cursos.length ? (
        <ul
          style={{ listStyle: "none", margin: "8.4px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 4 }}
        >
          {lacuna.cursos.map((curso) => (
            <li key={curso.id} style={{ fontSize: 12.5, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
              <Icon name="award" size={13} style={{ color: curso.gratuito ? C.verde : C.ambar }} />
              <a href={curso.url} target="_blank" rel="noreferrer noopener" style={{ color: ACC }}>
                {curso.titulo}
              </a>
              <span style={{ color: TEXT.faint }}>
                {curso.emissor} · certificado {curso.gratuito ? "gratuito" : "pago"}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <div style={{ fontSize: 12, color: TEXT.faint, marginTop: 4 }}>
          Sem curso com certificado para isto no catálogo. Marcar como meta leva o tema para o seu roadmap.
        </div>
      )}
    </div>
  );
}
