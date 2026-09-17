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
import { useIdioma, useT, type Traduzir } from "@/lib/i18n";
import { vagasGuardadas } from "@/lib/vagasGuardadas";
import { ACC, ACC4, C, HAIRLINE, SIZE, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { ProgressoDaTarefa } from "@/components/ui/ProgressoDaTarefa";

import { linkExterno } from "@/lib/linkExterno";
type Filtro = "todas" | "remotas";
type Alcance = "todas" | "nacionais" | "internacionais";

const filtros = (t: Traduzir): readonly { value: Filtro; label: string }[] => [
  { value: "todas", label: t("vagas.filtro.todas") },
  { value: "remotas", label: t("vagas.filtro.remotas") },
];

const alcances = (t: Traduzir): readonly { value: Alcance; label: string }[] => [
  { value: "todas", label: t("vagas.alcance.todas") },
  { value: "nacionais", label: t("vagas.alcance.nacionais") },
  { value: "internacionais", label: t("vagas.alcance.internacionais") },
];

const nomeDaFonte = (t: Traduzir): Record<keyof JobList["fontes"], string> => ({
  gupy: "Gupy",
  remotive: "Remotive",
  adzuna: "Adzuna",
  busca: t("vagas.fonte.busca"),
});

const estadoDaFonte = (t: Traduzir): Record<"ok" | "erro" | "sem_chave", string> => ({
  ok: t("vagas.estadoFonte.ok"),
  erro: t("vagas.estadoFonte.erro"),
  sem_chave: t("vagas.estadoFonte.semChave"),
});

const nivelLabel = (t: Traduzir): Record<"junior" | "pleno" | "senior", string> => ({
  junior: t("vagas.nivel.junior"),
  pleno: t("vagas.nivel.pleno"),
  senior: t("vagas.nivel.senior"),
});

const situacaoLabel = (t: Traduzir): Record<JobRequirement["situacao"], { rotulo: string; cor: string }> => ({
  sem_nivel: { rotulo: t("vagas.situacao.semNivel"), cor: C.azul },
  tem: { rotulo: t("vagas.situacao.tem"), cor: C.verde },
  parcial: { rotulo: t("vagas.situacao.parcial"), cor: C.ambar },
  falta: { rotulo: t("vagas.situacao.falta"), cor: C.rosa },
  desconhecido: { rotulo: t("vagas.situacao.desconhecido"), cor: TEXT.faint },
});

/** Quantas lacunas o cartão mostra antes do "ver todas". */
const LACUNAS_VISIVEIS = 4;

function corDaNota(nota: number): string {
  return nota >= 70 ? C.verde : nota >= 40 ? C.ambar : C.rosa;
}

function haQuanto(dias: number | null, t: Traduzir): string | null {
  if (dias === null) return null;
  if (dias === 0) return t("vagas.tempo.hoje");
  return dias === 1 ? t("vagas.tempo.umDia") : t("vagas.tempo.dias", { n: dias });
}

function minutosDesde(iso: string | undefined, t: Traduzir): string | null {
  if (!iso) return null;
  const minutos = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutos < 1) return t("vagas.tempo.agora");
  if (minutos < 60) return t("vagas.tempo.min", { n: minutos });
  const horas = Math.round(minutos / 60);
  return horas === 1 ? t("vagas.tempo.umaHora") : t("vagas.tempo.horas", { n: horas });
}

function juntar(nomes: string[], e: string): string {
  if (nomes.length <= 1) return nomes.join("");
  return `${nomes.slice(0, -1).join(", ")} ${e} ${nomes[nomes.length - 1]}`;
}

