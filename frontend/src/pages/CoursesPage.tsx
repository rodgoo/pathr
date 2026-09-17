/**
 * Cursos com certificado, para o perfil do LinkedIn.
 *
 * ## O que a tela promete
 *
 * Três coisas, e cada uma está desenhada para não poder ser lida errado:
 *
 * - **Todo curso emite certificado**, e o selo diz se ele é gratuito ou pago
 *   — o certificado, não as aulas. "Aulas grátis" com certificado pago é o
 *   caso mais comum de gente que termina um curso e descobre a conta no fim.
 * - **Gratuito primeiro, sempre.** A lista vem dividida em dois blocos, e o
 *   gratuito vem em cima. A regra de ordem mora no servidor; a divisão aqui
 *   é o que a torna visível.
 * - **Só o que a pessoa pediu.** Cada cartão diz qual configuração o trouxe.
 * - **O que a pessoa já tem sai da lista.** Marcou "já possuo", o cartão some
 *   (com "Desfazer" para o clique errado) e passa a morar em Perfil e tags.
 *   Um botão nos filtros mostra os escondidos, para desmarcar.
 *
 * ## A barra de chama
 *
 * Mede quanto aquele conteúdo pesa numa vaga hoje, não a qualidade do curso.
 * Cinco segmentos, e o rótulo em texto ao lado: cor sozinha não carrega o
 * significado para quem não distingue laranja de cinza.
 *
 * ## Adicionar ao LinkedIn
 *
 * O botão abre o formulário oficial de certificação do LinkedIn já com o
 * nome e o emissor. Não há integração por trás e não precisa: é o fluxo que o
 * próprio LinkedIn oferece a quem emite certificado.
 */

import { useEffect, useState } from "react";
import { api } from "@/api/client";
import { courses as coursesApi } from "@/api/endpoints";
import type { Course, CourseList, DemandBand } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useQuery } from "@/hooks/useApi";
import { useIdioma, useT, type Traduzir } from "@/lib/i18n";
import { C, HAIRLINE, SIZE, TEXT, tint } from "@/lib/tokens";
import { CATEGORIAS, rotuloCategoria } from "@/components/profile/SkillsTab";
import { Icon } from "@/components/ui/icons";
import { Segmented } from "@/components/ui/Segmented";
import { Select } from "@/components/ui/Select";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";

import { linkExterno } from "@/lib/linkExterno";
type Filtro = "todos" | "gratuitos" | "pagos";
type Escopo = "voce" | "catalogo";
type Ordem = "relevancia" | "mais_procurados" | "menos_procurados";

/** O curso com as categorias das suas tecnologias (backend, cloud…), para o filtro. */
type Curso = Course & { categorias?: string[] };

const filtros = (t: Traduzir): readonly { value: Filtro; label: string }[] => [
  { value: "todos", label: t("cursos.filtro.todos") },
  { value: "gratuitos", label: t("cursos.filtro.gratuitos") },
  { value: "pagos", label: t("cursos.filtro.pagos") },
];

const escopos = (t: Traduzir): readonly { value: Escopo; label: string }[] => [
  { value: "voce", label: t("cursos.escopo.voce") },
  { value: "catalogo", label: t("cursos.escopo.catalogo") },
];

const ordens = (t: Traduzir): readonly { value: Ordem; label: string }[] => [
  { value: "relevancia", label: t("cursos.ordem.relevancia") },
  { value: "mais_procurados", label: t("cursos.ordem.maisProcurados") },
  { value: "menos_procurados", label: t("cursos.ordem.menosProcurados") },
];

const TODAS = "todas";

const NOME_DA_CATEGORIA = new Map(CATEGORIAS.map((categoria) => [categoria.slug, categoria.label]));

function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

const nivelLabel = (t: Traduzir): Record<Course["nivel"], string> => ({
  iniciante: t("cursos.nivel.iniciante"),
  intermediario: t("cursos.nivel.intermediario"),
  avancado: t("cursos.nivel.avancado"),
});

const motivoLabel = (t: Traduzir): Record<Course["motivos"][number]["tipo"], string> => ({
  meta: t("cursos.motivo.meta"),
  quero_aprender: t("cursos.motivo.queroAprender"),
  roadmap: t("cursos.motivo.roadmap"),
  objetivo: t("cursos.motivo.objetivo"),
});

