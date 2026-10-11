/**
 * Newsletter: escolher tecnologias, ângulos, dias e hora; procurar e enviar.
 *
 * Só o super admin (o SettingsPage decide se mostra a aba; o servidor responde
 * 404 para qualquer outra conta). Tudo é decidido no servidor — esta tela lê
 * `GET /admin/newsletter`, grava em `PUT /admin/newsletter/config` e dispara
 * `buscar` / `enviar`.
 *
 * ## O campo "Combinações"
 *
 * "Java + Empregos": a tecnologia e o ângulo que a busca vai cruzar. A lista
 * é montada AQUI, ao vivo, a partir do que está escolhido — a pessoa vê o
 * resultado do que marcou antes de salvar. O ecossistema que cada uma traz
 * ("inclui Spring Boot, JVM, Kotlin") vem do servidor, que é quem o conhece.
 *
 * ## Dois estados de configuração
 *
 * `form` é o que está na tela; `salvo` é o que está gravado. "Enviar edição
 * agora" e o envio automático usam o SALVO, e por isso o botão fica desligado
 * enquanto houver alteração solta: enviar "o que está na tela" sem ter salvo
 * mandaria algo diferente do que o cron mandará amanhã.
 */

import { useMemo, useState, type CSSProperties } from "react";
import {
  newsletter,
  type AnguloNewsletter,
  type CombinacaoNewsletter,
  type ConfigNewsletter,
  type FrequenciaNewsletter,
  type MateriaNewsletter,
  type PainelNewsletter,
} from "@/api/endpoints";
import { useMutation, useQuery } from "@/hooks/useApi";
import { useT } from "@/lib/i18n";
import { linkExterno } from "@/lib/linkExterno";
import { Chip } from "@/components/ui/Chip";
import { Segmented, type SegmentedOption } from "@/components/ui/Segmented";
import { Select, type SelectOption } from "@/components/ui/Select";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";
import { ACC, ACC4, C, TEXT, tint } from "@/lib/tokens";

const SUGESTOES = [
  "Java",
  "Python",
  "JavaScript",
  "TypeScript",
  "C#",
  "Go",
  "Rust",
  "Kotlin",
  "PHP",
  "Kubernetes",
  "DevOps",
  "Inteligência artificial",
];
const ANGULOS: readonly AnguloNewsletter[] = ["noticias", "novidades", "trabalhos", "polemicas"];
const FREQUENCIAS: readonly FrequenciaNewsletter[] = [
  "diaria",
  "dias_uteis",
  "fim_de_semana",
  "semanal",
  "mensal",
  "personalizada",
];
const DIAS = [0, 1, 2, 3, 4, 5, 6] as const;

const SUB: CSSProperties = { margin: "0 0 8px", fontSize: 12.5, color: TEXT.muted, maxWidth: "64ch" };
const SECAO: CSSProperties = { padding: "16px 0", borderTop: "1px solid rgba(233,233,237,.1)" };

function dataLegivel(iso: string | null | undefined): string {
  if (!iso) return "";
  // `YYYY-MM-DD` vira meio-dia local: meia-noite UTC cairia no dia anterior.
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString();
}

function ordenado<T>(lista: T[]): string {
  return JSON.stringify([...lista].sort());
}

function mesmoConfig(a: ConfigNewsletter, b: ConfigNewsletter): boolean {
  return (
    a.enabled === b.enabled &&
    a.frequency === b.frequency &&
    a.month_day === b.month_day &&
    a.send_hour === b.send_hour &&
    a.items_per_topic === b.items_per_topic &&
    JSON.stringify(a.topics) === JSON.stringify(b.topics) &&
    ordenado(a.angles) === ordenado(b.angles) &&
    ordenado(a.weekdays) === ordenado(b.weekdays)
  );
}

function configDe(painel: PainelNewsletter): ConfigNewsletter {
  const c = painel.config;
  return {
    enabled: c.enabled,
    topics: [...c.topics],
    angles: [...c.angles],
    frequency: c.frequency,
    weekdays: [...c.weekdays],
    month_day: c.month_day,
    send_hour: c.send_hour,
    items_per_topic: c.items_per_topic,
  };
}