export function JobsPage() {
  const t = useT();
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
        <h1 style={{ fontSize: 28, margin: 0 }}>{t("vagas.titulo")}</h1>
        <p style={{ margin: "5.6px 0 0", fontSize: SIZE.corpo, color: TEXT.strong, maxWidth: "72ch" }}>
          {t("vagas.subtitulo")}
        </p>
      </header>

      <form
        onSubmit={buscar}
        style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "center", margin: "0 0 8.4px" }}
      >
        <input
          className="input"
          aria-label={t("vagas.buscarAria")}
          placeholder={t("vagas.buscarPlaceholder")}
          value={busca}
          onChange={(evento) => setBusca(evento.target.value)}
          style={{ flex: "1 1 260px" }}
        />
        <button type="submit" className="btn btn-secondary">
          <Icon name="search" size={15} />
          {t("vagas.buscar")}
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
            {t("vagas.voltarPerfil")}
          </button>
        ) : null}
      </form>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, marginBottom: 11.2, alignItems: "center" }}>
        <Segmented name="vagas-alcance" label={t("vagas.onde")} value={alcance} options={alcances(t)} onChange={setAlcance} />
        <Segmented name="vagas-filtro" label={t("vagas.tipoVaga")} value={filtro} options={filtros(t)} onChange={setFiltro} />
        {lista.data && !lista.data.sem_perfil ? (
          <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 8.4 }}>
            <span style={{ fontSize: 11.5, color: TEXT.faint }}>
              {atualizando
                ? t("vagas.procurandoNovas")
                : t("vagas.atualizadoEm", { tempo: minutosDesde(lista.data.buscado_em, t) ?? "" })}
            </span>
            <button type="button" className="btn btn-secondary" onClick={() => void atualizar()} disabled={atualizando}>
              <Icon name="refresh" size={15} />
              {atualizando ? t("vagas.atualizando") : t("vagas.atualizar")}
            </button>
          </span>
        ) : null}
      </div>
      {erroAoAtualizar ? (
        <p role="alert" style={{ margin: "0 0 11.2px", fontSize: 12.5, color: C.ambar }}>
          {t("vagas.erroAtualizar", { erro: erroAoAtualizar })}
        </p>
      ) : null}

      {lista.loading ? <Loading label={t("vagas.carregando")} /> : null}
      {lista.error ? <ErrorState message={lista.error} onRetry={lista.reload} /> : null}
      {lista.data && !lista.loading ? <Resultado dados={lista.data} filtro={filtro} alcance={alcance} /> : null}

      <div style={{ marginTop: 22.4 }}>
        <AnalisarVaga />
      </div>
    </div>
  );
}