/** Segmentos acesos e a cor da chama em cada faixa. Do cinza ao vermelho. */
const CHAMA: Record<DemandBand, { acesos: number; cor: string }> = {
  basico: { acesos: 1, cor: "#7b7f8c" },
  comum: { acesos: 2, cor: C.ambar },
  procurado: { acesos: 3, cor: "#d99452" },
  em_alta: { acesos: 4, cor: "#e2794a" },
  pegando_fogo: { acesos: 5, cor: "#e85c45" },
};

/** Cada segmento tem a cor da faixa que ele representa: a barra esquenta da
 * esquerda para a direita, e um curso "em alta" mostra o caminho até lá. */
const FAIXA_DO_SEGMENTO: DemandBand[] = ["basico", "comum", "procurado", "em_alta", "pegando_fogo"];

function mesPorExtenso(anoMes: string, idioma: string): string {
  const [ano, mes] = anoMes.split("-").map(Number);
  if (!ano || !mes || mes < 1 || mes > 12) return anoMes;
  return new Intl.DateTimeFormat(idioma, { month: "long", year: "numeric" }).format(
    new Date(ano, mes - 1, 1),
  );
}

/** O formulário "Adicionar certificação" do LinkedIn, já preenchido. */
export function linkParaLinkedIn(
  curso: Pick<Course, "titulo" | "emissor" | "url">,
  hoje = new Date(),
): string {
  const query = new URLSearchParams({
    startTask: "CERTIFICATION_NAME",
    name: curso.titulo,
    organizationName: curso.emissor,
    issueYear: String(hoje.getFullYear()),
    issueMonth: String(hoje.getMonth() + 1),
    certUrl: curso.url,
  });
  return `https://www.linkedin.com/profile/add?${query}`;
}

