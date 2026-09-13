/**
 * Configurações › Relatar: reclamação ou sugestão, com foto se ajudar.
 *
 * A pessoa vê o que já relatou e em que pé está — "em análise", "resolvido",
 * com a resposta de quem moderou. Um formulário que engole a mensagem sem
 * retorno ensina a não relatar de novo.
 *
 * Mora na barra lateral, ao alcance de qualquer tela: quem esbarra num
 * problema não deveria precisar lembrar que o caminho passa por
 * Configurações. A moderação dos relatos fica em Configurações, e só para
 * quem modera (ver ModeracaoRelatos).
 */

import { useState, type FormEvent } from "react";
import { relatos } from "@/api/endpoints";
import type { Relato, TipoRelato } from "@/api/types";
import { useQuery } from "@/hooks/useApi";
import { C, TEXT } from "@/lib/tokens";
import { Segmented } from "@/components/ui/Segmented";
import { Kicker, Panel } from "@/components/ui/primitives";
import { MidiaAnexada } from "./MidiaAnexada";

const TIPOS: readonly { value: TipoRelato; label: string }[] = [
  { value: "reclamacao", label: "Reclamação" },
  { value: "sugestao", label: "Sugestão" },
];

export const ROTULO_STATUS: Record<Relato["status"], { texto: string; cor: string }> = {
  aberto: { texto: "Recebido", cor: TEXT.muted },
  em_analise: { texto: "Em análise", cor: C.ambar },
  resolvido: { texto: "Resolvido", cor: C.verde },
};

/** O mesmo teto do servidor; conferido aqui para a pessoa não esperar o envio falhar. */
const FOTO_MAX_MB = 5;
const ACEITOS = ["image/jpeg", "image/png", "image/webp"];

export function RelatarTab() {
  const meus = useQuery(() => relatos.meus(), []);
  const [tipo, setTipo] = useState<TipoRelato>("reclamacao");
  const [mensagem, setMensagem] = useState("");
  const [foto, setFoto] = useState<File | null>(null);
  const [previa, setPrevia] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  function escolherFoto(arquivo: File | null) {
    setErro(null);
    if (previa) URL.revokeObjectURL(previa);
    if (!arquivo) {
      setFoto(null);
      setPrevia(null);
      return;
    }
    if (!ACEITOS.includes(arquivo.type)) {
      setErro("A foto precisa ser JPG, PNG ou WebP.");
      return;
    }
    if (arquivo.size > FOTO_MAX_MB * 1024 * 1024) {
      setErro(`A foto passa de ${FOTO_MAX_MB} MB.`);
      return;
    }
    setFoto(arquivo);
    setPrevia(URL.createObjectURL(arquivo));
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    if (mensagem.trim().length < 10) {
      setErro("Conte um pouco mais: ao menos 10 caracteres.");
      return;
    }
    setEnviando(true);
    setErro(null);
    setAviso(null);
    try {
      const criado = await relatos.enviar({ tipo, mensagem: mensagem.trim(), pagina: "config", foto });
      setMensagem("");
      escolherFoto(null);
      setAviso(criado.aviso ?? "Relato enviado. Obrigado — ele já está com a moderação.");
      meus.reload();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : "Não consegui enviar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <Panel pad={16.8}>
        <Kicker style={{ display: "block", marginBottom: 4 }}>Relatar</Kicker>
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 14px", maxWidth: "62ch" }}>
          Algo não funcionou ou poderia ser melhor? Conte aqui. Uma captura de tela ajuda a entender
          o que você viu.
        </p>

        <form onSubmit={enviar} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Segmented name="relato-tipo" label="Tipo de relato" value={tipo} options={TIPOS} onChange={setTipo} />

          <div className="field" style={{ margin: 0 }}>
            <label htmlFor="relato-mensagem">
              {tipo === "reclamacao" ? "O que aconteceu?" : "O que você sugere?"}
            </label>
            <textarea
              id="relato-mensagem"
              className="input"
              maxLength={3000}
              rows={5}
              value={mensagem}
              placeholder={
                tipo === "reclamacao"
                  ? "ex: ao salvar o objetivo, a tela voltou para o início e perdi o que tinha escrito"
                  : "ex: poder exportar o plano da semana em PDF"
              }
              onChange={(evento) => setMensagem(evento.target.value)}
            />
            <div style={{ fontSize: 11, color: TEXT.faint, marginTop: 4, textAlign: "right" }}>
              {mensagem.length}/3000
            </div>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 11.2, alignItems: "center" }}>
            <label className="btn btn-secondary" style={{ cursor: "pointer", position: "relative" }}>
              {foto ? "Trocar foto" : "Anexar foto"}
              <input
                type="file"
                accept={ACEITOS.join(",")}
                aria-label="Anexar foto"
                style={{ position: "absolute", inset: 0, opacity: 0, cursor: "pointer" }}
                onChange={(evento) => escolherFoto(evento.target.files?.[0] ?? null)}
              />
            </label>
            {previa ? (
              <span style={{ display: "flex", alignItems: "center", gap: 8.4 }}>
                <img src={previa} alt="Prévia da foto anexada" style={{ width: 56, height: 56, objectFit: "cover", borderRadius: 8 }} />
                <button type="button" className="btn btn-ghost" style={{ fontSize: 12.5 }} onClick={() => escolherFoto(null)}>
                  Remover
                </button>
              </span>
            ) : (
              <span style={{ fontSize: 11.5, color: TEXT.faint }}>
                Opcional · JPG, PNG ou WebP até {FOTO_MAX_MB} MB
              </span>
            )}
          </div>

          {erro ? <p role="alert" style={{ margin: 0, fontSize: 12.5, color: C.ambar }}>{erro}</p> : null}
          {aviso ? <p role="status" style={{ margin: 0, fontSize: 12.5, color: C.verde }}>{aviso}</p> : null}

          <div>
            <button type="submit" className="btn btn-primary" disabled={enviando}>
              {enviando ? "Enviando…" : "Enviar relato"}
            </button>
          </div>
        </form>
      </Panel>

      {meus.data && meus.data.length > 0 ? (
        <Panel pad={16.8}>
          <Kicker style={{ display: "block", marginBottom: 11.2 }}>Seus relatos</Kicker>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8.4 }}>
            {meus.data.map((relato) => (
              <li key={relato.id} style={{ padding: "10px 12px", borderRadius: 8, background: "#0c0c10" }}>
                <div style={{ display: "flex", gap: 8.4, alignItems: "baseline", flexWrap: "wrap" }}>
                  <span style={{ fontSize: 12, color: TEXT.faint }}>
                    {relato.kind === "reclamacao" ? "Reclamação" : "Sugestão"} ·{" "}
                    {new Date(relato.created_at).toLocaleDateString("pt-BR")}
                  </span>
                  <span style={{ marginLeft: "auto", fontSize: 12, color: ROTULO_STATUS[relato.status].cor }}>
                    {ROTULO_STATUS[relato.status].texto}
                  </span>
                </div>
                {/* Texto puro, nunca HTML: o React escapa, e nada aqui vira link. */}
                <p style={{ margin: "4px 0 0", fontSize: 13.5, whiteSpace: "pre-wrap" }}>{relato.message}</p>
                {relato.has_attachment ? (
                  <div style={{ marginTop: 6 }}>
                    <MidiaAnexada relatoId={relato.id} />
                  </div>
                ) : null}
                {relato.moderator_note ? (
                  <p style={{ margin: "6px 0 0", fontSize: 12.5, color: TEXT.muted }}>
                    <strong style={{ fontWeight: 500 }}>Resposta:</strong> {relato.moderator_note}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}
    </div>
  );
}