function Resultado({ dados, filtro, alcance }: { dados: JobList; filtro: Filtro; alcance: Alcance }) {
  const t = useT();
  const { idioma } = useIdioma();
  const nf = new Intl.NumberFormat(idioma);
  const { dispatch } = useAppState();
  const NOME_DA_FONTE = nomeDaFonte(t);
  const ESTADO_DA_FONTE = estadoDaFonte(t);

  if (dados.sem_perfil) {
    return (
      <EmptyState
        title={t("vagas.semPerfil.titulo")}
        description={t("vagas.semPerfil.desc")}
        action={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => dispatch({ type: "navigate", screen: "config", settingsTab: "skills" })}
          >
            <Icon name="plus" size={15} />
            {t("vagas.cadastrarTecnologias")}
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
        {t("vagas.buscandoPor")} <span style={{ color: TEXT.full }}>{dados.termos.join(" · ")}</span> ·{" "}
        {nf.format(visiveis.length)} {visiveis.length === 1 ? t("vagas.vaga") : t("vagas.vagas")} · {t("vagas.seuIngles")}{" "}
        {dados.nivel_ingles ? (
          <span style={{ color: TEXT.full }}>{dados.nivel_ingles}</span>
        ) : (
          <button
            type="button"
            className="btn btn-ghost"
            style={{ fontSize: 12, padding: 0, minHeight: 0 }}
            onClick={() => dispatch({ type: "navigate", screen: "ingles" })}
          >
            {t("vagas.semNivelamentoFazer")}
          </button>
        )}
        <Regiao regiao={dados.regiao} />
        <div style={{ color: TEXT.faint }}>
          {t("vagas.fontes")}{" "}
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
          title={t("vagas.vazio.titulo")}
          description={t("vagas.vazio.desc")}
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
  const t = useT();
  const { idioma } = useIdioma();
  const { dispatch } = useAppState();
  let texto: string;
  if (!regiao) {
    texto = t("vagas.regiao.semCidade");
  } else if (regiao.raio_km === 0) {
    texto = t("vagas.regiao.soRemotas");
  } else if (regiao.cidade) {
    texto = t("vagas.regiao.cidade", {
      km: new Intl.NumberFormat(idioma).format(regiao.raio_km),
      cidade: regiao.cidade,
      uf: regiao.uf ?? "",
    });
  } else {
    texto = t("vagas.regiao.uf", { uf: regiao.uf ?? "" });
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
        {regiao ? t("vagas.mudarRegiao") : t("vagas.definirRegiao")}
      </button>
    </div>
  );
}

function CartaoDaVaga({ vaga, cursos }: { vaga: Job; cursos: Record<string, JobCourse[]> }) {
  const t = useT();
  const { idioma } = useIdioma();
  const NIVEL = nivelLabel(t);
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
    ? t("vagas.ondeDistancia", {
        local: vaga.local ?? t("vagas.presencial"),
        km: new Intl.NumberFormat(idioma).format(vaga.distancia_km),
      })
    : vaga.local;
  const detalhes = [vaga.empresa, onde, vaga.nivel ? NIVEL[vaga.nivel] : null, haQuanto(vaga.publicada_ha_dias, t)]
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
              {vaga.internacional ? <span style={{ color: C.azul }}>{t("vagas.internacional")} · </span> : null}
              {detalhes ? `${detalhes} · ` : ""}{t("vagas.via", { fonte: vaga.fonte })}
              {vaga.na_sua_regiao ? <span style={{ color: C.verde }}> · {t("vagas.naSuaRegiao")}</span> : null}
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
            <span style={{ color: TEXT.faint }}>{t("vagas.paraQuem")} </span>
            {vaga.nivel ? t("vagas.paraQuemNivel", { nivel: NIVEL[vaga.nivel] }) : ""}
            {t("vagas.paraQuemCom", { lista: juntar(pedidas.slice(0, 6), t("vagas.conectorE")) })}
            {pedidas.length > 6 ? t("vagas.paraQuemMais", { n: pedidas.length - 6 }) : ""}.
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
            {descricao ? t("vagas.esconderDescricao") : t("vagas.verDescricao")}
          </button>
        ) : null}
        {descricao && sobre ? <Descricao sobre={sobre} /> : null}

        {lido ? (
          <OQueFalta lacunas={vaga.lacunas ?? []} cursos={cursos} />
        ) : (
          <p style={{ margin: "11.2px 0 0", fontSize: 12, color: TEXT.faint }}>
            {vaga.so_trecho ? t("vagas.soTrecho") : t("vagas.soBuscador")}
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
            {t("vagas.verVaga")}
            <Icon name="externalLink" size={14} />
          </a>
          {!lido ? (
            <button type="button" className="btn btn-secondary" aria-expanded={aberta} onClick={() => void lerAnuncio()}>
              <Icon name="search" size={15} />
              {aberta ? t("vagas.esconderAnalise") : t("vagas.lerAnuncio")}
            </button>
          ) : null}
        </div>

        {aberta ? (
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: `1px solid ${HAIRLINE}` }}>
            {analise.pending ? <Loading label={t("vagas.lendoRequisitos")} /> : null}
            {analise.error ? <ErrorState message={analise.error} /> : null}
            {resultado ? <Analise analise={resultado} /> : null}
          </div>
        ) : null}
      </article>
    </Panel>
  );
}

function Descricao({ sobre }: { sobre: NonNullable<Job["sobre"]> }) {
  const t = useT();
  const partes: [string, string[]][] = [
    [t("vagas.descricao.faz"), sobre.faz],
    [t("vagas.descricao.pede"), sobre.pede],
    [t("vagas.descricao.diferenciais"), sobre.diferenciais],
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
  const t = useT();
  const { idioma } = useIdioma();
  const nf = new Intl.NumberFormat(idioma);
  const [todas, setTodas] = useState(false);
  if (!lacunas.length) {
    return (
      <p style={{ margin: "11.2px 0 0", fontSize: 12.5, color: C.verde, display: "flex", alignItems: "center", gap: 5 }}>
        <Icon name="check" size={14} />
        {t("vagas.temTudo")}
      </p>
    );
  }
  const obrigatorias = lacunas.filter((l) => l.obrigatorio).length;
  const mostradas = todas ? lacunas : lacunas.slice(0, LACUNAS_VISIVEIS);
  return (
    <section aria-label={t("vagas.oQueFaltaAria")} style={{ marginTop: 11.2 }}>
      <div style={{ fontSize: 11.5, color: TEXT.faint, marginBottom: 5.6 }}>
        {t("vagas.oQueFalta")} · {nf.format(lacunas.length)}{" "}
        {lacunas.length === 1 ? t("vagas.item") : t("vagas.itens")}
        {obrigatorias
          ? `, ${nf.format(obrigatorias)} ${obrigatorias === 1 ? t("vagas.obrigatorioUm") : t("vagas.obrigatoriosVarios")}`
          : ""}
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
          {todas ? t("vagas.mostrarMenos") : t("vagas.verTodasLacunas", { n: nf.format(lacunas.length) })}
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
  const t = useT();
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
        {lacuna.situacao === "sem_nivel" ? t("vagas.fazerNivelamento") : t("vagas.treinarIngles")}
      </button>
    );
  }
  if (lacuna.no_roadmap) return <span style={{ color: ACC4, fontSize: 12 }}>{t("vagas.jaNoRoadmap")}</span>;
  if (meta) {
    return (
      <span style={{ color: C.verde, fontSize: 12, display: "inline-flex", alignItems: "center", gap: 4 }}>
        <Icon name="check" size={13} />
        {t("vagas.metaMarcada")}
      </span>
    );
  }
  if (!lacuna.tag_id) return null;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      {error ? <span style={{ fontSize: 11.5, color: C.ambar }}>{error}</span> : null}
      <button type="button" className="btn btn-ghost" disabled={pending} style={{ fontSize: 12 }} onClick={() => void executar()}>
        <Icon name="flag" size={14} />
        {pending ? t("vagas.marcando") : t("vagas.marcarMeta")}
      </button>
    </span>
  );
}

