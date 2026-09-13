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

import { useState } from "react";
import { courses as coursesApi } from "@/api/endpoints";
import type { Course, DemandBand } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useQuery } from "@/hooks/useApi";
import { C, HAIRLINE, SIZE, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";

type Filtro = "todos" | "gratuitos" | "pagos";

const FILTROS: readonly { value: Filtro; label: string }[] = [
  { value: "todos", label: "Todos" },
  { value: "gratuitos", label: "Gratuitos" },
  { value: "pagos", label: "Pagos" },
];

const NIVEL: Record<Course["nivel"], string> = {
  iniciante: "Iniciante",
  intermediario: "Intermediário",
  avancado: "Avançado",
};

const MOTIVO: Record<Course["motivos"][number]["tipo"], string> = {
  meta: "Sua meta",
  quero_aprender: "Quero aprender",
  roadmap: "No seu roadmap",
  objetivo: "Seu objetivo",
};

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

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
  "setembro", "outubro", "novembro", "dezembro"];

function mesPorExtenso(anoMes: string): string {
  const [ano, mes] = anoMes.split("-").map(Number);
  return MESES[mes - 1] ? `${MESES[mes - 1]} de ${ano}` : anoMes;
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
  const { dispatch } = useAppState();
  const lista = useQuery(() => coursesApi.list(), []);
  const [filtro, setFiltro] = useState<Filtro>("todos");

  if (lista.loading) return <Loading label="Procurando cursos com certificado…" />;
  if (lista.error) return <ErrorState message={lista.error} onRetry={lista.reload} />;
  if (!lista.data) return null;

  const { cursos, conferido_em, tem_pedido } = lista.data;
  const gratuitos = cursos.filter((curso) => curso.certificado.gratuito);
  const pagos = cursos.filter((curso) => !curso.certificado.gratuito);

  return (
    <div style={SCREEN_IN}>
      <header
        style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: 16.8, marginBottom: 16.8 }}
      >
        <div style={{ flex: 1, minWidth: 250 }}>
          <div style={{ fontSize: SIZE.apoio, color: TEXT.muted }}>
            {cursos.length} {cursos.length === 1 ? "curso" : "cursos"} · {gratuitos.length} com certificado
            gratuito
          </div>
          <h1 style={{ fontSize: 28, margin: 0 }}>Cursos com certificado</h1>
          <p style={{ margin: "5.6px 0 0", fontSize: SIZE.corpo, color: TEXT.strong, maxWidth: "70ch" }}>
            Escolhidos pelo que você quer aprender, para colocar no LinkedIn. Todos emitem
            certificado, e os gratuitos vêm sempre primeiro.
          </p>
        </div>
        {cursos.length > 0 ? (
          <Segmented
            name="cursos-filtro"
            label="Tipo de certificado"
            value={filtro}
            options={FILTROS}
            onChange={setFiltro}
          />
        ) : null}
      </header>

      {cursos.length === 0 ? (
        tem_pedido ? (
          <EmptyState
            title="Ainda não há certificação séria para o que você pediu"
            description="Só entram cursos com certificado de emissor reconhecido. Marque outras tecnologias como meta e a lista cresce."
            action={
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => dispatch({ type: "navigate", screen: "config", settingsTab: "skills" })}
              >
                <Icon name="code" size={15} />
                Escolher tecnologias
              </button>
            }
          />
        ) : (
          <EmptyState
            title="Diga o que você quer aprender"
            description="Os cursos saem do seu objetivo e das tecnologias marcadas como meta. Sem isso, não há como escolher."
            action={
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => dispatch({ type: "navigate", screen: "config", settingsTab: "objetivo" })}
              >
                <Icon name="flag" size={15} />
                Definir objetivo
              </button>
            }
          />
        )
      ) : (
        <>
          {filtro !== "pagos" ? (
            <Bloco titulo="Certificado gratuito" cursos={gratuitos} vazio="Nenhum curso gratuito para o que você pediu." />
          ) : null}
          {filtro !== "gratuitos" ? (
            <Bloco titulo="Certificado pago" cursos={pagos} vazio="Nenhum curso pago para o que você pediu." />
          ) : null}
          <p style={{ margin: "22.4px 0 0", fontSize: 11.5, color: TEXT.faint, maxWidth: "76ch" }}>
            Preços e gratuidade conferidos em {mesPorExtenso(conferido_em)}. Quem define é o emissor, e
            as condições mudam: confira no site antes de começar.
          </p>
        </>
      )}
    </div>
  );
}

function Bloco({ titulo, cursos, vazio }: { titulo: string; cursos: Course[]; vazio: string }) {
  return (
    <section aria-label={titulo} style={{ marginBottom: 28 }}>
      <Kicker style={{ display: "block", marginBottom: 11.2 }}>
        {titulo} · {cursos.length}
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
            <CartaoDoCurso key={curso.id} curso={curso} />
          ))}
        </div>
      )}
    </section>
  );
}

function CartaoDoCurso({ curso }: { curso: Course }) {
  const [possuo, setPossuo] = useState(Boolean(curso.possuo));
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const { gratuito, detalhe } = curso.certificado;

  // Otimista: o botão muda na hora e volta atrás se o servidor recusar.
  async function alternarPossuo() {
    const antes = possuo;
    setPossuo(!antes);
    setSalvando(true);
    setErro(null);
    try {
      if (antes) await coursesApi.disown(curso.id);
      else await coursesApi.own(curso.id);
    } catch (caught) {
      setPossuo(antes);
      setErro(caught instanceof Error ? caught.message : "Não consegui salvar.");
    } finally {
      setSalvando(false);
    }
  }
  const corDoSelo = gratuito ? C.verde : C.ambar;
  const meta = [curso.emissor, NIVEL[curso.nivel], curso.idioma === "pt" ? "Português" : "Inglês"];
  if (curso.horas) meta.push(`~${curso.horas}h`);

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
              {gratuito ? "Certificado gratuito" : "Certificado pago"}
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
            href={curso.url}
            target="_blank"
            rel="noreferrer noopener"
            style={{ textDecoration: "none" }}
          >
            Ir para o curso
            <Icon name="externalLink" size={14} />
          </a>
          <button
            type="button"
            className={possuo ? "btn btn-primary" : "btn btn-secondary"}
            aria-pressed={possuo}
            disabled={salvando}
            onClick={() => void alternarPossuo()}
            title={possuo ? "Aparece em Perfil e tags. Clique para desmarcar." : "Marque se você já tem este certificado."}
            style={possuo ? { background: tint(C.verde, 14), borderColor: C.verde, color: C.verde } : undefined}
          >
            {possuo ? <Icon name="check" size={14} /> : null}
            {possuo ? "Já possuo" : "Já possuo?"}
          </button>
          <a
            className="btn btn-ghost"
            href={linkParaLinkedIn(curso)}
            target="_blank"
            rel="noreferrer noopener"
            title="Depois de receber o certificado"
            style={{ textDecoration: "none", fontSize: SIZE.apoio }}
          >
            <Icon name="externalLink" size={15} />
            Adicionar ao LinkedIn
          </a>
        </div>
        {erro ? <div style={{ fontSize: 12, color: C.ambar }}>{erro}</div> : null}
      </article>
    </Panel>
  );
}

function BarraDeChama({ demanda }: { demanda: Course["demanda"] }) {
  const { acesos, cor } = CHAMA[demanda.faixa];
  const quente = acesos >= 4;
  return (
    <div>
      <div
        role="meter"
        aria-label="Procura no mercado"
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
