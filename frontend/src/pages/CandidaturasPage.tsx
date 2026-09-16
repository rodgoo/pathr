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

import { useMemo, useState } from "react";
import { candidaturas as candidaturasApi, resumes as resumesApi } from "@/api/endpoints";
import type { Candidatura } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useMutation, useQuery } from "@/hooks/useApi";
import { ACC4, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";

export function CandidaturasPage() {
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
        <Kicker style={{ display: "block", marginBottom: 5.6 }}>Candidaturas</Kicker>
        <h1 style={{ fontSize: 23, fontWeight: 500, margin: 0 }}>Seu currículo indo para as vagas certas</h1>
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

      {temCurriculo ? (
        <Panel pad={16.8}>
          <div style={{ display: "flex", gap: 11.2, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ flex: 1, minWidth: 220 }}>
              <Kicker style={{ display: "block", marginBottom: 4 }}>Hoje</Kicker>
              <p style={{ margin: 0, fontSize: 13.5, color: TEXT.full }}>
                {hoje.length > 0
                  ? `${hoje.length} ${hoje.length === 1 ? "vaga separada" : "vagas separadas"} para você`
                  : "Nenhuma vaga nova hoje ainda."}
                {fila.data?.enviadas ? (
                  <span style={{ color: TEXT.faint }}> · {fila.data.enviadas} enviadas no período</span>
                ) : null}
              </p>
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
  const [carta, setCarta] = useState(item.letter ?? "");
  const [email, setEmail] = useState(item.to_email ?? "");
  const [aberta, setAberta] = useState(false);

  const escrever = useMutation(() => candidaturasApi.carta(item.id));
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
            Abrir vaga e responder
          </a>

          <button type="button" className="btn btn-secondary" disabled={escrever.pending} onClick={() => void escreverCarta()}>
            <Icon name="pencil" size={15} />
            {escrever.pending ? "Escrevendo…" : carta ? "Reescrever carta" : "Escrever carta"}
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

      {enviada && item.sent_at ? (
        <p style={{ fontSize: 11.5, color: TEXT.faint, margin: "11.2px 0 0" }}>
          Enviada em {new Date(item.sent_at).toLocaleDateString("pt-BR")}
          {item.to_email ? ` para ${item.to_email}` : " (pelo site da vaga)"}.
        </p>
      ) : null}
    </Panel>
  );
}