function LacunaCompacta({ lacuna, cursos }: { lacuna: JobListGap; cursos: JobCourse[] }) {
  const t = useT();
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
            {lacuna.obrigatorio ? t("vagas.obrigatorio") : t("vagas.diferencial")}
            {lacuna.situacao === "parcial" ? (lacuna.idioma ? t("vagas.degrauAbaixo") : t("vagas.comecando")) : ""}
            {lacuna.situacao === "sem_nivel" ? t("vagas.semNivelamentoSufixo") : ""}
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
          title={`${curso.emissor} · ${curso.gratuito ? t("vagas.certificadoGratuito") : t("vagas.certificadoPago")}`}
        >
          <Icon
            name="award"
            size={13}
            style={{ color: curso.gratuito ? C.verde : C.ambar, verticalAlign: "-2px", marginRight: 4 }}
          />
          {curso.titulo}
          <span style={{ color: TEXT.faint, whiteSpace: "nowrap" }}> · {curso.gratuito ? t("vagas.gratuito") : t("vagas.pago")}</span>
        </a>
      ) : null}
    </div>
  );
}

const inglesLabel = (
  t: Traduzir,
): Record<NonNullable<JobEnglish["situacao"]>, { cor: string; texto: (i: JobEnglish) => string }> => ({
  tem: { cor: C.verde, texto: (i) => t("vagas.ingles.tem", { exigido: i.exigido ?? "", seu: i.seu ?? "" }) },
  parcial: { cor: C.ambar, texto: (i) => t("vagas.ingles.parcial", { exigido: i.exigido ?? "", seu: i.seu ?? "" }) },
  falta: { cor: C.rosa, texto: (i) => t("vagas.ingles.falta", { exigido: i.exigido ?? "", seu: i.seu ?? "" }) },
  sem_nivel: { cor: C.azul, texto: (i) => t("vagas.ingles.semNivel", { exigido: i.exigido ?? "" }) },
});

/** Por que esta vaga está na lista: a stack que ela pede e o objetivo. */
function Afinidade({ afinidade }: { afinidade?: Job["afinidade"] }) {
  const t = useT();
  const { idioma } = useIdioma();
  if (!afinidade) return null;
  const quantas = afinidade.stack_em_comum.length;
  if (!quantas && !afinidade.objetivo) return null;
  return (
    <div style={{ marginTop: 8.4, fontSize: 12, color: TEXT.strong, display: "flex", flexWrap: "wrap", gap: "4px 12px" }}>
      {quantas ? (
        <span title={afinidade.stack_em_comum.join(", ")} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <Icon name="code" size={13} style={{ color: C.verde }} />
          {t("vagas.tecnologiasDaStack", {
            n: new Intl.NumberFormat(idioma).format(quantas),
            tecnologias: quantas === 1 ? t("vagas.tecnologia") : t("vagas.tecnologias"),
          })}
        </span>
      ) : null}
      {afinidade.objetivo ? (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <Icon name="flag" size={13} style={{ color: ACC4 }} />
          {t("vagas.combinaObjetivo")}
        </span>
      ) : null}
    </div>
  );
}

function SeloDeIngles({ ingles }: { ingles: JobEnglish }) {
  const t = useT();
  if (!ingles.situacao) return null;
  const { cor, texto } = inglesLabel(t)[ingles.situacao];
  return (
    <div style={{ marginTop: 8.4, fontSize: 12, color: cor, display: "flex", alignItems: "center", gap: 5 }}>
      <Icon name="globe" size={13} />
      {texto(ingles)}
    </div>
  );
}