/** tema (minúsculas) → termos do ecossistema, como o servidor devolveu. */
function ecoDe(combos: CombinacaoNewsletter[]): Record<string, string[]> {
  const mapa: Record<string, string[]> = {};
  for (const c of combos) mapa[c.topico.toLowerCase()] = c.ecossistema;
  return mapa;
}

function Materia({ item, marcada, onMarcar }: { item: MateriaNewsletter; marcada: boolean; onMarcar: () => void }) {
  const t = useT();
  const href = linkExterno(item.url);
  // A foto também passa por `linkExterno`, e só https é exibida.
  const foto = linkExterno(item.imagem)?.startsWith("https://") ? linkExterno(item.imagem) : undefined;
  const via = item.termo && item.termo.toLowerCase() !== item.topico.toLowerCase() ? item.termo : "";
  return (
    <li style={{ display: "flex", gap: 10, padding: "10px 0", borderTop: "1px solid rgba(233,233,237,.08)" }}>
      <input
        type="checkbox"
        checked={marcada}
        onChange={onMarcar}
        aria-label={item.titulo}
        style={{ marginTop: 4, accentColor: ACC }}
      />
      <div style={{ minWidth: 0 }}>
        {foto ? (
          <img
            src={foto}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={(e) => {
              // Foto que não abre some: o título abaixo carrega a matéria.
              e.currentTarget.style.display = "none";
            }}
            style={{
              display: "block",
              width: "100%",
              maxWidth: 360,
              maxHeight: 180,
              objectFit: "cover",
              borderRadius: 8,
              marginBottom: 6,
              border: "1px solid rgba(233,233,237,.12)",
            }}
          />
        ) : null}
        <div style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: ACC4 }}>
          {item.topico} + {t(`newsletter.angulo.${item.categoria}`)}
          {via ? <span style={{ color: TEXT.faint }}> · {t("newsletter.via", { termo: via })}</span> : null}
        </div>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          style={{ display: "block", fontSize: 14.5, color: TEXT.full, textDecoration: "none", marginTop: 2 }}
        >
          {item.titulo}
        </a>
        {item.resumo ? (
          <p style={{ margin: "4px 0 0", fontSize: 12.5, color: TEXT.muted, lineHeight: 1.5 }}>{item.resumo}</p>
        ) : null}
        <div style={{ fontSize: 11.5, color: TEXT.faint, marginTop: 4 }}>
          {[item.fonte, dataLegivel(item.publicado_em)].filter(Boolean).join(" · ")}
        </div>
      </div>
    </li>
  );
}

