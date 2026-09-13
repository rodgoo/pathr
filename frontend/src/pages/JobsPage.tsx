/**
 * Vagas reais para o perfil, e o que falta para cada uma.
 *
 * ## O que a tela promete
 *
 * - **A de cima é a que mais combina.** O número do cartão ("combina com
 *   você") e a ordem da lista são a mesma conta: stack em comum, cobertura dos
 *   requisitos, objetivo e nível.
 * - **Só vaga que dá para aceitar.** Presencial e híbrida dentro do raio da
 *   cidade escolhida em Configurações; remota de qualquer lugar.
 * - **O que falta aparece sozinho.** Cada cartão já traz as lacunas, com curso
 *   com certificado (gratuito primeiro) e o botão de marcar como meta — sem
 *   clique, sem esperar IA. A leitura por IA fica para a vaga cujo anúncio a
 *   fonte não mandou inteiro.
 * - **Voltar à tela não busca de novo.** A lista fica guardada; "Atualizar"
 *   vai às fontes quando a pessoa quer vagas novas.
 * - **Vaga real, de fonte confiável, com a fonte dita** em cada cartão — é
 *   também o crédito que a Remotive pede.
 *
 * O LinkedIn não entra por integração: não há API de vagas para terceiros. A
 * vaga do LinkedIn aparece quando o buscador a encontra, ou colando o texto.
 */

import { useEffect, useState, type FormEvent } from "react";
import { jobs as jobsApi, tags as tagsApi } from "@/api/endpoints";
import type {
  Job,
  JobAnalysis,
  JobCourse,
  JobEnglish,
  JobGap,
  JobList,
  JobListGap,
  JobRequirement,
} from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { messageFor, useMutation, useQuery } from "@/hooks/useApi";
import { vagasGuardadas } from "@/lib/vagasGuardadas";
import { ACC, ACC4, C, HAIRLINE, SIZE, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";

import { linkExterno } from "@/lib/linkExterno";
type Filtro = "todas" | "remotas";
type Alcance = "todas" | "nacionais" | "internacionais";

const FILTROS: readonly { value: Filtro; label: string }[] = [
  { value: "todas", label: "Todas" },
  { value: "remotas", label: "Remotas" },
];

const ALCANCES: readonly { value: Alcance; label: string }[] = [
  { value: "todas", label: "Brasil e exterior" },
  { value: "nacionais", label: "Nacionais" },
  { value: "internacionais", label: "Internacionais" },
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
  sem_nivel: { rotulo: "faça o nivelamento", cor: C.azul },
  tem: { rotulo: "você tem", cor: C.verde },
  parcial: { rotulo: "começando", cor: C.ambar },
  falta: { rotulo: "falta", cor: C.rosa },
  desconhecido: { rotulo: "fora do catálogo", cor: TEXT.faint },
};

/** Quantas lacunas o cartão mostra antes do "ver todas". */
const LACUNAS_VISIVEIS = 4;

function corDaNota(nota: number): string {
  return nota >= 70 ? C.verde : nota >= 40 ? C.ambar : C.rosa;
}

function haQuanto(dias: number | null): string | null {
  if (dias === null) return null;
  if (dias === 0) return "hoje";
  return dias === 1 ? "há 1 dia" : `há ${dias} dias`;
}

function minutosDesde(iso?: string): string | null {
  if (!iso) return null;
  const minutos = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutos < 1) return "agora";
  if (minutos < 60) return `há ${minutos} min`;
  const horas = Math.round(minutos / 60);
  return horas === 1 ? "há 1 hora" : `há ${horas} horas`;
}

function juntar(nomes: string[]): string {
  if (nomes.length <= 1) return nomes.join("");
  return `${nomes.slice(0, -1).join(", ")} e ${nomes[nomes.length - 1]}`;
}