function Nota({ nota, estimada }: { nota: number | null | undefined; estimada?: boolean }) {
  const t = useT();
  const { idioma } = useIdioma();
  if (nota === null || nota === undefined) {
    return <span style={{ fontSize: 11.5, color: TEXT.faint, whiteSpace: "nowrap" }}>{t("vagas.anuncioNaoLido")}</span>;
  }
  const cor = corDaNota(nota);
  return (
    <div
      role="meter"
      aria-label={t("vagas.compatibilidadeAria")}
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
        <span style={{ fontSize: 20, lineHeight: 1, color: cor }}>{t("vagas.porcentagem", { n: new Intl.NumberFormat(idioma).format(nota) })}</span>
        <span style={{ fontSize: 11, color: TEXT.faint }}>
          {estimada ? t("vagas.estimadoTitulo") : t("vagas.combinaComVoce")}
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
  const t = useT();
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
      <Kicker style={{ display: "block", marginBottom: 5.6 }}>{t("vagas.analisarTitulo")}</Kicker>
      <p style={{ margin: "0 0 11.2px", fontSize: 12.5, color: TEXT.muted }}>
        {t("vagas.analisarDesc")}
      </p>
      <form onSubmit={analisar} style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
        <textarea
          className="input"
          rows={3}
          aria-label={t("vagas.analisarAria")}
          placeholder={t("vagas.analisarPlaceholder")}
          value={entrada}
          onChange={(evento) => setEntrada(evento.target.value)}
          style={{ width: "100%", resize: "vertical" }}
        />
        <div>
          <button type="submit" className="btn btn-primary" disabled={analise.pending || entrada.trim().length < 8}>
            <Icon name="search" size={15} />
            {analise.pending ? t("vagas.analisando") : t("vagas.verOQueFalta")}
          </button>
        </div>
      </form>
      <ProgressoDaTarefa
        ativo={analise.pending}
        chave="vaga-analisar"
        etapas={[t("vagas.etapa.lendo"), t("vagas.etapa.separando"), t("vagas.etapa.comparando")]}
        duracaoMs={18_000}
        style={{ marginTop: 11.2 }}
      />
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
  const t = useT();
  const { dispatch } = useAppState();
  const obrigatorios = analise.requisitos.filter((r) => r.obrigatorio);
  const desejaveis = analise.requisitos.filter((r) => !r.obrigatorio);

  return (
    <section aria-label={t("vagas.analiseCompletaAria")}>
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
              {t("vagas.analiseSimplificada")}
            </p>
          ) : null}
        </div>
        <Nota nota={analise.nota} />
      </div>

      <Requisitos titulo={t("vagas.obrigatorios")} lista={obrigatorios} />
      <Requisitos titulo={t("vagas.desejaveis")} lista={desejaveis} />

      <Kicker style={{ display: "block", margin: "16.8px 0 8.4px" }}>
        {analise.lacunas.length ? t("vagas.oQueFaltaComoChegar") : t("vagas.nadaFalta")}
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
          {t("vagas.verTodosCursos")}
        </button>
      ) : null}
    </section>
  );
}

function Requisitos({ titulo, lista }: { titulo: string; lista: JobRequirement[] }) {
  const t = useT();
  const SITUACAO = situacaoLabel(t);
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
  const t = useT();
  return (
    <div style={{ padding: "11.2px 12.6px", borderRadius: 8, background: "rgba(233,233,237,.04)" }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8.4 }}>
        <span style={{ fontSize: 14, color: TEXT.full }}>{lacuna.nome}</span>
        <span style={{ fontSize: 11, color: lacuna.obrigatorio ? C.rosa : TEXT.faint }}>
          {lacuna.obrigatorio ? t("vagas.obrigatorio") : t("vagas.desejavel")}
          {lacuna.situacao === "parcial" ? (lacuna.idioma ? t("vagas.degrauAbaixo") : t("vagas.comecando")) : ""}
          {lacuna.situacao === "sem_nivel" ? t("vagas.semNivelamentoComparar") : ""}
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
                {curso.emissor} · {curso.gratuito ? t("vagas.certificadoGratuito") : t("vagas.certificadoPago")}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <div style={{ fontSize: 12, color: TEXT.faint, marginTop: 4 }}>
          {t("vagas.semCursoCatalogo")}
        </div>
      )}
    </div>
  );
}
