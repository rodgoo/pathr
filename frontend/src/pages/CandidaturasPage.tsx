/**
 * Candidaturas: as vagas que o app separou hoje, com o currículo pronto para ir.
 *
 * ## O que esta tela resolve
 *
 * Procurar vaga é um trabalho diário e repetitivo: abrir os sites, filtrar o
 * que tem a ver, escrever de novo a mesma carta. O servidor faz a primeira
 * parte todo dia de manhã, sozinho (services/candidaturas.py) — inclusive com
 * o computador de casa desligado, porque quem procura é o backend.
 *
 * ## Por que não envia tudo sozinho
 *
 * Duas coisas diferentes:
 *
 * - vaga com e-mail de contato: o app manda a carta com o currículo em anexo;
 * - vaga que pede para responder no site (Gupy, LinkedIn, formulário próprio
 *   com perguntas): a tela dá o LINK para abrir e responder, com a carta ao
 *   lado para copiar. Ninguém responde essas perguntas no lugar da pessoa —
 *   cada vaga pergunta uma coisa, e responder por ela seria inventar resposta
 *   em nome dela para o recrutador. Um robô que loga nesses sites também
 *   violaria os termos deles e arriscaria bloquear a conta de quem está
 *   procurando emprego.
 */

import { useEffect, useMemo, useState } from "react";
import { candidaturas as candidaturasApi, profile as profileApi, resumes as resumesApi } from "@/api/endpoints";
import type { Candidatura, PassoDaCandidatura, PerguntaPendente } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useMutation, useQuery } from "@/hooks/useApi";
import { ACC, ACC4, C, HAIRLINE, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { useT } from "@/lib/i18n";

export function CandidaturasPage() {
  const t = useT();
  const { dispatch } = useAppState();
  const fila = useQuery(() => candidaturasApi.list(), []);
  const curriculos = useQuery(() => resumesApi.list(), []);
  const [erro, setErro] = useState<string | null>(null);

  const gerar = useMutation(() => candidaturasApi.gerar());

  const temCurriculo = (curriculos.data ?? []).some((item) => item.status === "parsed");
  const lista = fila.data?.candidaturas ?? [];
  const hoje = useMemo(() => lista.filter((c) => c.day === fila.data?.hoje), [lista, fila.data?.hoje]);
  const anteriores = useMemo(() => lista.filter((c) => c.day !== fila.data?.hoje), [lista, fila.data?.hoje]);

  async function buscarAgora() {
    setErro(null);
    const resposta = await gerar.run();
    if (resposta) fila.reload();
  }

  return (
    <div style={{ ...SCREEN_IN, display: "flex", flexDirection: "column", gap: 16.8 }}>
      <header>
        <Kicker style={{ display: "block", marginBottom: 5.6 }}>{t("candidaturas.kicker")}</Kicker>
        <h1 style={{ fontSize: 23, fontWeight: 500, margin: 0 }}>{t("candidaturas.titulo")}</h1>
        <p style={{ fontSize: 13, color: TEXT.muted, margin: "8.4px 0 0", maxWidth: "72ch" }}>
          Todo dia de manhã o PathR separa as vagas que mais combinam com o seu currículo e escreve uma
          carta de apresentação para cada uma. Onde a vaga tem e-mail de contato, o envio sai daqui com o
          currículo em anexo. Onde a vaga tem perguntas próprias, você recebe o link para abrir e responder.
        </p>
      </header>

      {curriculos.loading && !curriculos.data ? <Loading label="Carregando…" /> : null}

      {!curriculos.loading && !temCurriculo ? (
        <Panel pad={16.8}>
          <EmptyState
            title="Comece pelo seu currículo"
            description="É dele que saem as vagas escolhidas e a carta de apresentação. Envie o arquivo e deixe a IA ler uma vez — depois disso, a fila do dia vem sozinha."
            action={
              <button type="button" className="btn btn-primary" onClick={() => dispatch({ type: "navigate", screen: "cv" })}>
                <Icon name="upload" size={15} />
                Enviar meu currículo
              </button>
            }
          />
        </Panel>
      ) : null}

      {temCurriculo ? <EnvioAutomatico /> : null}

      {temCurriculo ? (
        <Panel pad={16.8}>
          <div style={{ display: "flex", gap: 11.2, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ flex: 1, minWidth: 220 }}>
              <Kicker style={{ display: "block", marginBottom: 4 }}>Hoje</Kicker>
              <p style={{ margin: 0, fontSize: 13.5, color: TEXT.full }}>
                {hoje.length > 0
                  ? `${hoje.length} ${hoje.length === 1 ? "vaga separada" : "vagas separadas"} para você`
                  : "Nenhuma vaga nova hoje ainda."}
              </p>
              {/* O que a pessoa pergunta todo dia: quantos currículos saíram. */}
              <div style={{ display: "flex", gap: 16.8, marginTop: 8.4, flexWrap: "wrap" }}>
                {([
                  ["hoje", "candidaturas.enviadasHoje"],
                  ["ontem", "candidaturas.ontem"],
                  ["ultimos7", "candidaturas.ultimos7"],
                ] as const).map(([campo, rotulo]) => (
                  <div key={campo}>
                    <div style={{ fontSize: 18, fontWeight: 500, color: TEXT.full }}>
                      {fila.data?.resumo?.[campo] ?? 0}
                    </div>
                    <div style={{ fontSize: 11, color: TEXT.faint }}>{t(rotulo)}</div>
                  </div>
                ))}
              </div>
            </div>
            <button type="button" className="btn btn-secondary" disabled={gerar.pending} onClick={() => void buscarAgora()}>
              <Icon name="refresh" size={15} />
              {gerar.pending ? "Buscando vagas…" : "Buscar vagas agora"}
            </button>
          </div>
          {gerar.error ? <ErrorState message={gerar.error} /> : null}
          {erro ? <ErrorState message={erro} /> : null}
        </Panel>
      ) : null}

      {fila.error ? <ErrorState message={fila.error} onRetry={fila.reload} /> : null}
      {fila.loading && !fila.data ? <Loading label="Carregando suas candidaturas…" /> : null}

      {hoje.map((item) => (
        <Cartao key={item.id} item={item} onMudou={() => fila.reload()} onErro={setErro} />
      ))}

      {anteriores.length > 0 ? (
        <section style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
          <Kicker style={{ display: "block" }}>Dias anteriores</Kicker>
          {anteriores.map((item) => (
            <Cartao key={item.id} item={item} onMudou={() => fila.reload()} onErro={setErro} />
          ))}
        </section>
      ) : null}

      {temCurriculo && !fila.loading && lista.length === 0 ? (
        <EmptyState
          title="A fila de hoje ainda não foi montada"
          description="Ela chega de manhã, no seu horário, junto com um e-mail. Se quiser ver agora, use “Buscar vagas agora”."
        />
      ) : null}
    </div>
  );
}

/** Os passos do envio, na ordem — o mesmo `PASSOS` do servidor. */
const PASSOS = ["anuncio", "curriculo", "carta", "respostas", "envio"] as const;

const COR_DA_SITUACAO: Record<string, string> = {
  feito: C.verde,
  pendente: C.ambar,
  falhou: C.rosa,
  pulado: TEXT.faint,
};

/**
 * O passo a passo de uma candidatura, acontecendo.
 *
 * Uma linha do tempo em vez de um "carregando": o que o app faz em nome da
 * pessoa não pode ser caixa preta — ela precisa ver o currículo ser conferido,
 * a carta ser escrita, as respostas preenchidas e o envio acontecer (ou parar,
 * e onde parou).
 */
function LinhaDoTempo({ passos, rodando }: { passos: PassoDaCandidatura[]; rodando: boolean }) {
  const t = useT();
  const porNome = new Map(passos.map((passo) => [passo.passo, passo]));
  const primeiroSemResultado = PASSOS.find((nome) => !porNome.has(nome));

  return (
    <ol
      aria-label={t("candidaturas.passos.titulo")}
      style={{ listStyle: "none", margin: "14px 0 0", padding: 0 }}
    >
      {PASSOS.map((nome, indice) => {
        const passo = porNome.get(nome);
        const fazendo = rodando && nome === primeiroSemResultado;
        const cor = passo ? COR_DA_SITUACAO[passo.situacao] ?? TEXT.muted : fazendo ? ACC : HAIRLINE;
        return (
          <li key={nome} style={{ display: "flex", gap: 11.2, alignItems: "flex-start", minHeight: 34 }}>
            {/* O ponto e a linha que liga ao próximo — menos no último. */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", alignSelf: "stretch" }}>
              <span
                aria-hidden
                style={{
                  width: 11,
                  height: 11,
                  borderRadius: "50%",
                  marginTop: 5,
                  background: cor,
                  boxShadow: fazendo ? `0 0 0 4px ${tint(ACC, 18)}` : "none",
                }}
              />
              {indice < PASSOS.length - 1 ? (
                <span aria-hidden style={{ flex: 1, width: 2, background: HAIRLINE, marginTop: 2 }} />
              ) : null}
            </div>
            <div style={{ paddingBottom: 8 }}>
              <div style={{ fontSize: 13, color: passo || fazendo ? TEXT.full : TEXT.faint }}>
                {t(`candidaturas.passos.${nome}`)}
                {fazendo ? ` · ${t("candidaturas.passos.fazendo")}` : ""}
              </div>
              {passo?.detalhe ? (
                <div style={{ fontSize: 11.5, color: TEXT.muted, marginTop: 2 }}>{passo.detalhe}</div>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * As perguntas que o app não pode responder por você.
 *
 * Aparecem como campo, e o que você escreve entra no banco de respostas: a
 * mesma pergunta, em qualquer outro site, já vem preenchida na próxima vez.
 * Pergunta sensível (gênero, raça, deficiência) fica marcada e NÃO é guardada
 * — é opcional no formulário, e a escolha é sua a cada vez.
 */
function PerguntasQueFaltam({
  pendentes,
  aoSalvar,
  salvando,
}: {
  pendentes: PerguntaPendente[];
  aoSalvar: (respostas: { pergunta: string; chave: string; resposta: string }[]) => void;
  salvando: boolean;
}) {
  const t = useT();
  const [digitadas, setDigitadas] = useState<Record<string, string>>({});
  if (pendentes.length === 0) return null;

  const preenchidas = pendentes
    .map((item) => ({ pergunta: item.pergunta, chave: item.chave, resposta: (digitadas[item.chave] ?? "").trim() }))
    .filter((item) => item.resposta);

  return (
    <div style={{ marginTop: 14, borderTop: `1px solid ${HAIRLINE}`, paddingTop: 14 }}>
      <Kicker style={{ display: "block", marginBottom: 4 }}>{t("candidaturas.faltam.titulo")}</Kicker>
      <p style={{ margin: "0 0 11.2px", fontSize: 12, color: TEXT.muted, maxWidth: "64ch", lineHeight: 1.5 }}>
        {t("candidaturas.faltam.explicacao")}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
        {pendentes.map((item) => (
          <label key={item.chave} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 12.5, color: TEXT.full }}>
              {item.pergunta}
              {item.motivo === "sensivel" ? (
                <span style={{ color: C.ambar, fontSize: 11.5 }}> · {t("candidaturas.faltam.sensivel")}</span>
              ) : null}
            </span>
            <input
              className="input"
              value={digitadas[item.chave] ?? ""}
              onChange={(evento) => setDigitadas((atuais) => ({ ...atuais, [item.chave]: evento.target.value }))}
            />
          </label>
        ))}
      </div>
      <button
        type="button"
        className="btn btn-secondary"
        style={{ marginTop: 11.2 }}
        disabled={salvando || preenchidas.length === 0}
        onClick={() => aoSalvar(preenchidas)}
      >
        <Icon name="check" size={15} />
        {salvando ? t("candidaturas.faltam.salvando") : t("candidaturas.faltam.salvar")}
      </button>
    </div>
  );
}

/**
 * O envio sem confirmação, e o que ele precisa saber sobre você.
 *
 * Desligado por padrão de propósito: candidatura é uma ação em seu nome, e
 * ninguém deve descobrir depois do fato que ela aconteceu. Ligado, o app envia
 * sozinho de manhã as vagas que trazem e-mail de contato no anúncio e combinam
 * acima do corte — e o e-mail do dia diz o que saiu.
 */
function EnvioAutomatico() {
  const perfil = useQuery(() => profileApi.get(), []);
  const salvar = useMutation((corpo: Parameters<typeof profileApi.update>[0]) => profileApi.update(corpo));

  const [pretensao, setPretensao] = useState("");
  const [disponibilidade, setDisponibilidade] = useState("");
  const [salvo, setSalvo] = useState(false);

  const ligado = Boolean(perfil.data?.notifications?.candidatura_automatica);

  useEffect(() => {
    if (!perfil.data) return;
    setPretensao(perfil.data.salary_expectation ?? "");
    setDisponibilidade(perfil.data.availability ?? "");
  }, [perfil.data]);

  async function alternar() {
    const atualizado = await salvar.run({
      notifications: { ...(perfil.data?.notifications ?? {}), candidatura_automatica: !ligado },
    });
    if (atualizado) perfil.reload();
  }

  async function salvarRespostas() {
    setSalvo(false);
    const atualizado = await salvar.run({
      salary_expectation: pretensao.trim(),
      availability: disponibilidade.trim(),
    });
    if (atualizado) {
      setSalvo(true);
      perfil.reload();
    }
  }

  if (!perfil.data) return null;

  return (
    <Panel pad={16.8}>
      <div style={{ display: "flex", gap: 11.2, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 260 }}>
          <Kicker style={{ display: "block", marginBottom: 4 }}>Envio automático</Kicker>
          <p style={{ margin: 0, fontSize: 13, color: TEXT.muted, lineHeight: 1.55, maxWidth: "62ch" }}>
            {ligado
              ? "Ligado: todo dia de manhã o app envia seu currículo, sozinho, para as vagas que trazem e-mail de contato e combinam 70% ou mais — até 5 por dia. Você recebe um e-mail com o que foi enviado."
              : "Desligado: o app separa as vagas e escreve a carta, e você clica para enviar. Ligando, ele envia sozinho as vagas que trazem e-mail de contato e combinam 70% ou mais, até 5 por dia."}
          </p>
          <p style={{ margin: "6px 0 0", fontSize: 11.5, color: TEXT.faint, lineHeight: 1.5, maxWidth: "62ch" }}>
            Vaga que só aceita candidatura pelo site (Gupy, LinkedIn, formulário próprio) continua vindo com o
            link e as respostas prontas: lá quem responde é você.
          </p>
        </div>
        <button
          type="button"
          className={ligado ? "btn btn-secondary" : "btn btn-primary"}
          aria-pressed={ligado}
          disabled={salvar.pending}
          onClick={() => void alternar()}
        >
          <Icon name={ligado ? "check" : "send"} size={15} />
          {ligado ? "Enviando sozinho" : "Enviar sozinho todo dia"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 11.2, flexWrap: "wrap", alignItems: "flex-end", marginTop: 14 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1, minWidth: 200 }}>
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>Pretensão salarial</span>
          <input
            className="input"
            value={pretensao}
            maxLength={120}
            placeholder="R$ 8.000 CLT"
            onChange={(evento) => setPretensao(evento.target.value)}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1, minWidth: 200 }}>
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>Disponibilidade para começar</span>
          <input
            className="input"
            value={disponibilidade}
            maxLength={120}
            placeholder="30 dias"
            onChange={(evento) => setDisponibilidade(evento.target.value)}
          />
        </label>
        <button type="button" className="btn btn-ghost" disabled={salvar.pending} onClick={() => void salvarRespostas()}>
          {salvar.pending ? "Salvando…" : salvo ? "Salvo" : "Salvar"}
        </button>
      </div>
      <p style={{ fontSize: 11, color: TEXT.faint, margin: "8.4px 0 0" }}>
        São as duas perguntas que todo formulário faz e que o currículo não responde. Sem elas, a resposta
        pronta devolve a pergunta em vez de inventar um número.
      </p>
      {salvar.error ? <ErrorState message={salvar.error} /> : null}
    </Panel>
  );
}

/** Uma vaga da fila: a carta, o envio e o link para responder no site. */
function Cartao({
  item,
  onMudou,
  onErro,
}: {
  item: Candidatura;
  onMudou: () => void;
  onErro: (mensagem: string | null) => void;
}) {
  const t = useT();
  const [carta, setCarta] = useState(item.letter ?? "");
  const [email, setEmail] = useState(item.to_email ?? "");
  const [aberta, setAberta] = useState(false);
  const [respostas, setRespostas] = useState(item.answers ?? []);
  const [copiada, setCopiada] = useState<string | null>(null);

  const [passos, setPassos] = useState<PassoDaCandidatura[]>(item.steps ?? []);
  const [pendentes, setPendentes] = useState<PerguntaPendente[]>(item.pending ?? []);

  const escrever = useMutation(() => candidaturasApi.carta(item.id));
  const prepararRespostas = useMutation(() => candidaturasApi.respostas(item.id));
  const rodar = useMutation((enviar: boolean) => candidaturasApi.preparar(item.id, enviar));
  const guardar = useMutation((respostas: { pergunta: string; chave: string; resposta: string }[]) =>
    candidaturasApi.guardarRespostas(respostas),
  );

  /** Roda a candidatura e vai mostrando cada passo. `enviar` manda de verdade. */
  async function executar(enviar: boolean) {
    onErro(null);
    setPassos([]);
    const resposta = await rodar.run(enviar);
    if (!resposta) {
      if (rodar.error) onErro(rodar.error);
      return;
    }
    setPassos(resposta.steps ?? []);
    setPendentes(resposta.pending ?? []);
    setRespostas(resposta.answers ?? []);
    if (resposta.letter) setCarta(resposta.letter);
    onMudou();
  }
  const enviar = useMutation((corpo: { email?: string; carta?: string }) => candidaturasApi.enviar(item.id, corpo));
  const descartar = useMutation(() => candidaturasApi.descartar(item.id));

  const enviada = item.status === "enviada";
  const descartada = item.status === "descartada";

  async function escreverCarta() {
    onErro(null);
    const resposta = await escrever.run();
    if (resposta) {
      setCarta(resposta.letter ?? "");
      setAberta(true);
      onMudou();
    } else if (escrever.error) {
      onErro(escrever.error);
    }
  }

  async function enviarAgora(comEmail: boolean) {
    onErro(null);
    const resposta = await enviar.run(
      comEmail ? { email: email.trim(), carta: carta.trim() || undefined } : {},
    );
    if (resposta) onMudou();
    else if (enviar.error) onErro(enviar.error);
  }

  return (
    <Panel pad={16.8}>
      <div style={{ display: "flex", gap: 11.2, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 240 }}>
          <h2 style={{ fontSize: 16, fontWeight: 500, margin: 0, color: descartada ? TEXT.faint : TEXT.full }}>
            {item.title}
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 12.5, color: TEXT.muted }}>
            {item.company}
            {item.location ? ` · ${item.location}` : ""}
            {item.remote ? " · Remota" : ""}
          </p>
        </div>
        <span
          className="tag tag-outline"
          title="O quanto esta vaga combina com o seu perfil"
          style={{ color: item.score >= 70 ? ACC4 : TEXT.muted }}
        >
          {item.score}% combina
        </span>
        {enviada ? (
          <span className="tag" style={{ color: C.verde }}>
            <Icon name="check" size={13} /> Enviada
          </span>
        ) : null}
      </div>

      {item.snippet && !descartada ? (
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "11.2px 0 0", lineHeight: 1.55 }}>
          {item.snippet.slice(0, 260)}
          {item.snippet.length > 260 ? "…" : ""}
        </p>
      ) : null}

      {!descartada ? (
        <div style={{ display: "flex", gap: 8.4, flexWrap: "wrap", marginTop: 14 }}>
          {/* O link da vaga vem sempre: é por ele que se respondem as perguntas
              do formulário da empresa, que é o caminho da maioria das vagas. */}
          <a
            className="btn btn-primary"
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ textDecoration: "none" }}
          >
            <Icon name="externalLink" size={15} />
            {t("candidaturas.abrirVaga")}
          </a>

          {/* O envio de verdade: prepara tudo e, quando a vaga tem e-mail de
              contato, manda o currículo nesta hora. A linha do tempo abaixo
              mostra cada passo enquanto acontece. */}
          {!enviada ? (
            <button
              type="button"
              className="btn btn-primary"
              disabled={rodar.pending}
              onClick={() => void executar(true)}
            >
              <Icon name="send" size={15} />
              {rodar.pending ? t("candidaturas.enviando") : t("candidaturas.enviarAgora")}
            </button>
          ) : null}

          <button type="button" className="btn btn-ghost" disabled={rodar.pending} onClick={() => void executar(false)}>
            <Icon name="refresh" size={15} />
            {t("candidaturas.prepararSemEnviar")}
          </button>

          <button type="button" className="btn btn-secondary" disabled={escrever.pending} onClick={() => void escreverCarta()}>
            <Icon name="pencil" size={15} />
            {escrever.pending ? "Escrevendo…" : carta ? "Reescrever carta" : "Escrever carta"}
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            disabled={prepararRespostas.pending}
            onClick={async () => {
              onErro(null);
              const resposta = await prepararRespostas.run();
              if (resposta) setRespostas(resposta.answers ?? []);
              else if (prepararRespostas.error) onErro(prepararRespostas.error);
            }}
          >
            <Icon name="chat" size={15} />
            {prepararRespostas.pending
              ? "Escrevendo…"
              : respostas.length > 0
                ? "Refazer respostas"
                : "Respostas do formulário"}
          </button>

          {carta ? (
            <button type="button" className="btn btn-ghost" onClick={() => setAberta((valor) => !valor)}>
              <Icon name={aberta ? "eyeOff" : "eye"} size={15} />
              {aberta ? "Esconder carta" : "Ver carta"}
            </button>
          ) : null}

          {!enviada ? (
            <button type="button" className="btn btn-ghost" disabled={enviar.pending} onClick={() => void enviarAgora(false)}>
              <Icon name="check" size={15} />
              Já me candidatei
            </button>
          ) : null}

          <button
            type="button"
            className="btn btn-ghost"
            style={{ marginLeft: "auto", color: C.ambar }}
            disabled={descartar.pending}
            onClick={async () => {
              await descartar.run();
              onMudou();
            }}
          >
            <Icon name="trash" size={15} />
            Não me interessa
          </button>
        </div>
      ) : (
        <p style={{ fontSize: 12.5, color: TEXT.faint, margin: "11.2px 0 0" }}>
          Descartada — esta vaga não volta para a sua fila.
        </p>
      )}

      {aberta && carta ? (
        <div style={{ marginTop: 14, borderTop: `1px solid ${HAIRLINE}`, paddingTop: 14 }}>
          <label style={{ display: "block", fontSize: 11.5, color: TEXT.faint, marginBottom: 4 }} htmlFor={`carta-${item.id}`}>
            Carta de apresentação (você pode editar antes de enviar)
          </label>
          <textarea
            id={`carta-${item.id}`}
            className="input"
            rows={9}
            value={carta}
            onChange={(evento) => setCarta(evento.target.value)}
            style={{ width: "100%", fontSize: 13.5, lineHeight: 1.6, resize: "vertical" }}
          />

          {!enviada ? (
            <div style={{ display: "flex", gap: 8.4, flexWrap: "wrap", alignItems: "flex-end", marginTop: 11.2 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1, minWidth: 220 }}>
                <span style={{ fontSize: 11.5, color: TEXT.faint }}>
                  E-mail da empresa (quando o anúncio tiver um)
                </span>
                <input
                  className="input"
                  type="email"
                  value={email}
                  placeholder="vagas@empresa.com"
                  onChange={(evento) => setEmail(evento.target.value)}
                />
              </label>
              <button
                type="button"
                className="btn btn-primary"
                disabled={enviar.pending || !email.includes("@")}
                onClick={() => void enviarAgora(true)}
              >
                <Icon name="send" size={15} />
                {enviar.pending ? "Enviando…" : "Enviar com meu currículo"}
              </button>
            </div>
          ) : null}

          <p style={{ fontSize: 11, color: TEXT.faint, margin: "11.2px 0 0", lineHeight: 1.5 }}>
            O e-mail sai pelo PathR, mas a resposta da empresa vai direto para o seu endereço. Seu currículo
            vai em anexo, do jeito que você enviou.
          </p>
        </div>
      ) : null}

      {respostas.length > 0 ? (
        <div style={{ marginTop: 14, borderTop: `1px solid ${HAIRLINE}`, paddingTop: 14 }}>
          <Kicker style={{ display: "block", marginBottom: 8.4 }}>Respostas para o formulário da vaga</Kicker>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 11.2 }}>
            {respostas.map((item_) => (
              <li key={item_.pergunta}>
                <div style={{ display: "flex", gap: 8.4, alignItems: "baseline", flexWrap: "wrap" }}>
                  <strong style={{ fontSize: 12.5, fontWeight: 500, color: ACC4 }}>{item_.pergunta}</strong>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    style={{ marginLeft: "auto", fontSize: 11.5, padding: "2px 8px" }}
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(item_.resposta);
                        setCopiada(item_.pergunta);
                      } catch {
                        // Sem permissão da área de transferência: o texto está
                        // à vista para selecionar e copiar à mão.
                        setCopiada(null);
                      }
                    }}
                  >
                    {copiada === item_.pergunta ? "Copiado" : "Copiar"}
                  </button>
                </div>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "rgba(233,233,237,.85)", lineHeight: 1.55 }}>
                  {item_.resposta}
                </p>
              </li>
            ))}
          </ul>
          <p style={{ fontSize: 11, color: TEXT.faint, margin: "11.2px 0 0", lineHeight: 1.5 }}>
            Confira antes de colar: quem responde ao recrutador é você, e o formulário pode perguntar outra coisa.
          </p>
        </div>
      ) : null}

      {(passos.length > 0 || rodar.pending) && !descartada ? (
        <LinhaDoTempo passos={passos} rodando={rodar.pending} />
      ) : null}

      <PerguntasQueFaltam
        pendentes={pendentes}
        salvando={guardar.pending}
        aoSalvar={async (respostas) => {
          onErro(null);
          const guardadas = await guardar.run(respostas);
          if (!guardadas) {
            if (guardar.error) onErro(guardar.error);
            return;
          }
          // Guardadas: rodar de novo já aproveita as respostas novas, e as
          // que sobrarem continuam aparecendo aqui.
          await executar(false);
        }}
      />

      {enviada && item.sent_at ? (
        <p style={{ fontSize: 11.5, color: TEXT.faint, margin: "11.2px 0 0" }}>
          Enviada em {new Date(item.sent_at).toLocaleDateString("pt-BR")}
          {item.to_email ? ` para ${item.to_email}` : " (pelo site da vaga)"}.
        </p>
      ) : null}
    </Panel>
  );
}