export function JobsPage() {
  const [filtro, setFiltro] = useState<Filtro>("todas");
  const [alcance, setAlcance] = useState<Alcance>("todas");
  const [busca, setBusca] = useState("");
  const [termo, setTermo] = useState("");
  const [atualizando, setAtualizando] = useState(false);
  const [erroAoAtualizar, setErroAoAtualizar] = useState<string | null>(null);

  // Guardada: voltar à tela devolve a lista que estava aqui, sem ir às fontes.
  // Os filtros de "onde" e "tipo" filtram esta mesma lista — trocar de aba
  // não é uma busca nova.
  const lista = useQuery(async () => {
    const guardada = vagasGuardadas.get(termo);
    if (guardada) return guardada;
    const dados = await jobsApi.list({ q: termo });
    vagasGuardadas.set(termo, dados);
    return dados;
  }, [termo]);

  async function atualizar() {
    setAtualizando(true);
    setErroAoAtualizar(null);
    try {
      const dados = await jobsApi.list({ q: termo, atualizar: true });
      vagasGuardadas.set(termo, dados);
      lista.set(() => dados);
    } catch (caught) {
      setErroAoAtualizar(messageFor(caught));
    } finally {
      setAtualizando(false);
    }
  }

  function buscar(evento: FormEvent) {
    evento.preventDefault();
    setTermo(busca.trim());
  }

  return (
    <div style={SCREEN_IN}>
      <header style={{ marginBottom: 16.8 }}>
        <h1 style={{ fontSize: 28, margin: 0 }}>Vagas para você</h1>
        <p style={{ margin: "5.6px 0 0", fontSize: SIZE.corpo, color: TEXT.strong, maxWidth: "72ch" }}>
          Vagas reais de fontes confiáveis, na sua região ou remotas, da que mais tem a cara da sua stack e do
          seu objetivo para a que menos. Em cada uma, o que falta e como chegar lá.
        </p>
      </header>

      <form
        onSubmit={buscar}
        style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "center", margin: "0 0 8.4px" }}
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
            <Icon name="arrowLeft" size={15} />
            Voltar ao meu perfil
          </button>
        ) : null}
      </form>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, marginBottom: 11.2, alignItems: "center" }}>
        <Segmented name="vagas-alcance" label="Onde" value={alcance} options={ALCANCES} onChange={setAlcance} />
        <Segmented name="vagas-filtro" label="Tipo de vaga" value={filtro} options={FILTROS} onChange={setFiltro} />
        {lista.data && !lista.data.sem_perfil ? (
          <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 8.4 }}>
            <span style={{ fontSize: 11.5, color: TEXT.faint }}>
              {atualizando ? "procurando vagas novas…" : `atualizado ${minutosDesde(lista.data.buscado_em) ?? ""}`}
            </span>
            <button type="button" className="btn btn-secondary" onClick={() => void atualizar()} disabled={atualizando}>
              <Icon name="refresh" size={15} />
              {atualizando ? "Atualizando…" : "Atualizar"}
            </button>
          </span>
        ) : null}
      </div>
      {erroAoAtualizar ? (
        <p role="alert" style={{ margin: "0 0 11.2px", fontSize: 12.5, color: C.ambar }}>
          Não consegui atualizar agora ({erroAoAtualizar}). A lista abaixo é a anterior.
        </p>
      ) : null}

      {lista.loading ? <Loading label="Procurando vagas nas fontes…" /> : null}
      {lista.error ? <ErrorState message={lista.error} onRetry={lista.reload} /> : null}
      {lista.data && !lista.loading ? <Resultado dados={lista.data} filtro={filtro} alcance={alcance} /> : null}

      <div style={{ marginTop: 22.4 }}>
        <AnalisarVaga />
      </div>
    </div>
  );
}