export function CoursesPage() {
  const t = useT();
  const { idioma } = useIdioma();
  const nf = new Intl.NumberFormat(idioma);
  const { dispatch } = useAppState();
  const [escopo, setEscopo] = useState<Escopo>("voce");
  const lista = useQuery(
    () => (escopo === "catalogo" ? api.get<CourseList>("/courses?todos=true") : coursesApi.list()),
    [escopo],
  );
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [busca, setBusca] = useState("");
  const [categoria, setCategoria] = useState<string>(TODAS);
  const [stack, setStack] = useState<string>(TODAS);
  const [ordem, setOrdem] = useState<Ordem>("relevancia");
  // O que já possui, mantido aqui: marcar num cartão tira o cartão da lista na
  // hora, sem esperar a lista voltar do servidor.
  const [possuidos, setPossuidos] = useState<Set<string>>(new Set());
  const [mostrarPossuidos, setMostrarPossuidos] = useState(false);
  const [recemMarcado, setRecemMarcado] = useState<Course | null>(null);

  useEffect(() => {
    if (lista.data) setPossuidos(new Set(lista.data.cursos.filter((c) => c.possuo).map((c) => c.id)));
  }, [lista.data]);

  // O aviso "Desfazer" some sozinho depois de alguns segundos.
  useEffect(() => {
    if (!recemMarcado) return;
    const timer = window.setTimeout(() => setRecemMarcado(null), 6000);
    return () => window.clearTimeout(timer);
  }, [recemMarcado]);

  if (lista.loading) return <Loading label={t("cursos.carregando")} />;
  if (lista.error) return <ErrorState message={lista.error} onRetry={lista.reload} />;
  if (!lista.data) return null;

  const { conferido_em, tem_pedido } = lista.data;
  const cursos = lista.data.cursos as Curso[];

  // O nome da categoria no idioma de quem lê; categoria fora do catálogo
  // conhecido cai no próprio slug.
  const nomeCategoria = (slug: string) => rotuloCategoria(t, slug, NOME_DA_CATEGORIA.get(slug) ?? slug);

  // As opções dos filtros saem da lista que chegou: filtrar por uma categoria
  // que não tem curso nenhum só levaria a uma tela vazia.
  const categorias = [...new Set(cursos.flatMap((curso) => curso.categorias ?? []))].sort((a, b) =>
    nomeCategoria(a).localeCompare(nomeCategoria(b), idioma),
  );
  const tecnologias = [...new Set(cursos.flatMap((curso) => curso.tags))].sort((a, b) => a.localeCompare(b, idioma));

  function marcarPossuo(curso: Course, possuo: boolean) {
    setPossuidos((atual) => {
      const novo = new Set(atual);
      if (possuo) novo.add(curso.id);
      else novo.delete(curso.id);
      return novo;
    });
    setRecemMarcado(possuo ? curso : null);
  }

  async function desfazer(curso: Course) {
    marcarPossuo(curso, false);
    try {
      await coursesApi.disown(curso.id);
    } catch {
      marcarPossuo(curso, true);
    }
  }

  const escondidos = cursos.filter((curso) => possuidos.has(curso.id)).length;
  const termo = semAcento(busca.trim());
  const filtrados = cursos
    .filter(
      (curso) =>
        (mostrarPossuidos || !possuidos.has(curso.id)) &&
        (!termo || semAcento([curso.titulo, curso.emissor, ...curso.tags].join(" ")).includes(termo)) &&
        (categoria === TODAS || (curso.categorias ?? []).includes(categoria)) &&
        (stack === TODAS || curso.tags.includes(stack)),
    )
    // Gratuito primeiro continua valendo: a divisão em blocos abaixo garante.
    // Aqui só muda a ordem dentro de cada bloco.
    .sort((a, b) =>
      ordem === "mais_procurados"
        ? b.demanda.nota - a.demanda.nota
        : ordem === "menos_procurados"
          ? a.demanda.nota - b.demanda.nota
          : 0,
    );
  const gratuitos = filtrados.filter((curso) => curso.certificado.gratuito);
  const pagos = filtrados.filter((curso) => !curso.certificado.gratuito);
  const filtrando = Boolean(termo) || categoria !== TODAS || stack !== TODAS;

  function limpar() {
    setBusca("");
    setCategoria(TODAS);
    setStack(TODAS);
  }

  return (
    <div style={SCREEN_IN}>
      <header
        style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: 16.8, marginBottom: 16.8 }}
      >
        <div style={{ flex: 1, minWidth: 250 }}>
          <div style={{ fontSize: SIZE.apoio, color: TEXT.muted }}>
            {t("cursos.contador", {
              n: nf.format(filtrados.length),
              cursos: filtrados.length === 1 ? t("cursos.curso") : t("cursos.cursos"),
              gratuitos: nf.format(gratuitos.length),
            })}
          </div>
          <h1 style={{ fontSize: 28, margin: 0 }}>{t("cursos.titulo")}</h1>
          <p style={{ margin: "5.6px 0 0", fontSize: SIZE.corpo, color: TEXT.strong, maxWidth: "70ch" }}>
            {t("cursos.subtitulo")}
          </p>
        </div>
        <Segmented name="cursos-escopo" label={t("cursos.quaisCursos")} value={escopo} options={escopos(t)} onChange={setEscopo} />
      </header>

      {cursos.length > 0 ? (
        <Panel pad={14} style={{ marginBottom: 16.8 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 200px), 1fr))",
              gap: 8.4,
              alignItems: "end",
            }}
          >
            <div className="field" style={{ margin: 0 }}>
              <label htmlFor="cursos-busca">{t("cursos.buscar")}</label>
              <input
                id="cursos-busca"
                className="input"
                type="search"
                placeholder={t("cursos.buscarPlaceholder")}
                value={busca}
                onChange={(evento) => setBusca(evento.target.value)}
              />
            </div>
            <div className="field" style={{ margin: 0 }}>
              <label htmlFor="cursos-categoria">{t("cursos.categoria")}</label>
              <Select
                id="cursos-categoria"
                value={categoria}
                onChange={setCategoria}
                options={[
                  { value: TODAS, label: t("cursos.todasCategorias") },
                  ...categorias.map((slug) => ({ value: slug, label: nomeCategoria(slug) })),
                ]}
              />
            </div>
            <div className="field" style={{ margin: 0 }}>
              <label htmlFor="cursos-stack">{t("cursos.stack")}</label>
              <Select
                id="cursos-stack"
                value={stack}
                onChange={setStack}
                options={[
                  { value: TODAS, label: t("cursos.todasTecnologias") },
                  ...tecnologias.map((nome) => ({ value: nome, label: nome })),
                ]}
              />
            </div>
            <div className="field" style={{ margin: 0 }}>
              <label htmlFor="cursos-ordem">{t("cursos.ordenar")}</label>
              <Select id="cursos-ordem" value={ordem} onChange={setOrdem} options={ordens(t)} />
            </div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8.4, marginTop: 10 }}>
            <Segmented
              name="cursos-filtro"
              label={t("cursos.tipoCertificado")}
              value={filtro}
              options={filtros(t)}
              onChange={setFiltro}
            />
            {filtrando ? (
              <button type="button" className="btn btn-ghost" style={{ fontSize: 12 }} onClick={limpar}>
                <Icon name="x" size={14} />
                {t("cursos.limparFiltros")}
              </button>
            ) : null}
            {escondidos > 0 ? (
              <button
                type="button"
                className="btn btn-ghost"
                style={{ fontSize: 12, marginLeft: "auto" }}
                aria-pressed={mostrarPossuidos}
                onClick={() => setMostrarPossuidos((valor) => !valor)}
              >
                <Icon name="check" size={14} />
                {mostrarPossuidos
                  ? t("cursos.esconderPossuidos")
                  : t("cursos.mostrarPossuidos", { n: nf.format(escondidos) })}
              </button>
            ) : null}
          </div>
        </Panel>
      ) : null}

      {recemMarcado && !mostrarPossuidos ? (
        <div
          role="status"
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 8.4,
            padding: "8.4px 12px",
            marginBottom: 16.8,
            borderRadius: 9,
            background: tint(C.verde, 10),
            boxShadow: `inset 0 0 0 1px ${tint(C.verde, 35)}`,
            fontSize: 12.5,
            color: TEXT.strong,
          }}
        >
          <Icon name="check" size={15} style={{ color: C.verde }} />
          <span style={{ flex: 1, minWidth: 0 }}>
            <strong>{recemMarcado.titulo}</strong> {t("cursos.saiuDaLista")}
          </span>
          <button type="button" className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => void desfazer(recemMarcado)}>
            {t("cursos.desfazer")}
          </button>
        </div>
      ) : null}

      {cursos.length > 0 && filtrados.length === 0 && escondidos === cursos.length ? (
        <EmptyState
          title={t("cursos.vazioPossuiTodos.titulo")}
          description={
            escopo === "voce"
              ? t("cursos.vazioPossuiTodos.descVoce")
              : t("cursos.vazioPossuiTodos.descCatalogo")
          }
          action={
            escopo === "voce" ? (
              <button type="button" className="btn btn-secondary" onClick={() => setEscopo("catalogo")}>
                <Icon name="search" size={15} />
                {t("cursos.buscarCatalogo")}
              </button>
            ) : undefined
          }
        />
      ) : cursos.length > 0 && filtrados.length === 0 ? (
        <EmptyState
          title={t("cursos.vazioFiltros.titulo")}
          description={
            escopo === "voce"
              ? t("cursos.vazioFiltros.descVoce")
              : t("cursos.vazioFiltros.descCatalogo")
          }
          action={
            escopo === "voce" ? (
              <button type="button" className="btn btn-secondary" onClick={() => setEscopo("catalogo")}>
                <Icon name="search" size={15} />
                {t("cursos.buscarCatalogo")}
              </button>
            ) : (
              <button type="button" className="btn btn-secondary" onClick={limpar}>
                <Icon name="x" size={15} />
                {t("cursos.limparFiltros")}
              </button>
            )
          }
        />
      ) : null}

      {cursos.length === 0 ? (
        tem_pedido ? (
          <EmptyState
            title={t("cursos.vazioSemCurso.titulo")}
            description={t("cursos.vazioSemCurso.desc")}
            action={
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => dispatch({ type: "navigate", screen: "config", settingsTab: "skills" })}
              >
                <Icon name="code" size={15} />
                {t("cursos.escolherTecnologias")}
              </button>
            }
          />
        ) : (
          <EmptyState
            title={t("cursos.vazioSemPedido.titulo")}
            description={t("cursos.vazioSemPedido.desc")}
            action={
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => dispatch({ type: "navigate", screen: "config", settingsTab: "objetivo" })}
              >
                <Icon name="flag" size={15} />
                {t("cursos.definirObjetivo")}
              </button>
            }
          />
        )
      ) : filtrados.length === 0 ? null : (
        <>
          {filtro !== "pagos" ? (
            <Bloco
              titulo={t("cursos.blocoGratuito")}
              cursos={gratuitos}
              possuidos={possuidos}
              onPossuo={marcarPossuo}
              vazio={t("cursos.vazioGratuito")}
            />
          ) : null}
          {filtro !== "gratuitos" ? (
            <Bloco
              titulo={t("cursos.blocoPago")}
              cursos={pagos}
              possuidos={possuidos}
              onPossuo={marcarPossuo}
              vazio={t("cursos.vazioPago")}
            />
          ) : null}
          <p style={{ margin: "22.4px 0 0", fontSize: 11.5, color: TEXT.faint, maxWidth: "76ch" }}>
            {t("cursos.rodapePrecos", { mes: mesPorExtenso(conferido_em, idioma) })}
          </p>
        </>
      )}
    </div>
  );
}

