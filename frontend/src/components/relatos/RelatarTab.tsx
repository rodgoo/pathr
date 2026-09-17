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
import { useIdioma, useT } from "@/lib/i18n";
import { C, TEXT } from "@/lib/tokens";
import { Segmented } from "@/components/ui/Segmented";
import { Kicker, Panel } from "@/components/ui/primitives";
import { MidiaAnexada } from "./MidiaAnexada";

/** O rótulo de cada status guarda a CHAVE de tradução (traduzida no render) e a
 * cor, que não muda com o idioma. */
export const ROTULO_STATUS: Record<Relato["status"], { chave: string; cor: string }> = {
  aberto: { chave: "relatar.status.recebido", cor: TEXT.muted },
  em_analise: { chave: "relatar.status.emAnalise", cor: C.ambar },
  resolvido: { chave: "relatar.status.resolvido", cor: C.verde },
};

/** O mesmo teto do servidor; conferido aqui para a pessoa não esperar o envio falhar. */
const FOTO_MAX_MB = 5;
const ACEITOS = ["image/jpeg", "image/png", "image/webp"];

export function RelatarTab() {
  const t = useT();
  const { idioma } = useIdioma();
  const TIPOS: readonly { value: TipoRelato; label: string }[] = [
    { value: "reclamacao", label: t("relatar.tipo.reclamacao") },
    { value: "sugestao", label: t("relatar.tipo.sugestao") },
  ];
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
      setErro(t("relatar.erro.formatoFoto"));
      return;
    }
    if (arquivo.size > FOTO_MAX_MB * 1024 * 1024) {
      setErro(t("relatar.erro.fotoGrande", { mb: FOTO_MAX_MB }));
      return;
    }
    setFoto(arquivo);
    setPrevia(URL.createObjectURL(arquivo));
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    if (mensagem.trim().length < 10) {
      setErro(t("relatar.erro.curto"));
      return;
    }
    setEnviando(true);
    setErro(null);
    setAviso(null);
    try {
      const criado = await relatos.enviar({ tipo, mensagem: mensagem.trim(), pagina: "config", foto });
      setMensagem("");
      escolherFoto(null);
      setAviso(criado.aviso ?? t("relatar.aviso.enviado"));
      meus.reload();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : t("relatar.erro.envioFalhou"));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <Panel pad={16.8}>
        <Kicker style={{ display: "block", marginBottom: 4 }}>{t("relatar.titulo")}</Kicker>
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 14px", maxWidth: "62ch" }}>
          {t("relatar.form.intro")}
        </p>

        <form onSubmit={enviar} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Segmented name="relato-tipo" label={t("relatar.form.tipoLabel")} value={tipo} options={TIPOS} onChange={setTipo} />

          <div className="field" style={{ margin: 0 }}>
            <label htmlFor="relato-mensagem">
              {tipo === "reclamacao" ? t("relatar.form.oQueAconteceu") : t("relatar.form.oQueSugere")}
            </label>
            <textarea
              id="relato-mensagem"
              className="input"
              maxLength={3000}
              rows={5}
              value={mensagem}
              placeholder={
                tipo === "reclamacao"
                  ? t("relatar.form.placeholderReclamacao")
                  : t("relatar.form.placeholderSugestao")
              }
              onChange={(evento) => setMensagem(evento.target.value)}
            />
            <div style={{ fontSize: 11, color: TEXT.faint, marginTop: 4, textAlign: "right" }}>
              {mensagem.length}/3000
            </div>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 11.2, alignItems: "center" }}>
            <label className="btn btn-secondary" style={{ cursor: "pointer", position: "relative" }}>
              {foto ? t("relatar.form.trocarFoto") : t("relatar.form.anexarFoto")}
              <input
                type="file"
                accept={ACEITOS.join(",")}
                aria-label={t("relatar.form.anexarFoto")}
                style={{ position: "absolute", inset: 0, opacity: 0, cursor: "pointer" }}
                onChange={(evento) => escolherFoto(evento.target.files?.[0] ?? null)}
              />
            </label>
            {previa ? (
              <span style={{ display: "flex", alignItems: "center", gap: 8.4 }}>
                <img src={previa} alt={t("relatar.form.previaAlt")} style={{ width: 56, height: 56, objectFit: "cover", borderRadius: 8 }} />
                <button type="button" className="btn btn-ghost" style={{ fontSize: 12.5 }} onClick={() => escolherFoto(null)}>
                  {t("relatar.form.remover")}
                </button>
              </span>
            ) : (
              <span style={{ fontSize: 11.5, color: TEXT.faint }}>
                {t("relatar.form.fotoOpcional", { mb: FOTO_MAX_MB })}
              </span>
            )}
          </div>

          {erro ? <p role="alert" style={{ margin: 0, fontSize: 12.5, color: C.ambar }}>{erro}</p> : null}
          {aviso ? <p role="status" style={{ margin: 0, fontSize: 12.5, color: C.verde }}>{aviso}</p> : null}

          <div>
            <button type="submit" className="btn btn-primary" disabled={enviando}>
              {enviando ? t("relatar.form.enviando") : t("relatar.form.enviar")}
            </button>
          </div>
        </form>
      </Panel>

      {meus.data && meus.data.length > 0 ? (
        <Panel pad={16.8}>
          <Kicker style={{ display: "block", marginBottom: 11.2 }}>{t("relatar.meus.titulo")}</Kicker>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8.4 }}>
            {meus.data.map((relato) => (
              <li key={relato.id} style={{ padding: "10px 12px", borderRadius: 8, background: "#0c0c10" }}>
                <div style={{ display: "flex", gap: 8.4, alignItems: "baseline", flexWrap: "wrap" }}>
                  <span style={{ fontSize: 12, color: TEXT.faint }}>
                    {relato.kind === "reclamacao" ? t("relatar.tipo.reclamacao") : t("relatar.tipo.sugestao")} ·{" "}
                    {new Date(relato.created_at).toLocaleDateString(idioma)}
                  </span>
                  <span style={{ marginLeft: "auto", fontSize: 12, color: ROTULO_STATUS[relato.status].cor }}>
                    {t(ROTULO_STATUS[relato.status].chave)}
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
                    <strong style={{ fontWeight: 500 }}>{t("relatar.meus.resposta")}</strong> {relato.moderator_note}
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