function Resultado({ dados, filtro, alcance }: { dados: JobList; filtro: Filtro; alcance: Alcance }) {
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
            <Icon name="plus" size={15} />
            Cadastrar tecnologias
          </button>
        }
      />
    );
  }

  const fontes = Object.keys(dados.fontes) as (keyof JobList["fontes"])[];
  const visiveis = dados.vagas.filter(
    (vaga) =>
      (filtro === "todas" || vaga.remota === true) &&
      (alcance === "todas" || (alcance === "internacionais") === vaga.internacional),
  );

  return (
    <>
      <div style={{ fontSize: 12, color: TEXT.muted, marginBottom: 11.2, lineHeight: 1.6 }}>
        Buscando por <span style={{ color: TEXT.full }}>{dados.termos.join(" · ")}</span> ·{" "}
        {visiveis.length} {visiveis.length === 1 ? "vaga" : "vagas"} · seu inglês:{" "}
        {dados.nivel_ingles ? (
          <span style={{ color: TEXT.full }}>{dados.nivel_ingles}</span>
        ) : (
          <button
            type="button"
            className="btn btn-ghost"
            style={{ fontSize: 12, padding: 0, minHeight: 0 }}
            onClick={() => dispatch({ type: "navigate", screen: "ingles" })}
          >
            sem nivelamento — fazer agora
          </button>
        )}
        <Regiao regiao={dados.regiao} />
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

      {visiveis.length === 0 ? (
        <EmptyState
          title="Nenhuma vaga encontrada agora"
          description="As fontes não trouxeram vagas para estes termos e filtros. Tente outro cargo ou tecnologia, aumente o raio da sua região ou aperte Atualizar."
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
          {visiveis.map((vaga) => (
            <CartaoDaVaga key={vaga.id} vaga={vaga} cursos={dados.cursos ?? {}} />
          ))}
        </div>
      )}
    </>
  );
}

/** Onde as vagas presenciais podem estar, e o atalho para mudar. */
function Regiao({ regiao }: { regiao: JobList["regiao"] }) {
  const { dispatch } = useAppState();
  let texto: string;
  if (!regiao) {
    texto = "Sem cidade no perfil: vagas presenciais de todo o Brasil aparecem.";
  } else if (regiao.raio_km === 0) {
    texto = "Só vagas remotas.";
  } else if (regiao.cidade) {
    texto = `Presenciais e híbridas até ${regiao.raio_km} km de ${regiao.cidade} - ${regiao.uf} · remotas de qualquer lugar.`;
  } else {
    texto = `Presenciais e híbridas em ${regiao.uf} · remotas de qualquer lugar.`;
  }
  return (
    <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
      <Icon name="mapPin" size={13} style={{ color: ACC4 }} />
      <span>{texto}</span>
      <button
        type="button"
        className="btn btn-ghost"
        style={{ fontSize: 12, padding: "0 4px", minHeight: 0 }}
        onClick={() => dispatch({ type: "navigate", screen: "config", settingsTab: "objetivo" })}
      >
        <Icon name="pencil" size={13} />
        {regiao ? "Mudar região" : "Definir região"}
      </button>
    </div>
  );
}