function Bloco({
  titulo,
  cursos,
  possuidos,
  onPossuo,
  vazio,
}: {
  titulo: string;
  cursos: Course[];
  possuidos: Set<string>;
  onPossuo: (curso: Course, possuo: boolean) => void;
  vazio: string;
}) {
  const { idioma } = useIdioma();
  return (
    <section aria-label={titulo} style={{ marginBottom: 28 }}>
      <Kicker style={{ display: "block", marginBottom: 11.2 }}>
        {titulo} · {new Intl.NumberFormat(idioma).format(cursos.length)}
      </Kicker>
      {cursos.length === 0 ? (
        <p style={{ margin: 0, fontSize: SIZE.apoio, color: TEXT.faint }}>{vazio}</p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill,minmax(min(100%,330px),1fr))",
            gap: 11.2,
          }}
        >
          {cursos.map((curso) => (
            <CartaoDoCurso key={curso.id} curso={curso} possuo={possuidos.has(curso.id)} onPossuo={onPossuo} />
          ))}
        </div>
      )}
    </section>
  );
}

function CartaoDoCurso({
  curso,
  possuo,
  onPossuo,
}: {
  curso: Course;
  possuo: boolean;
  onPossuo: (curso: Course, possuo: boolean) => void;
}) {
  const t = useT();
  const NIVEL = nivelLabel(t);
  const MOTIVO = motivoLabel(t);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const { gratuito, detalhe } = curso.certificado;

  // Otimista: o cartão sai da lista na hora e volta se o servidor recusar.
  async function alternarPossuo() {
    const antes = possuo;
    onPossuo(curso, !antes);
    setSalvando(true);
    setErro(null);
    try {
      if (antes) await coursesApi.disown(curso.id);
      else await coursesApi.own(curso.id);
    } catch (caught) {
      onPossuo(curso, antes);
      setErro(caught instanceof Error ? caught.message : t("cursos.erroSalvar"));
    } finally {
      setSalvando(false);
    }
  }
  const corDoSelo = gratuito ? C.verde : C.ambar;
  const meta = [curso.emissor, NIVEL[curso.nivel], curso.idioma === "pt" ? t("cursos.portugues") : t("cursos.ingles")];
  if (curso.horas) meta.push(t("cursos.horas", { h: curso.horas }));

  return (
    <Panel pad={16.8} style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <article aria-label={curso.titulo} style={{ display: "contents" }}>
        <div>
          <h2 style={{ fontSize: 15.5, fontWeight: 500, margin: 0, lineHeight: 1.35 }}>{curso.titulo}</h2>
          <div style={{ fontSize: 12, color: TEXT.muted, marginTop: 3 }}>{meta.join(" · ")}</div>
        </div>

        <div
          style={{
            display: "flex",
            gap: 8.4,
            alignItems: "flex-start",
            padding: "8.4px 10px",
            borderRadius: 8,
            background: tint(corDoSelo, 10),
            boxShadow: `inset 0 0 0 1px ${tint(corDoSelo, 35)}`,
          }}
        >
          <Icon name="award" size={16} style={{ color: corDoSelo, flex: "none", marginTop: 1 }} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 12.5, fontWeight: 500, color: corDoSelo }}>
              {gratuito ? t("cursos.blocoGratuito") : t("cursos.blocoPago")}
            </div>
            <div style={{ fontSize: 12, color: TEXT.strong, lineHeight: 1.45 }}>{detalhe}</div>
          </div>
        </div>

        <BarraDeChama demanda={curso.demanda} />

        <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6 }}>
          {curso.motivos.map((motivo) => (
            <span
              key={`${motivo.tipo}-${motivo.tag}`}
              style={{
                fontSize: 11,
                padding: "2px 7px",
                borderRadius: 5,
                background: "rgba(233,233,237,.07)",
                color: TEXT.strong,
              }}
            >
              {MOTIVO[motivo.tipo]}: {motivo.tag}
            </span>
          ))}
        </div>

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 8.4,
            marginTop: "auto",
            paddingTop: 11.2,
            borderTop: `1px solid ${HAIRLINE}`,
          }}
        >
          <a
            className="btn btn-primary"
            href={linkExterno(curso.url)}
            target="_blank"
            rel="noreferrer noopener"
            style={{ textDecoration: "none" }}
          >
            {t("cursos.irParaCurso")}
            <Icon name="externalLink" size={14} />
          </a>
          <button
            type="button"
            className={possuo ? "btn btn-primary" : "btn btn-secondary"}
            aria-pressed={possuo}
            disabled={salvando}
            onClick={() => void alternarPossuo()}
            title={possuo ? t("cursos.possuoTitleSim") : t("cursos.possuoTitleNao")}
            style={possuo ? { background: tint(C.verde, 14), borderColor: C.verde, color: C.verde } : undefined}
          >
            {possuo ? <Icon name="check" size={14} /> : null}
            {possuo ? t("cursos.jaPossuo") : t("cursos.jaPossuoPergunta")}
          </button>
          <a
            className="btn btn-ghost"
            href={linkParaLinkedIn(curso)}
            target="_blank"
            rel="noreferrer noopener"
            title={t("cursos.linkedinTitle")}
            style={{ textDecoration: "none", fontSize: SIZE.apoio }}
          >
            <Icon name="externalLink" size={15} />
            {t("cursos.adicionarLinkedin")}
          </a>
        </div>
        {erro ? <div style={{ fontSize: 12, color: C.ambar }}>{erro}</div> : null}
      </article>
    </Panel>
  );
}

