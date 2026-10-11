/**
 * Newsletter: montar, agendar, conferir e enviar.
 *
 * Só o super admin (o SettingsPage decide se mostra a aba; o servidor responde
 * 404 para qualquer outra conta). Tudo é decidido no servidor — esta tela lê
 * `GET /admin/newsletter`, grava em `PUT /admin/newsletter/config` e dispara
 * `buscar` / `enviar`.
 *
 * ## A ordem da tela é a ordem da decisão
 *
 * Um resumo em frase no topo ("Toda segunda-feira, às 08:00, você recebe 4
 * combinações…"), que muda enquanto se escolhe; depois sobre o quê, o que
 * acompanhar, o que isso vira (as combinações), quando receber. A barra fixa
 * no pé guarda as ações, para salvar nunca exigir rolar de volta.
 *
 * ## O campo "Combinações"
 *
 * "Java + Empregos": a tecnologia e o ângulo que a busca vai cruzar, montados
 * AQUI, ao vivo, do que está marcado. O ecossistema de cada uma ("Inclui
 * Spring Boot, JVM, Kotlin") vem do servidor, que é quem o conhece.
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
import { Icon, type IconName } from "@/components/ui/icons";
import { Select, type SelectOption } from "@/components/ui/Select";
import { ErrorState, Loading } from "@/components/ui/States";
import { ANGULO, MateriaCard, estiloDoAngulo } from "@/components/admin/NewsletterCard";
import "@/styles/newsletter.css";

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
const HORARIOS_RAPIDOS = [7, 8, 12, 18, 20] as const;
/** Os dias que cada atalho decide sozinho (0 = segunda). */
const DIAS_DO_ATALHO: Partial<Record<FrequenciaNewsletter, readonly number[]>> = {
  diaria: [0, 1, 2, 3, 4, 5, 6],
  dias_uteis: [0, 1, 2, 3, 4],
  fim_de_semana: [5, 6],
};

function hhmm(hora: number): string {
  return `${String(hora).padStart(2, "0")}:00`;
}

function dataLonga(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { weekday: "short", day: "2-digit", month: "short" });
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

/** tecnologia (minúsculas) → termos do ecossistema, como o servidor devolveu. */
function ecoDe(combos: CombinacaoNewsletter[]): Record<string, string[]> {
  const mapa: Record<string, string[]> = {};
  for (const c of combos) mapa[c.topico.toLowerCase()] = c.ecossistema;
  return mapa;
}