function CartaoDaVaga({ vaga, cursos }: { vaga: Job; cursos: Record<string, JobCourse[]> }) {
  const [aberta, setAberta] = useState(false);
  const [descricao, setDescricao] = useState(false);
  const analise = useMutation(() => jobsApi.analyze({ vaga_id: vaga.id }));
  const [resultado, setResultado] = useState<JobAnalysis | null>(null);
  const { tem, parcial, falta } = vaga.compatibilidade;
  const lido = !vaga.so_link && !vaga.so_trecho;
  const nota = vaga.combina ?? vaga.compatibilidade.nota;

  async function lerAnuncio() {
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

  const onde = vaga.distancia_km !== null && vaga.distancia_km !== undefined && vaga.remota !== true
    ? `${vaga.local ?? "Presencial"} · a ${vaga.distancia_km} km`
    : vaga.local;
  const detalhes = [vaga.empresa, onde, vaga.nivel ? NIVEL[vaga.nivel] : null, haQuanto(vaga.publicada_ha_dias)]
    .filter(Boolean)
    .join(" · ");
  const pedidas = [...tem, ...parcial, ...falta];
  const sobre = vaga.sobre;
  const temDescricao = Boolean(sobre && (sobre.faz.length || sobre.pede.length || sobre.diferenciais.length));

  return (
    <Panel pad={16.8}>
      <article aria-label={vaga.titulo}>
        <div style={{ display: "flex", gap: 14, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 280px", minWidth: 0 }}>
            <h2 style={{ fontSize: 15.5, fontWeight: 500, margin: 0, lineHeight: 1.35 }}>{vaga.titulo}</h2>
            <div style={{ fontSize: 12, color: TEXT.muted, marginTop: 3 }}>
              {vaga.internacional ? <span style={{ color: C.azul }}>Internacional · </span> : null}
              {detalhes ? `${detalhes} · ` : ""}via {vaga.fonte}
              {vaga.na_sua_regiao ? <span style={{ color: C.verde }}> · na sua região</span> : null}
            </div>
          </div>
          <Nota nota={nota} estimada={!lido} />
        </div>

        {/* O que é a vaga e para quem: a apresentação do anúncio e a frase
            montada com o nível e as tecnologias que ele pede. */}
        {sobre?.apresentacao ? (
          <p style={{ margin: "8.4px 0 0", fontSize: 12.5, color: TEXT.strong, lineHeight: 1.55, maxWidth: "95ch" }}>
            {sobre.apresentacao}
          </p>
        ) : null}
        {pedidas.length ? (
          <p style={{ margin: "5.6px 0 0", fontSize: 12.5, color: TEXT.muted }}>
            <span style={{ color: TEXT.faint }}>Para quem: </span>
            {vaga.nivel ? `nível ${NIVEL[vaga.nivel]}, ` : ""}
            com {juntar(pedidas.slice(0, 6))}
            {pedidas.length > 6 ? ` e mais ${pedidas.length - 6}` : ""}.
          </p>
        ) : null}

        <Afinidade afinidade={vaga.afinidade} />
        <SeloDeIngles ingles={vaga.ingles} />

        {tem.length ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginTop: 11.2 }}>
            {tem.slice(0, 8).map((nome) => (
              <Pilula key={`t-${nome}`} cor={C.verde} texto={nome} comCheck />
            ))}
          </div>
        ) : null}

        {temDescricao ? (
          <button
            type="button"
            className="btn btn-ghost"
            aria-expanded={descricao}
            onClick={() => setDescricao((valor) => !valor)}
            style={{ fontSize: 12, marginTop: 8.4, padding: "2px 4px" }}
          >
            <Icon name="chevronDown" size={14} style={{ transform: descricao ? "rotate(180deg)" : undefined }} />
            {descricao ? "Esconder descrição" : "Ver descrição da vaga"}
          </button>
        ) : null}
        {descricao && sobre ? <Descricao sobre={sobre} /> : null}

        {lido ? (
          <OQueFalta lacunas={vaga.lacunas ?? []} cursos={cursos} />
        ) : (
          <p style={{ margin: "11.2px 0 0", fontSize: 12, color: TEXT.faint }}>
            {vaga.so_trecho
              ? "A fonte mandou só um trecho do anúncio: a nota é estimada pelo título. Leia o anúncio completo para ver o que falta."
              : "Encontrada por buscador: o anúncio não foi lido aqui, e a nota é estimada pelo título."}
          </p>
        )}

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, marginTop: 11.2 }}>
          <a
            className="btn btn-primary"
            href={linkExterno(vaga.url)}
            target="_blank"
            rel="noreferrer noopener"
            style={{ textDecoration: "none" }}
          >
            Ver vaga
            <Icon name="externalLink" size={14} />
          </a>
          {!lido ? (
            <button type="button" className="btn btn-secondary" aria-expanded={aberta} onClick={() => void lerAnuncio()}>
              <Icon name="search" size={15} />
              {aberta ? "Esconder análise" : "Ler o anúncio completo"}
            </button>
          ) : null}
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