function Formulario({ dados, onSalvo }: { dados: PainelNewsletter; onSalvo: () => void }) {
  const t = useT();
  const inicial = useMemo(() => configDe(dados), [dados]);
  const [form, setForm] = useState<ConfigNewsletter>(inicial);
  const [salvo, setSalvo] = useState<ConfigNewsletter>(inicial);
  const [novoTema, setNovoTema] = useState("");
  const [ecossistema, setEcossistema] = useState<Record<string, string[]>>(() => ecoDe(dados.combinacoes));
  const [achadas, setAchadas] = useState<MateriaNewsletter[] | null>(null);
  const [diasBuscados, setDiasBuscados] = useState(0);
  const [marcadas, setMarcadas] = useState<Set<string>>(new Set());
  const [aviso, setAviso] = useState<{ tom: "ok" | "erro"; texto: string } | null>(null);

  const salvar = useMutation((config: ConfigNewsletter) => newsletter.salvar(config));
  const buscar = useMutation((config: ConfigNewsletter) =>
    newsletter.buscar({ topics: config.topics, angles: config.angles }),
  );
  const enviar = useMutation((itens?: MateriaNewsletter[]) => newsletter.enviar(itens));

  const { limites } = dados;
  const sujo = !mesmoConfig(form, salvo);
  const total = form.topics.length * form.angles.length;
  const demais = total > limites.max_consultas;

  function adicionar(bruto: string) {
    const tema = bruto.replace(/\s+/g, " ").trim().slice(0, 60);
    if (!tema || form.topics.length >= limites.max_temas) return;
    if (form.topics.some((x) => x.toLowerCase() === tema.toLowerCase())) return;
    setForm({ ...form, topics: [...form.topics, tema] });
    setNovoTema("");
  }

  function alternarAngulo(a: AnguloNewsletter) {
    const tem = form.angles.includes(a);
    // Ao menos um: tecnologia sem ângulo não buscaria nada.
    if (tem && form.angles.length === 1) return;
    setForm({ ...form, angles: tem ? form.angles.filter((x) => x !== a) : [...form.angles, a] });
  }

  function trocarFrequencia(f: FrequenciaNewsletter) {
    const dias = f === "semanal" ? [form.weekdays[0] ?? 0] : form.weekdays.length ? form.weekdays : [0];
    setForm({ ...form, frequency: f, weekdays: dias });
  }

  function alternarDia(d: number) {
    if (form.frequency === "semanal") {
      setForm({ ...form, weekdays: [d] });
      return;
    }
    const tem = form.weekdays.includes(d);
    if (tem && form.weekdays.length === 1) return;
    setForm({ ...form, weekdays: tem ? form.weekdays.filter((x) => x !== d) : [...form.weekdays, d].sort() });
  }

  async function aoSalvar() {
    setAviso(null);
    const r = await salvar.run(form);
    if (r) {
      setSalvo(form);
      setEcossistema((atual) => ({ ...atual, ...ecoDe(r.combinacoes) }));
      setAviso({ tom: "ok", texto: t("newsletter.salvo") });
      onSalvo();
    } else {
      setAviso({ tom: "erro", texto: salvar.error ?? t("newsletter.erroSalvar") });
    }
  }

  async function aoBuscar() {
    setAviso(null);
    const r = await buscar.run(form);
    if (!r) {
      setAviso({ tom: "erro", texto: buscar.error ?? t("newsletter.erroSalvar") });
      return;
    }
    setAchadas(r.itens);
    setDiasBuscados(r.dias);
    setMarcadas(new Set(r.itens.map((i) => i.url)));
    setEcossistema((atual) => ({ ...atual, ...ecoDe(r.combinacoes) }));
  }

  async function aoEnviar(itens?: MateriaNewsletter[]) {
    setAviso(null);
    const r = await enviar.run(itens);
    if (!r) {
      setAviso({ tom: "erro", texto: enviar.error ?? t("newsletter.erroSalvar") });
      return;
    }
    setAviso(
      r.enviado
        ? { tom: "ok", texto: t("newsletter.enviada", { assunto: r.assunto ?? "" }) }
        : { tom: "erro", texto: t("newsletter.naoEnviada", { motivo: r.motivo ?? "" }) },
    );
    if (r.enviado) onSalvo();
  }

  const opcoesFrequencia: readonly SelectOption<FrequenciaNewsletter>[] = FREQUENCIAS.map((f) => ({
    value: f,
    label: t(`newsletter.frequenciaOpcao.${f}`),
  }));
  const opcoesHora: readonly SelectOption<string>[] = Array.from({ length: 24 }, (_, h) => ({
    value: String(h),
    label: `${String(h).padStart(2, "0")}:00`,
  }));
  const opcoesDiaDoMes: readonly SelectOption<string>[] = Array.from({ length: 28 }, (_, i) => ({
    value: String(i + 1),
    label: String(i + 1),
  }));
  const opcoesQuantidade: readonly SelectOption<string>[] = Array.from(
    { length: limites.max_itens_por_busca },
    (_, i) => ({ value: String(i + 1), label: String(i + 1) }),
  );
  const opcoesLigado: readonly SegmentedOption<"ligada" | "pausada">[] = [
    { value: "ligada", label: t("newsletter.ligada") },
    { value: "pausada", label: t("newsletter.pausada") },
  ];

  const hora = `${String(form.send_hour).padStart(2, "0")}:00`;
  const proximo = dados.config.next_send_on;

  return (
    <div>
      {!dados.ativa ? (
        <p role="status" style={{ ...SUB, color: C.ambar }}>
          {t("newsletter.avisoPausada")}
        </p>
      ) : null}
      {!dados.fontes.tavily && !dados.fontes.brave ? (
        <p role="status" style={{ ...SUB, color: C.ambar }}>
          {t("newsletter.avisoSemFonte")}
        </p>
      ) : null}
      {!dados.email_configurado ? (
        <p role="status" style={{ ...SUB, color: C.ambar }}>
          {t("newsletter.avisoSemEmail")}
        </p>
      ) : null}

      {/* Tecnologias */}
      <section style={SECAO}>
        <Kicker tone="muted" style={{ display: "block", marginBottom: 4 }}>
          {t("newsletter.tecnologias")}
        </Kicker>
        <p style={SUB}>{t("newsletter.tecnologiasAjuda", { max: limites.max_temas })}</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            adicionar(novoTema);
          }}
          style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}
        >
          <input
            className="input"
            value={novoTema}
            onChange={(e) => setNovoTema(e.target.value)}
            placeholder={t("newsletter.adicionarPlaceholder")}
            aria-label={t("newsletter.adicionarRotulo")}
            maxLength={60}
            style={{ flex: "1 1 220px", minWidth: 0 }}
          />
          <button
            type="submit"
            className="btn btn-ghost"
            disabled={!novoTema.trim() || form.topics.length >= limites.max_temas}
          >
            {t("newsletter.adicionar")}
          </button>
        </form>
        {form.topics.length ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
            {form.topics.map((tema) => (
              <Chip
                key={tema}
                active
                title={t("newsletter.remover", { nome: tema })}
                onClick={() => setForm({ ...form, topics: form.topics.filter((x) => x !== tema) })}
              >
                {tema} ×
              </Chip>
            ))}
          </div>
        ) : null}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 12, color: TEXT.faint }}>{t("newsletter.sugestoes")}:</span>
          {SUGESTOES.filter((s) => !form.topics.some((x) => x.toLowerCase() === s.toLowerCase())).map((s) => (
            <Chip key={s} dashed active={false} onClick={() => adicionar(s)}>
              + {s}
            </Chip>
          ))}
        </div>
      </section>

      {/* Ângulos */}
      <section style={SECAO}>
        <Kicker tone="muted" style={{ display: "block", marginBottom: 4 }}>
          {t("newsletter.angulos")}
        </Kicker>
        <p style={SUB}>{t("newsletter.angulosAjuda")}</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {ANGULOS.map((a) => (
            <Chip key={a} active={form.angles.includes(a)} onClick={() => alternarAngulo(a)}>
              {t(`newsletter.angulo.${a}`)}
            </Chip>
          ))}
        </div>
      </section>

      {/* O campo das combinações: "Java + Empregos" */}
      <section style={SECAO} aria-live="polite">
        <Kicker tone="muted" style={{ display: "block", marginBottom: 4 }}>
          {t("newsletter.combinacoes")}
        </Kicker>
        <p style={SUB}>{t("newsletter.combinacoesAjuda")}</p>
        {total === 0 ? (
          <p style={{ ...SUB, color: TEXT.faint }}>{t("newsletter.combinacoesVazio")}</p>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 6 }}>
            {form.topics.flatMap((tema) =>
              form.angles.map((a) => {
                const eco = ecossistema[tema.toLowerCase()];
                return (
                  <li
                    key={`${tema}|${a}`}
                    style={{
                      padding: "8px 10px",
                      borderRadius: 8,
                      background: tint(ACC, 10),
                      border: "1px solid rgba(145,132,217,.28)",
                    }}
                  >
                    <span style={{ fontSize: 14, color: TEXT.full }}>
                      {tema} + {t(`newsletter.angulo.${a}`)}
                    </span>
                    <span style={{ display: "block", fontSize: 12, color: TEXT.faint, marginTop: 2 }}>
                      {eco && eco.length
                        ? t("newsletter.inclui", { termos: eco.join(", ") })
                        : t("newsletter.ecossistemaDescoberto")}
                    </span>
                  </li>
                );
              }),
            )}
          </ul>
        )}
        <p style={{ ...SUB, margin: "8px 0 0", color: demais ? C.ambar : TEXT.faint }}>
          {demais
            ? t("newsletter.combinacoesDemais")
            : t("newsletter.combinacoesTotal", { n: total, max: limites.max_consultas })}
        </p>
      </section>

      {/* Quando: frequência, dias e hora */}
      <section style={SECAO}>
        <Kicker tone="muted" style={{ display: "block", marginBottom: 8 }}>
          {t("newsletter.quando")}
        </Kicker>
        <div style={{ display: "grid", gap: 14 }}>
          <div>
            <label htmlFor="nl-frequencia" style={{ ...SUB, display: "block" }}>
              {t("newsletter.frequencia")}
            </label>
            <Select
              id="nl-frequencia"
              options={opcoesFrequencia}
              value={form.frequency}
              onChange={trocarFrequencia}
              style={{ maxWidth: 300 }}
            />
          </div>

          {form.frequency === "semanal" || form.frequency === "personalizada" ? (
            <div role="group" aria-label={t("newsletter.diasDaSemana")}>
              <span style={{ ...SUB, display: "block" }}>{t("newsletter.diasDaSemana")}</span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {DIAS.map((d) => (
                  <Chip key={d} active={form.weekdays.includes(d)} onClick={() => alternarDia(d)}>
                    {t(`newsletter.dia.${d}`)}
                  </Chip>
                ))}
              </div>
            </div>
          ) : null}

          {form.frequency === "mensal" ? (
            <div>
              <label htmlFor="nl-dia-mes" style={{ ...SUB, display: "block" }}>
                {t("newsletter.diaDoMes")}
              </label>
              <Select
                id="nl-dia-mes"
                options={opcoesDiaDoMes}
                value={String(form.month_day)}
                onChange={(v) => setForm({ ...form, month_day: Number(v) })}
                style={{ maxWidth: 120 }}
              />
              <p style={{ ...SUB, margin: "6px 0 0", color: TEXT.faint }}>{t("newsletter.diaDoMesNota")}</p>
            </div>
          ) : null}

          <div>
            <label htmlFor="nl-hora" style={{ ...SUB, display: "block" }}>
              {t("newsletter.horario")}
            </label>
            <Select
              id="nl-hora"
              options={opcoesHora}
              value={String(form.send_hour)}
              onChange={(v) => setForm({ ...form, send_hour: Number(v) })}
              style={{ maxWidth: 140 }}
            />
            <p style={{ ...SUB, margin: "6px 0 0", color: TEXT.faint }}>
              {t("newsletter.horarioNota", { hora, fuso: dados.fuso })}
            </p>
          </div>

          <div>
            <label htmlFor="nl-quantidade" style={{ ...SUB, display: "block" }}>
              {t("newsletter.porCombinacao")}
            </label>
            <Select
              id="nl-quantidade"
              options={opcoesQuantidade}
              value={String(form.items_per_topic)}
              onChange={(v) => setForm({ ...form, items_per_topic: Number(v) })}
              style={{ maxWidth: 120 }}
            />
          </div>

          <div>
            <span style={{ ...SUB, display: "block" }}>{t("newsletter.envio")}</span>
            <Segmented
              name="nl-ligada"
              label={t("newsletter.envio")}
              options={opcoesLigado}
              value={form.enabled ? "ligada" : "pausada"}
              onChange={(v) => setForm({ ...form, enabled: v === "ligada" })}
              style={{ maxWidth: 260 }}
            />
          </div>
        </div>

        <p style={{ ...SUB, margin: "14px 0 0" }}>
          {proximo ? t("newsletter.proximo", { data: dataLegivel(proximo) }) : t("newsletter.semProximo")}
          {dados.config.last_sent_on
            ? ` · ${t("newsletter.ultimo", { data: dataLegivel(dados.config.last_sent_on) })}`
            : ""}
        </p>
      </section>

      {/* Ações */}
      <section style={{ ...SECAO, display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={salvar.pending || demais}
          onClick={() => void aoSalvar()}
        >
          {salvar.pending ? t("newsletter.salvando") : t("newsletter.salvar")}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={buscar.pending || form.topics.length === 0 || demais}
          onClick={() => void aoBuscar()}
        >
          {buscar.pending ? t("newsletter.procurando") : t("newsletter.procurar")}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={enviar.pending || sujo || salvo.topics.length === 0}
          title={t("newsletter.enviarAgoraAjuda")}
          onClick={() => void aoEnviar()}
        >
          {enviar.pending ? t("newsletter.enviando") : t("newsletter.enviarAgora")}
        </button>
        {sujo ? <span style={{ fontSize: 12, color: C.ambar }}>{t("newsletter.naoSalvo")}</span> : null}
        {aviso ? (
          <span
            role={aviso.tom === "erro" ? "alert" : "status"}
            style={{ fontSize: 12.5, color: aviso.tom === "erro" ? C.ambar : C.verde }}
          >
            {aviso.texto}
          </span>
        ) : null}
      </section>

      {/* O que a busca achou */}
      {achadas ? (
        <section style={SECAO}>
          {achadas.length === 0 ? (
            <p style={SUB}>{t("newsletter.semResultados")}</p>
          ) : (
            <>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: 13.5, color: TEXT.full }}>
                  {t("newsletter.resultados", { n: achadas.length, dias: diasBuscados })}
                </span>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setMarcadas(new Set(achadas.map((i) => i.url)))}
                >
                  {t("newsletter.marcarTodas")}
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={enviar.pending || marcadas.size === 0}
                  onClick={() => void aoEnviar(achadas.filter((i) => marcadas.has(i.url)))}
                >
                  {t("newsletter.enviarSelecionadas", { n: marcadas.size, destino: dados.destino })}
                </button>
              </div>
              <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {achadas.map((item) => (
                  <Materia
                    key={item.url}
                    item={item}
                    marcada={marcadas.has(item.url)}
                    onMarcar={() =>
                      setMarcadas((atual) => {
                        const novo = new Set(atual);
                        if (novo.has(item.url)) novo.delete(item.url);
                        else novo.add(item.url);
                        return novo;
                      })
                    }
                  />
                ))}
              </ul>
            </>
          )}
        </section>
      ) : null}

      {/* Histórico */}
      <section style={SECAO}>
        <Kicker tone="muted" style={{ display: "block", marginBottom: 6 }}>
          {t("newsletter.historico")}
        </Kicker>
        {dados.edicoes.length === 0 ? (
          <p style={SUB}>{t("newsletter.historicoVazio")}</p>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {dados.edicoes.slice(0, 5).map((e) => (
              <li key={e.id} style={{ padding: "6px 0", fontSize: 13, color: TEXT.muted }}>
                <span style={{ color: TEXT.full }}>{e.assunto}</span> · {dataLegivel(e.enviada_em)} ·{" "}
                {t("newsletter.materias", { n: e.quantidade })} · {t(`newsletter.tipo.${e.tipo}`)}
              </li>
            ))}
          </ul>
        )}
        <a href="/newsletter" target="_blank" rel="noopener" style={{ fontSize: 12.5, color: ACC }}>
          {t("newsletter.abrirArquivo")}
        </a>
      </section>
    </div>
  );
}

export function NewsletterAdmin() {
  const t = useT();
  const painel = useQuery(() => newsletter.painel(), []);

  return (
    <Panel pad={16.8}>
      <Kicker tone="muted" style={{ display: "block", marginBottom: 4 }}>
        {t("newsletter.titulo")}
      </Kicker>
      <p style={SUB}>{t("newsletter.explica")}</p>
      {painel.loading ? <Loading label={t("newsletter.pagina.carregando")} /> : null}
      {painel.error ? <ErrorState message={painel.error} onRetry={painel.reload} /> : null}
      {painel.data ? <Formulario dados={painel.data} onSalvo={painel.reload} /> : null}
    </Panel>
  );
}