function BarraDeChama({ demanda }: { demanda: Course["demanda"] }) {
  const t = useT();
  const { acesos, cor } = CHAMA[demanda.faixa];
  const quente = acesos >= 4;
  return (
    <div>
      <div
        role="meter"
        aria-label={t("cursos.procuraNoMercado")}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={demanda.nota}
        aria-valuetext={demanda.rotulo}
        style={{ display: "flex", alignItems: "center", gap: 8.4 }}
      >
        <Icon
          name="fogo"
          size={17}
          style={{ color: cor, flex: "none" }}
          fill={quente ? cor : "none"}
          fillOpacity={quente ? 0.35 : undefined}
        />
        <div aria-hidden style={{ display: "flex", gap: 3, flex: 1, maxWidth: 150 }}>
          {FAIXA_DO_SEGMENTO.map((faixa, posicao) => (
            <span
              key={faixa}
              style={{
                flex: 1,
                height: 6,
                borderRadius: 3,
                background: posicao < acesos ? CHAMA[faixa].cor : "rgba(233,233,237,.1)",
              }}
            />
          ))}
        </div>
        <span style={{ fontSize: 12.5, color: cor, whiteSpace: "nowrap" }}>{demanda.rotulo}</span>
      </div>
      {demanda.motivo ? (
        <div style={{ fontSize: 11.5, color: TEXT.faint, marginTop: 4, lineHeight: 1.45 }}>{demanda.motivo}</div>
      ) : null}
    </div>
  );
}