function Descricao({ sobre }: { sobre: NonNullable<Job["sobre"]> }) {
  const partes: [string, string[]][] = [
    ["O que você vai fazer", sobre.faz],
    ["O que pede", sobre.pede],
    ["Diferenciais", sobre.diferenciais],
  ];
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
        gap: "8.4px 16.8px",
        marginTop: 8.4,
        padding: "11.2px 12.6px",
        borderRadius: 8,
        background: "rgba(233,233,237,.04)",
      }}
    >
      {partes
        .filter(([, itens]) => itens.length)
        .map(([titulo, itens]) => (
          <div key={titulo}>
            <div style={{ fontSize: 11.5, color: TEXT.faint, marginBottom: 4 }}>{titulo}</div>
            <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12.5, color: TEXT.strong, lineHeight: 1.5 }}>
              {itens.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
    </div>
  );
}

/** As lacunas da vaga, já calculadas na listagem. */
function OQueFalta({ lacunas, cursos }: { lacunas: JobListGap[]; cursos: Record<string, JobCourse[]> }) {
  const [todas, setTodas] = useState(false);
  if (!lacunas.length) {
    return (
      <p style={{ margin: "11.2px 0 0", fontSize: 12.5, color: C.verde, display: "flex", alignItems: "center", gap: 5 }}>
        <Icon name="check" size={14} />
        Você tem tudo o que o anúncio cita do catálogo.
      </p>
    );
  }
  const obrigatorias = lacunas.filter((l) => l.obrigatorio).length;
  const mostradas = todas ? lacunas : lacunas.slice(0, LACUNAS_VISIVEIS);
  return (
    <section aria-label="O que falta para a vaga" style={{ marginTop: 11.2 }}>
      <div style={{ fontSize: 11.5, color: TEXT.faint, marginBottom: 5.6 }}>
        O que falta · {lacunas.length} {lacunas.length === 1 ? "item" : "itens"}
        {obrigatorias ? `, ${obrigatorias} ${obrigatorias === 1 ? "obrigatório" : "obrigatórios"}` : ""}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5.6 }}>
        {mostradas.map((lacuna) => (
          <LacunaCompacta key={lacuna.slug} lacuna={lacuna} cursos={cursos[lacuna.slug] ?? []} />
        ))}
      </div>
      {lacunas.length > LACUNAS_VISIVEIS ? (
        <button
          type="button"
          className="btn btn-ghost"
          aria-expanded={todas}
          onClick={() => setTodas((valor) => !valor)}
          style={{ fontSize: 12, marginTop: 4, padding: "2px 4px" }}
        >
          <Icon name="chevronDown" size={14} style={{ transform: todas ? "rotate(180deg)" : undefined }} />
          {todas ? "Mostrar menos" : `Ver todas as ${lacunas.length}`}
        </button>
      ) : null}
    </section>
  );
}

/** Marca a lacuna como meta. Quem já estava começando continua no nível que
 * tinha: só vira meta, sem proficiência nova. */
function useMarcarMeta(lacuna: { user_tag_id: string | null; tag_id: string | null; e_meta: boolean }) {
  const [meta, setMeta] = useState(lacuna.e_meta);
  const marcar = useMutation(async () => {
    if (lacuna.user_tag_id) return tagsApi.update(lacuna.user_tag_id, { is_target: true });
    if (lacuna.tag_id) return tagsApi.add({ tag_id: lacuna.tag_id, proficiency: 0, is_target: true });
    return null;
  });
  useEffect(() => setMeta(lacuna.e_meta), [lacuna.e_meta]);
  async function executar() {
    const feito = await marcar.run();
    if (feito) setMeta(true);
  }
  return { meta, executar, pending: marcar.pending, error: marcar.error };
}