function CabecalhoDoCartao({
  icon,
  tom,
  titulo,
  sub,
  contador,
  alerta,
}: {
  icon: IconName;
  tom?: string;
  titulo: string;
  sub?: string;
  contador?: string;
  alerta?: boolean;
}) {
  const estilo = tom ? ({ ["--tone" as string]: tom } as CSSProperties) : undefined;
  return (
    <div className="nl-card-head">
      <span className="nl-card-icon" style={estilo}>
        <Icon name={icon} size={18} />
      </span>
      <div style={{ minWidth: 0 }}>
        <h3 className="nl-card-title">{titulo}</h3>
        {sub ? <p className="nl-card-sub">{sub}</p> : null}
      </div>
      {contador ? (
        <span className="nl-card-count" data-alert={alerta ? "true" : undefined}>
          {contador}
        </span>
      ) : null}
    </div>
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
  const cheio = form.topics.length >= limites.max_temas;
  const atalho = DIAS_DO_ATALHO[form.frequency];
  const diasMarcados = atalho ?? form.weekdays;

  // ---- ações sobre o formulário ----

  function adicionar(bruto: string) {
    const tema = bruto.replace(/\s+/g, " ").trim().slice(0, 60);
    if (!tema || cheio) return;
    if (form.topics.some((x) => x.toLowerCase() === tema.toLowerCase())) {
      setNovoTema("");
      return;
    }
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
      setAviso({ tom: "ok", texto: t("newsletter.aviso.salvo") });
      onSalvo();
    } else {
      setAviso({ tom: "erro", texto: salvar.error ?? t("newsletter.aviso.erroSalvar") });
    }
  }

  async function aoBuscar() {
    setAviso(null);
    const r = await buscar.run(form);
    if (!r) {
      setAviso({ tom: "erro", texto: buscar.error ?? t("newsletter.aviso.erroSalvar") });
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
      setAviso({ tom: "erro", texto: enviar.error ?? t("newsletter.aviso.erroSalvar") });
      return;
    }
    setAviso(
      r.enviado
        ? { tom: "ok", texto: t("newsletter.aviso.enviada", { assunto: r.assunto ?? "" }) }
        : { tom: "erro", texto: t("newsletter.aviso.naoEnviada", { motivo: r.motivo ?? "" }) },
    );
    if (r.enviado) onSalvo();
  }

  // ---- textos derivados ----

  function listaEm(nomes: string[]): string {
    if (nomes.length <= 1) return nomes.join("");
    return `${nomes.slice(0, -1).join(", ")} ${t("newsletter.frase.e")} ${nomes[nomes.length - 1]}`;
  }

  function quandoTexto(): string {
    switch (form.frequency) {
      case "semanal":
        return t(`newsletter.diaToda.${form.weekdays[0] ?? 0}`);
      case "mensal":
        return t("newsletter.frase.mensal", { dia: form.month_day });
      case "personalizada":
        return t("newsletter.frase.personalizada", {
          dias: listaEm([...form.weekdays].sort().map((d) => t(`newsletter.diaPlural.${d}`))),
        });
      default:
        return t(`newsletter.frase.${form.frequency}`);
    }
  }

  const combosTexto = total === 1 ? t("newsletter.combinacoes.uma") : t("newsletter.combinacoes.varias", { n: total });
  const hora = hhmm(form.send_hour);
  const proximo = dados.config.next_send_on;
  const ultimo = dados.config.last_sent_on;

  const opcoesHora: readonly SelectOption<string>[] = Array.from({ length: 24 }, (_, h) => ({
    value: String(h),
    label: hhmm(h),
  }));
  const horaForaDosRapidos = !(HORARIOS_RAPIDOS as readonly number[]).includes(form.send_hour);

  return (
    <div className="nl">
      {/* ---- Topo: resumo em frase + interruptor ---- */}
      <section className="nl-hero" aria-labelledby="nl-hero-titulo">
        <div className="nl-hero-top">
          <span className="nl-hero-icon">
            <Icon name="mail" size={22} />
          </span>
          <div className="nl-hero-copy">
            <p className="nl-kicker">{t("newsletter.kicker")}</p>
            <h2 id="nl-hero-titulo" className="nl-hero-title">
              {total > 0
                ? t("newsletter.heroFrase", { quando: quandoTexto(), hora, combos: combosTexto })
                : t("newsletter.heroVazio")}
            </h2>
            <p className="nl-hero-sub">
              {total > 0 ? t("newsletter.heroFraseSub") : t("newsletter.heroVazioSub")}
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={form.enabled}
            className="nl-switch"
            onClick={() => setForm({ ...form, enabled: !form.enabled })}
          >
            <span className="nl-switch-track" aria-hidden="true" />
            {form.enabled ? t("newsletter.ativa") : t("newsletter.pausada")}
          </button>
        </div>
        <div className="nl-stats">
          <span className="nl-stat">
            <Icon name="clock" size={15} />
            <span className="nl-stat-label">{t("newsletter.statProximo")}</span>
            <span className="nl-stat-value">
              {form.enabled && proximo ? dataLonga(proximo) : t("newsletter.nenhum")}
            </span>
          </span>
          <span className="nl-stat">
            <Icon name="send" size={15} />
            <span className="nl-stat-label">{t("newsletter.statUltimo")}</span>
            <span className="nl-stat-value">{ultimo ? dataLonga(ultimo) : t("newsletter.nunca")}</span>
          </span>
          <span className="nl-stat">
            <Icon name="mail" size={15} />
            <span className="nl-stat-label">{t("newsletter.statDestino")}</span>
            <span className="nl-stat-value">{dados.destino}</span>
          </span>
        </div>
      </section>

      {/* ---- Avisos de ambiente ---- */}
      {!dados.ativa ? (
        <div className="nl-banner" role="status">
          <Icon name="info" size={16} />
          {t("newsletter.avisoPausada")}
        </div>
      ) : null}
      {!dados.fontes.tavily && !dados.fontes.brave ? (
        <div className="nl-banner" role="status">
          <Icon name="info" size={16} />
          {t("newsletter.avisoSemFonte")}
        </div>
      ) : null}
      {!dados.email_configurado ? (
        <div className="nl-banner" role="status">
          <Icon name="info" size={16} />
          {t("newsletter.avisoSemEmail")}
        </div>
      ) : null}

      {/* ---- Sobre o quê ---- */}
      <section className="nl-card" aria-labelledby="nl-tec">
        <CabecalhoDoCartao
          icon="code"
          titulo={t("newsletter.tecnologias.titulo")}
          sub={t("newsletter.tecnologias.sub")}
          contador={`${form.topics.length}/${limites.max_temas}`}
        />
        <span id="nl-tec" hidden>
          {t("newsletter.tecnologias.titulo")}
        </span>
        <form
          className="nl-add"
          onSubmit={(e) => {
            e.preventDefault();
            adicionar(novoTema);
          }}
        >
          <label className="nl-add-field">
            <Icon name="search" size={16} />
            <input
              id="nl-novo-tema"
              className="input"
              value={novoTema}
              onChange={(e) => setNovoTema(e.target.value)}
              placeholder={t("newsletter.tecnologias.placeholder")}
              aria-label={t("newsletter.tecnologias.rotulo")}
              maxLength={60}
              disabled={cheio}
              autoComplete="off"
            />
          </label>
          <button type="submit" className="btn btn-primary" disabled={!novoTema.trim() || cheio}>
            <Icon name="plus" size={15} />
            {t("newsletter.tecnologias.adicionar")}
          </button>
        </form>

        {form.topics.length ? (
          <div className="nl-chips" role="list">
            {form.topics.map((tema) => (
              <button
                key={tema}
                type="button"
                role="listitem"
                className="nl-chip"
                title={t("newsletter.tecnologias.remover", { nome: tema })}
                aria-label={t("newsletter.tecnologias.remover", { nome: tema })}
                onClick={() => setForm({ ...form, topics: form.topics.filter((x) => x !== tema) })}
              >
                {tema}
                <span className="nl-chip-x">
                  <Icon name="x" size={12} />
                </span>
              </button>
            ))}
          </div>
        ) : (
          <div className="nl-empty">
            <Icon name="search" size={22} />
            {t("newsletter.tecnologias.vazio")}
          </div>
        )}

        {cheio ? <p className="nl-hint">{t("newsletter.tecnologias.limite", { max: limites.max_temas })}</p> : null}

        <div>
          <span className="nl-field-label">{t("newsletter.tecnologias.sugestoes")}</span>
          <div className="nl-chips">
            {SUGESTOES.filter((s) => !form.topics.some((x) => x.toLowerCase() === s.toLowerCase())).map((s) => (
              <button key={s} type="button" className="nl-suggest" disabled={cheio} onClick={() => adicionar(s)}>
                <Icon name="plus" size={13} />
                {s}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ---- O que acompanhar ---- */}
      <section className="nl-card" aria-label={t("newsletter.angulos.titulo")}>
        <CabecalhoDoCartao
          icon="flag"
          titulo={t("newsletter.angulos.titulo")}
          sub={t("newsletter.angulos.sub")}
          contador={`${form.angles.length}/${ANGULOS.length}`}
        />
        <div className="nl-tiles">
          {ANGULOS.map((a) => (
            <button
              key={a}
              type="button"
              className="nl-tile"
              style={estiloDoAngulo(a)}
              aria-pressed={form.angles.includes(a)}
              onClick={() => alternarAngulo(a)}
            >
              <span className="nl-tile-icon">
                <Icon name={ANGULO[a].icon} size={19} />
              </span>
              <span className="nl-tile-title">{t(`newsletter.angulo.${a}.nome`)}</span>
              <span className="nl-tile-desc">{t(`newsletter.angulo.${a}.desc`)}</span>
              <span className="nl-tile-check" aria-hidden="true">
                <Icon name="check" size={12} />
              </span>
            </button>
          ))}
        </div>
      </section>

      {/* ---- As combinações: "Java + Empregos" ---- */}
      <section className="nl-card" aria-label={t("newsletter.combinacoes.titulo")} aria-live="polite">
        <CabecalhoDoCartao
          icon="search"
          tom="#6aa6de"
          titulo={t("newsletter.combinacoes.titulo")}
          sub={t("newsletter.combinacoes.sub")}
          contador={total > 0 ? t("newsletter.combinacoes.total", { n: total, max: limites.max_consultas }) : undefined}
          alerta={demais}
        />
        {total === 0 ? (
          <div className="nl-empty">
            <Icon name="plus" size={22} />
            {t("newsletter.combinacoes.vazio")}
          </div>
        ) : (
          <ul className="nl-combos">
            {form.topics.flatMap((tema) =>
              form.angles.map((a) => {
                const eco = ecossistema[tema.toLowerCase()];
                return (
                  <li key={`${tema}|${a}`} className="nl-combo" style={estiloDoAngulo(a)}>
                    <div className="nl-combo-line">
                      <span className="nl-combo-tech">{tema}</span>
                      <span className="nl-combo-plus" aria-hidden="true">
                        +
                      </span>
                      <span className="nl-pill">
                        <Icon name={ANGULO[a].icon} size={13} />
                        {t(`newsletter.angulo.${a}.nome`)}
                      </span>
                    </div>
                    <div className="nl-eco">
                      {eco && eco.length ? (
                        <>
                          <span className="nl-eco-label">{t("newsletter.combinacoes.inclui")}</span>
                          {eco.map((termo) => (
                            <span key={termo} className="nl-tag">
                              {termo}
                            </span>
                          ))}
                        </>
                      ) : (
                        <span className="nl-tag" data-pending="true">
                          {t("newsletter.combinacoes.descoberto")}
                        </span>
                      )}
                    </div>
                  </li>
                );
              }),
            )}
          </ul>
        )}
        {demais ? (
          <div className="nl-banner" role="alert">
            <Icon name="info" size={16} />
            {t("newsletter.combinacoes.demais")}
          </div>
        ) : null}
      </section>

      {/* ---- Quando receber ---- */}
      <section className="nl-card" aria-label={t("newsletter.quando.titulo")}>
        <CabecalhoDoCartao
          icon="clock"
          tom="#cfa25e"
          titulo={t("newsletter.quando.titulo")}
          sub={t("newsletter.quando.sub")}
        />

        <div>
          <span className="nl-field-label" id="nl-freq-rotulo">
            {t("newsletter.quando.frequencia")}
          </span>
          <div className="nl-freq" role="radiogroup" aria-labelledby="nl-freq-rotulo">
            {FREQUENCIAS.map((f) => (
              <button
                key={f}
                type="button"
                role="radio"
                aria-checked={form.frequency === f}
                className="nl-freq-opt"
                onClick={() => trocarFrequencia(f)}
              >
                <span className="nl-freq-title">{t(`newsletter.freq.${f}.nome`)}</span>
                <span className="nl-freq-desc">{t(`newsletter.freq.${f}.desc`)}</span>
              </button>
            ))}
          </div>
        </div>

        {form.frequency === "mensal" ? (
          <div>
            <span className="nl-field-label" id="nl-mes-rotulo">
              {t("newsletter.quando.diaDoMes")}
            </span>
            <div className="nl-month" role="group" aria-labelledby="nl-mes-rotulo">
              {Array.from({ length: 28 }, (_, i) => i + 1).map((dia) => (
                <button
                  key={dia}
                  type="button"
                  className="nl-day"
                  aria-pressed={form.month_day === dia}
                  onClick={() => setForm({ ...form, month_day: dia })}
                >
                  {dia}
                </button>
              ))}
            </div>
            <p className="nl-hint">{t("newsletter.quando.diaDoMesNota")}</p>
          </div>
        ) : (
          <div>
            <span className="nl-field-label" id="nl-dias-rotulo">
              {t("newsletter.quando.dias")}
            </span>
            <div className="nl-week" role="group" aria-labelledby="nl-dias-rotulo">
              {DIAS.map((d) => (
                <button
                  key={d}
                  type="button"
                  className="nl-day"
                  aria-pressed={diasMarcados.includes(d)}
                  aria-label={t(`newsletter.diaNome.${d}`)}
                  title={t(`newsletter.diaNome.${d}`)}
                  disabled={Boolean(atalho)}
                  onClick={() => alternarDia(d)}
                >
                  {t(`newsletter.diaCurto.${d}`)}
                </button>
              ))}
            </div>
            {atalho ? <p className="nl-hint">{t("newsletter.quando.diaFixo")}</p> : null}
          </div>
        )}

        <div className="nl-two">
          <div>
            <span className="nl-field-label" id="nl-hora-rotulo">
              {t("newsletter.quando.horario")}
            </span>
            <div className="nl-time" role="group" aria-labelledby="nl-hora-rotulo">
              {HORARIOS_RAPIDOS.map((h) => (
                <button
                  key={h}
                  type="button"
                  className="nl-time-chip"
                  aria-pressed={form.send_hour === h}
                  onClick={() => setForm({ ...form, send_hour: h })}
                >
                  {hhmm(h)}
                </button>
              ))}
              <Select
                id="nl-hora"
                options={opcoesHora}
                value={horaForaDosRapidos ? String(form.send_hour) : ""}
                placeholder={t("newsletter.quando.outroHorario")}
                label={t("newsletter.quando.outroHorario")}
                onChange={(v) => setForm({ ...form, send_hour: Number(v) })}
                style={{ width: 150 }}
              />
            </div>
            <p className="nl-hint">{t("newsletter.quando.horarioNota", { fuso: dados.fuso })}</p>
          </div>

          <div>
            <span className="nl-field-label" id="nl-qtd-rotulo">
              {t("newsletter.quando.quantidade")}
            </span>
            <div className="nl-stepper" role="group" aria-labelledby="nl-qtd-rotulo">
              <button
                type="button"
                aria-label={t("newsletter.quando.menos")}
                disabled={form.items_per_topic <= 1}
                onClick={() => setForm({ ...form, items_per_topic: form.items_per_topic - 1 })}
              >
                −
              </button>
              <output aria-live="polite">{form.items_per_topic}</output>
              <button
                type="button"
                aria-label={t("newsletter.quando.mais")}
                disabled={form.items_per_topic >= limites.max_itens_por_busca}
                onClick={() => setForm({ ...form, items_per_topic: form.items_per_topic + 1 })}
              >
                +
              </button>
            </div>
            <p className="nl-hint">{t("newsletter.quando.quantidadeNota", { max: limites.max_itens_por_busca })}</p>
          </div>
        </div>
      </section>

      {/* ---- Prévia da busca ---- */}
      {achadas ? (
        <section className="nl-card" aria-label={t("newsletter.resultados.titulo")}>
          <CabecalhoDoCartao
            icon="eye"
            tom="#63b48f"
            titulo={t("newsletter.resultados.titulo")}
            sub={
              achadas.length
                ? t("newsletter.resultados.resumo", { n: achadas.length, dias: diasBuscados })
                : undefined
            }
          />
          {achadas.length === 0 ? (
            <div className="nl-empty">
              <Icon name="search" size={22} />
              {t("newsletter.resultados.vazio", { dias: diasBuscados })}
            </div>
          ) : (
            <>
              <div className="nl-results-head">
                <span className="nl-tag">{t("newsletter.resultados.selecionadas", { n: marcadas.size })}</span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setMarcadas(new Set(achadas.map((i) => i.url)))}
                >
                  {t("newsletter.resultados.todas")}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setMarcadas(new Set())}>
                  {t("newsletter.resultados.nenhuma")}
                </button>
                <button
                  type="button"
                  className="btn nl-btn-solid"
                  style={{ marginLeft: "auto" }}
                  disabled={enviar.pending || marcadas.size === 0}
                  onClick={() => void aoEnviar(achadas.filter((i) => marcadas.has(i.url)))}
                >
                  <Icon name="send" size={15} />
                  {t("newsletter.resultados.enviar", { n: marcadas.size })}
                </button>
              </div>
              <ul className="nl-grid">
                {achadas.map((item) => (
                  <MateriaCard
                    key={item.url}
                    item={item}
                    selecionada={marcadas.has(item.url)}
                    onAlternar={() =>
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

      {/* ---- Histórico ---- */}
      <section className="nl-card" aria-label={t("newsletter.historico.titulo")}>
        <CabecalhoDoCartao
          icon="mail"
          titulo={t("newsletter.historico.titulo")}
          sub={t("newsletter.historico.sub")}
        />
        {dados.edicoes.length === 0 ? (
          <div className="nl-empty">
            <Icon name="mail" size={22} />
            {t("newsletter.historico.vazio")}
          </div>
        ) : (
          <>
            <ul className="nl-history">
              {dados.edicoes.slice(0, 5).map((e) => (
                <li key={e.id}>
                  <span className="nl-history-icon">
                    <Icon name="mail" size={16} />
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <div className="nl-history-title">{e.assunto}</div>
                    <div className="nl-history-meta">
                      {dataLonga(e.enviada_em)} ·{" "}
                      {e.quantidade === 1
                        ? t("newsletter.materias.uma")
                        : t("newsletter.materias.varias", { n: e.quantidade })}{" "}
                      · {t(`newsletter.historico.${e.tipo}`)}
                    </div>
                  </div>
                  <a className="nl-link" href="/newsletter" target="_blank" rel="noopener">
                    {t("newsletter.historico.abrir")}
                    <Icon name="externalLink" size={13} />
                  </a>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      {/* ---- Barra de ações fixa ---- */}
      <div className="nl-bar" role="region" aria-label={t("newsletter.kicker")}>
        <span className="nl-bar-status" role="status">
          <span className="nl-dot" data-on={aviso?.tom === "erro" ? "dirty" : sujo ? "dirty" : "ok"} />
          {aviso
            ? aviso.texto
            : sujo
              ? t("newsletter.acoes.alteracoes")
              : t("newsletter.acoes.tudoSalvo")}
        </span>
        <div className="nl-bar-actions">
          {sujo ? (
            <button type="button" className="btn btn-secondary" onClick={() => setForm(salvo)}>
              <Icon name="undo" size={15} />
              {t("newsletter.acoes.descartar")}
            </button>
          ) : null}
          <button
            type="button"
            className="btn btn-secondary"
            disabled={buscar.pending || form.topics.length === 0 || demais}
            onClick={() => void aoBuscar()}
          >
            <Icon name="search" size={15} />
            {buscar.pending ? t("newsletter.acoes.procurando") : t("newsletter.acoes.procurar")}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={enviar.pending || sujo || salvo.topics.length === 0}
            title={t("newsletter.acoes.enviarAjuda")}
            onClick={() => void aoEnviar()}
          >
            <Icon name="send" size={15} />
            {enviar.pending ? t("newsletter.acoes.enviando") : t("newsletter.acoes.enviar")}
          </button>
          <button
            type="button"
            className="btn nl-btn-solid"
            disabled={salvar.pending || demais || !sujo}
            onClick={() => void aoSalvar()}
          >
            <Icon name="check" size={15} />
            {salvar.pending ? t("newsletter.acoes.salvando") : t("newsletter.acoes.salvar")}
          </button>
        </div>
      </div>
    </div>
  );
}

export function NewsletterAdmin() {
  const t = useT();
  const painel = useQuery(() => newsletter.painel(), []);

  return (
    <>
      {painel.loading && !painel.data ? <Loading label={t("newsletter.pagina.carregando")} /> : null}
      {painel.error ? <ErrorState message={painel.error} onRetry={painel.reload} /> : null}
      {painel.data ? <Formulario dados={painel.data} onSalvo={painel.reload} /> : null}
    </>
  );
}
