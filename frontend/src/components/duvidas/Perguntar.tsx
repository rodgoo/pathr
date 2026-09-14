/**
 * "Perguntar": a dúvida rápida sobre o que está na tela.
 *
 * A pessoa escreve do lado esquerdo, o tutor responde do lado direito, e toda
 * explicação termina perguntando se ficou claro — com os botões "Sim, entendi"
 * e "Ainda não" logo embaixo. "Ainda não" traz outra explicação, de outro
 * jeito.
 *
 * Aqui não se gera exercício. O que foi perguntado vai para a base de
 * conhecimento da conta, e a Trilha atual transforma isso em atividade, quiz e
 * busca de material depois (backend: services/conhecimento.py).
 *
 * O CONTEXTO não vai daqui: a tela diz só onde a pessoa está (tipo + id), e o
 * servidor lê o conteúdo conferindo que é dela. O `trecho` (o passo, a linha)
 * é o único texto de contexto que sai do cliente.
 *
 * A resposta do tutor sai formatada (parágrafos, listas, negrito, código) por
 * `TextoFormatado`, que monta elementos React e nunca HTML.
 */

import { useEffect, useRef, useState } from "react";
import { duvidas as duvidasApi } from "@/api/endpoints";
import type { DuvidaConversa, TipoDeContextoDaDuvida } from "@/api/types";
import { ACC, ACC4, C, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { ProgressoDaTarefa } from "@/components/ui/ProgressoDaTarefa";
import { TextoFormatado } from "./TextoFormatado";
import { useAppStateOpcional } from "@/hooks/useAppState";
import { abrirExemploNoLaboratorio } from "@/lib/laboratorio";

interface Props {
  contextoTipo: TipoDeContextoDaDuvida;
  contextoRef?: string;
  /** O que a pessoa está vendo agora (o passo do exemplo, a linha). */
  trecho?: string;
  /** Rótulo do botão; o padrão é "Perguntar". */
  rotulo?: string;
}

const ETAPAS = ["Lendo o conteúdo", "Pensando num exemplo", "Escrevendo a explicação"] as const;

function mensagemDeErro(erro: unknown): string {
  return erro instanceof Error ? erro.message : "Não consegui falar com o tutor agora.";
}

export function Perguntar({ contextoTipo, contextoRef, trecho, rotulo = "Perguntar" }: Props) {
  const [aberto, setAberto] = useState(false);
  const [conversa, setConversa] = useState<DuvidaConversa | null>(null);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const fim = useRef<HTMLDivElement>(null);
  const app = useAppStateOpcional();
  const [gerandoExemplo, setGerandoExemplo] = useState(false);

  function abrirNoDepurador(id: string) {
    abrirExemploNoLaboratorio(id);
    app?.dispatch({ type: "navigate", screen: "codigo" });
  }

  // Ao abrir: a última conversa deste contexto volta, para não sumir ao reabrir a tela.
  useEffect(() => {
    if (!aberto) return;
    let vivo = true;
    void duvidasApi
      .listar(contextoTipo, contextoRef)
      .then((lista) => {
        if (vivo && lista.length) setConversa(lista[0]);
      })
      .catch(() => undefined);
    return () => {
      vivo = false;
    };
  }, [aberto, contextoTipo, contextoRef]);

  useEffect(() => {
    fim.current?.scrollIntoView?.({ block: "nearest" });
  }, [conversa?.mensagens.length, enviando]);

  async function gerarExemplo(pedido: { linguagem: string; topico: string }) {
    if (!conversa) return;
    setGerandoExemplo(true);
    setErro(null);
    try {
      setConversa(await duvidasApi.exemplo(conversa.id, pedido));
    } catch (caught) {
      setErro(mensagemDeErro(caught));
    } finally {
      setGerandoExemplo(false);
    }
  }

  async function executar(acao: () => Promise<DuvidaConversa>) {
    setEnviando(true);
    setErro(null);
    try {
      setConversa(await acao());
    } catch (caught) {
      setErro(mensagemDeErro(caught));
    } finally {
      setEnviando(false);
    }
  }

  async function enviar() {
    const pergunta = texto.trim();
    if (pergunta.length < 3) return;
    setTexto("");
    const aindaAberta = conversa && conversa.status === "aberta";
    await executar(() =>
      aindaAberta
        ? duvidasApi.continuar(conversa.id, pergunta)
        : duvidasApi.abrir({ contexto_tipo: contextoTipo, contexto_ref: contextoRef, trecho, pergunta }),
    );
  }

  if (!aberto) {
    return (
      <button type="button" className="btn btn-secondary" style={{ fontSize: 12.5 }} onClick={() => setAberto(true)}>
        <Icon name="chat" size={15} />
        {rotulo}
      </button>
    );
  }

  const mensagens = conversa?.mensagens ?? [];
  const ultima = mensagens[mensagens.length - 1];
  const esperandoRetorno = Boolean(conversa && conversa.status === "aberta" && ultima?.papel === "tutor" && !enviando);

  return (
    <section
      aria-label="Perguntar ao tutor"
      style={{
        marginTop: 11.2,
        padding: 12.6,
        borderRadius: 10,
        background: "#0c0c10",
        boxShadow: `inset 0 0 0 1px ${tint(ACC, 30)}`,
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8.4, flexWrap: "wrap" }}>
        <Icon name="chat" size={15} style={{ color: ACC4 }} />
        <strong style={{ fontSize: 13, fontWeight: 500, color: TEXT.full }}>Tirar uma dúvida</strong>
        <span style={{ fontSize: 11.5, color: TEXT.faint }}>fica guardada para revisar depois</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
          {conversa ? (
            <button type="button" className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => setConversa(null)}>
              Nova dúvida
            </button>
          ) : null}
          <button type="button" className="btn btn-ghost" style={{ fontSize: 12 }} aria-label="Fechar" onClick={() => setAberto(false)}>
            <Icon name="x" size={14} />
          </button>
        </span>
      </div>

      {mensagens.length === 0 && !enviando ? (
        <p style={{ margin: 0, fontSize: 12.5, color: TEXT.muted }}>
          Não entendeu alguma parte? Pergunte do seu jeito — o tutor explica com base no que está nesta tela.
        </p>
      ) : null}

      <ol aria-label="Conversa" style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8.4 }}>
        {mensagens.map((mensagem) => {
          const daPessoa = mensagem.papel === "pessoa";
          return (
            <li
              key={mensagem.id}
              aria-label={daPessoa ? "Você" : "Tutor"}
              style={{ display: "flex", justifyContent: daPessoa ? "flex-start" : "flex-end" }}
            >
              <div
                style={{
                  maxWidth: "85%",
                  padding: "8.4px 11.2px",
                  borderRadius: daPessoa ? "10px 10px 10px 3px" : "10px 10px 3px 10px",
                  background: daPessoa ? "rgba(233,233,237,.07)" : tint(ACC, 14),
                  color: daPessoa ? TEXT.strong : TEXT.full,
                  fontSize: 13,
                  lineHeight: 1.55,
                  overflowWrap: "anywhere",
                }}
              >
                {daPessoa ? <span style={{ whiteSpace: "pre-wrap" }}>{mensagem.texto}</span> : <TextoFormatado texto={mensagem.texto} />}
                {!daPessoa && mensagem.exemplo_id ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ fontSize: 12.5, marginTop: 6 }}
                    onClick={() => abrirNoDepurador(mensagem.exemplo_id as string)}
                  >
                    <Icon name="code" size={14} />
                    Abrir no depurador
                  </button>
                ) : null}
                {!daPessoa && (mensagem.sugestoes ?? []).length > 0 ? (
                  <div
                    role="group"
                    aria-label="Exemplos para depurar"
                    style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8, paddingTop: 8, borderTop: "1px solid rgba(233,233,237,.1)" }}
                  >
                    <span style={{ fontSize: 11.5, color: TEXT.muted, width: "100%" }}>Quer ver rodando, passo a passo?</span>
                    {(mensagem.sugestoes ?? []).map((sugestao) => (
                      <button
                        key={`${sugestao.linguagem}-${sugestao.topico}`}
                        type="button"
                        className="btn btn-secondary"
                        style={{ fontSize: 12 }}
                        disabled={gerandoExemplo || enviando}
                        onClick={() => void gerarExemplo(sugestao)}
                      >
                        <Icon name="code" size={13} />
                        Gerar exemplo para depurar: {sugestao.topico}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>

      <ProgressoDaTarefa ativo={enviando} chave="tutor-responder" etapas={ETAPAS} duracaoMs={9_000} />
      <ProgressoDaTarefa
        ativo={gerandoExemplo}
        chave="tutor-exemplo"
        etapas={["Escrevendo o código", "Montando o passo a passo", "Conferindo cada passo com o código"]}
        duracaoMs={25_000}
      />

      {esperandoRetorno && conversa ? (
        <div role="group" aria-label="A explicação ficou clara?" style={{ display: "flex", gap: 8.4, justifyContent: "flex-end", flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ fontSize: 12.5, color: C.verde }}
            onClick={() => void executar(() => duvidasApi.entendeu(conversa.id, true))}
          >
            <Icon name="check" size={14} />
            Sim, entendi
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            style={{ fontSize: 12.5 }}
            onClick={() => void executar(() => duvidasApi.entendeu(conversa.id, false))}
          >
            Ainda não
          </button>
        </div>
      ) : null}

      {erro ? (
        <div role="alert" style={{ fontSize: 12.5, color: C.ambar }}>
          {erro}
        </div>
      ) : null}

      <form
        onSubmit={(evento) => {
          evento.preventDefault();
          void enviar();
        }}
        // Um compositor só: o campo e o botão de enviar dentro da mesma moldura,
        // como num app de mensagens. O botão é só o ícone — o nome "Enviar"
        // continua para leitor de tela, no aria-label.
        className="compositor"
      >
        <textarea
          className="input"
          aria-label="Sua dúvida"
          rows={2}
          maxLength={2000}
          placeholder={conversa?.status === "aberta" ? "Pergunte mais sobre isso…" : "Escreva sua dúvida…"}
          value={texto}
          onChange={(evento) => setTexto(evento.target.value)}
          onKeyDown={(evento) => {
            if (evento.key === "Enter" && !evento.shiftKey) {
              evento.preventDefault();
              void enviar();
            }
          }}
        />
        <button
          type="submit"
          className="compositor__enviar"
          aria-label="Enviar"
          title="Enviar (Enter)"
          disabled={enviando || texto.trim().length < 3}
        >
          <Icon name="send" size={16} />
        </button>
      </form>
      <div ref={fim} />
    </section>
  );
}