function AcaoDaLacuna({
  lacuna,
}: {
  lacuna: { idioma?: boolean; situacao: string; no_roadmap: boolean; tag_id: string | null; user_tag_id: string | null; e_meta: boolean };
}) {
  const { dispatch } = useAppState();
  const { meta, executar, pending, error } = useMarcarMeta(lacuna);
  if (lacuna.idioma) {
    return (
      <button
        type="button"
        className="btn btn-ghost"
        style={{ fontSize: 12 }}
        onClick={() => dispatch({ type: "navigate", screen: "ingles" })}
      >
        <Icon name="globe" size={14} />
        {lacuna.situacao === "sem_nivel" ? "Fazer o nivelamento" : "Treinar inglês"}
      </button>
    );
  }
  if (lacuna.no_roadmap) return <span style={{ color: ACC4, fontSize: 12 }}>já está no seu roadmap</span>;
  if (meta) {
    return (
      <span style={{ color: C.verde, fontSize: 12, display: "inline-flex", alignItems: "center", gap: 4 }}>
        <Icon name="check" size={13} />
        meta marcada
      </span>
    );
  }
  if (!lacuna.tag_id) return null;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      {error ? <span style={{ fontSize: 11.5, color: C.ambar }}>{error}</span> : null}
      <button type="button" className="btn btn-ghost" disabled={pending} style={{ fontSize: 12 }} onClick={() => void executar()}>
        <Icon name="flag" size={14} />
        {pending ? "Marcando…" : "Marcar como meta"}
      </button>
    </span>
  );
}

function LacunaCompacta({ lacuna, cursos }: { lacuna: JobListGap; cursos: JobCourse[] }) {
  const curso = cursos[0];
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 4,
        padding: "6px 10px",
        borderRadius: 7,
        background: "rgba(233,233,237,.04)",
      }}
    >
      {/* Nome e ação na MESMA linha: a ação fica à direita do que ela afeta,
          e não caída numa linha própria embaixo do certificado. */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ flex: 1, minWidth: 0, display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "2px 8px" }}>
          <span style={{ fontSize: 13, color: lacuna.situacao === "falta" ? C.rosa : C.ambar }}>{lacuna.nome}</span>
          <span style={{ fontSize: 11, color: lacuna.obrigatorio ? TEXT.muted : TEXT.faint }}>
            {lacuna.obrigatorio ? "obrigatório" : "diferencial"}
            {lacuna.situacao === "parcial" ? (lacuna.idioma ? " · um degrau abaixo" : " · você está começando") : ""}
            {lacuna.situacao === "sem_nivel" ? " · sem nivelamento" : ""}
          </span>
        </span>
        <span style={{ flex: "none" }}>
          <AcaoDaLacuna lacuna={lacuna} />
        </span>
      </div>
      {curso ? (
        // Texto corrido, e não `inline-flex`: com flex, título e preço viravam
        // blocos separados e o "· pago" caía sozinho numa coluna estreita ao
        // lado de um título quebrado em duas linhas.
        <a
          href={linkExterno(curso.url)}
          target="_blank"
          rel="noreferrer noopener"
          style={{ fontSize: 12, color: ACC, lineHeight: 1.45 }}
          title={`${curso.emissor} · certificado ${curso.gratuito ? "gratuito" : "pago"}`}
        >
          <Icon
            name="award"
            size={13}
            style={{ color: curso.gratuito ? C.verde : C.ambar, verticalAlign: "-2px", marginRight: 4 }}
          />
          {curso.titulo}
          <span style={{ color: TEXT.faint, whiteSpace: "nowrap" }}> · {curso.gratuito ? "gratuito" : "pago"}</span>
        </a>
      ) : null}
    </div>
  );
}

const INGLES: Record<NonNullable<JobEnglish["situacao"]>, { cor: string; texto: (i: JobEnglish) => string }> = {
  tem: { cor: C.verde, texto: (i) => `Inglês ${i.exigido} pedido · você tem ${i.seu}` },
  parcial: { cor: C.ambar, texto: (i) => `Inglês ${i.exigido} pedido · você ${i.seu}, um degrau abaixo` },
  falta: { cor: C.rosa, texto: (i) => `Inglês ${i.exigido} pedido · você ${i.seu}` },
  sem_nivel: { cor: C.azul, texto: (i) => `Inglês ${i.exigido} pedido · faça o nivelamento para comparar` },
};

/** Por que esta vaga está na lista: a stack que ela pede e o objetivo. */
function Afinidade({ afinidade }: { afinidade?: Job["afinidade"] }) {
  if (!afinidade) return null;
  const quantas = afinidade.stack_em_comum.length;
  if (!quantas && !afinidade.objetivo) return null;
  return (
    <div style={{ marginTop: 8.4, fontSize: 12, color: TEXT.strong, display: "flex", flexWrap: "wrap", gap: "4px 12px" }}>
      {quantas ? (
        <span title={afinidade.stack_em_comum.join(", ")} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <Icon name="code" size={13} style={{ color: C.verde }} />
          {quantas} {quantas === 1 ? "tecnologia" : "tecnologias"} da sua stack
        </span>
      ) : null}
      {afinidade.objetivo ? (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <Icon name="flag" size={13} style={{ color: ACC4 }} />
          combina com seu objetivo
        </span>
      ) : null}
    </div>
  );
}

function SeloDeIngles({ ingles }: { ingles: JobEnglish }) {
  if (!ingles.situacao) return null;
  const { cor, texto } = INGLES[ingles.situacao];
  return (
    <div style={{ marginTop: 8.4, fontSize: 12, color: cor, display: "flex", alignItems: "center", gap: 5 }}>
      <Icon name="globe" size={13} />
      {texto(ingles)}
    </div>
  );
}

function Nota({ nota, estimada }: { nota: number | null | undefined; estimada?: boolean }) {
  if (nota === null || nota === undefined) {
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
      // Número, legenda e barra alinhados pela mesma borda esquerda e na
      // mesma largura. Alinhados à direita, no celular — onde o bloco desce
      // para uma linha própria — o número ficava solto no meio, sem
      // relação com o começo da barra.
      style={{ width: 150, maxWidth: "100%" }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span style={{ fontSize: 20, lineHeight: 1, color: cor }}>{nota}%</span>
        <span style={{ fontSize: 11, color: TEXT.faint }}>
          {estimada ? "estimado pelo título" : "combina com você"}
        </span>
      </div>
      <div style={{ height: 5, marginTop: 6, borderRadius: 3, background: "rgba(233,233,237,.1)" }}>
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
        Achou uma vaga fora desta lista? Cole o link ou o texto do anúncio. Vaga do LinkedIn costuma pedir login
        para abrir — nesse caso, cole o texto.
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
            <Icon name="search" size={15} />
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
// O resultado da análise por IA
// ---------------------------------------------------------------------------

function Analise({ analise, mostrarTitulo }: { analise: JobAnalysis; mostrarTitulo?: boolean }) {
  const { dispatch } = useAppState();
  const obrigatorios = analise.requisitos.filter((r) => r.obrigatorio);
  const desejaveis = analise.requisitos.filter((r) => !r.obrigatorio);

  return (
    <section aria-label="Análise completa da vaga">
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
          <Icon name="award" size={15} />
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
  return (
    <div style={{ padding: "11.2px 12.6px", borderRadius: 8, background: "rgba(233,233,237,.04)" }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8.4 }}>
        <span style={{ fontSize: 14, color: TEXT.full }}>{lacuna.nome}</span>
        <span style={{ fontSize: 11, color: lacuna.obrigatorio ? C.rosa : TEXT.faint }}>
          {lacuna.obrigatorio ? "obrigatório" : "desejável"}
          {lacuna.situacao === "parcial" ? (lacuna.idioma ? " · um degrau abaixo" : " · você está começando") : ""}
          {lacuna.situacao === "sem_nivel" ? " · sem nivelamento para comparar" : ""}
        </span>
        <span style={{ marginLeft: "auto", fontSize: 12 }}>
          <AcaoDaLacuna lacuna={lacuna} />
        </span>
      </div>
      {lacuna.cursos.length ? (
        <ul
          style={{ listStyle: "none", margin: "8.4px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 4 }}
        >
          {lacuna.cursos.map((curso) => (
            <li key={curso.id} style={{ fontSize: 12.5, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
              <Icon name="award" size={13} style={{ color: curso.gratuito ? C.verde : C.ambar }} />
              <a href={linkExterno(curso.url)} target="_blank" rel="noreferrer noopener" style={{ color: ACC }}>
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
