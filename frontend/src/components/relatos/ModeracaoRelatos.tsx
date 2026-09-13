/**
 * A caixa de moderação: os relatos de todo mundo, para quem modera.
 *
 * Aparece só para a conta moderadora, mas não é a tela que protege nada — o
 * servidor responde 404 em /relatos/moderacao para qualquer outra conta.
 *
 * Tudo do relato entra como TEXTO. Mensagem, página e nome de quem relatou
 * passam pelo React, que escapa; nada vira link nem HTML. A foto vem pela API
 * como blob e é mostrada num `<img>` a partir de um `blob:` local — nunca de
 * um endereço que o autor do relato tenha escolhido.
 */

import { useEffect, useState } from "react";
import { relatos } from "@/api/endpoints";
import type { RelatoModeracao, StatusRelato } from "@/api/types";
import { useQuery } from "@/hooks/useApi";
import { C, HAIRLINE, TEXT } from "@/lib/tokens";
import { Segmented } from "@/components/ui/Segmented";
import { Select } from "@/components/ui/Select";
import { Kicker, Panel } from "@/components/ui/primitives";

type Situacao = "abertos" | "todos" | "resolvidos";

const SITUACOES: readonly { value: Situacao; label: string }[] = [
  { value: "abertos", label: "Abertos" },
  { value: "resolvidos", label: "Resolvidos" },
  { value: "todos", label: "Todos" },
];

const OPCOES_STATUS: readonly { value: StatusRelato; label: string }[] = [
  { value: "aberto", label: "Recebido" },
  { value: "em_analise", label: "Em análise" },
  { value: "resolvido", label: "Resolvido" },
];

function FotoDoRelato({ id }: { id: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let vivo = true;
    let criada: string | null = null;
    relatos
      .foto(id)
      .then((blob) => {
        if (!vivo) return;
        criada = URL.createObjectURL(blob);
        setUrl(criada);
      })
      .catch(() => undefined);
    return () => {
      vivo = false;
      if (criada) URL.revokeObjectURL(criada);
    };
  }, [id]);
  if (!url) return <span style={{ fontSize: 12, color: TEXT.faint }}>Carregando foto…</span>;
  return (
    <img
      src={url}
      alt="Foto anexada ao relato"
      style={{ maxWidth: "100%", maxHeight: 320, borderRadius: 8, boxShadow: `0 0 0 1px ${HAIRLINE}` }}
    />
  );
}

function ItemModeracao({ relato, onSalvo }: { relato: RelatoModeracao; onSalvo: () => void }) {
  const [statusNovo, setStatusNovo] = useState<StatusRelato>(relato.status);
  const [nota, setNota] = useState(relato.moderator_note ?? "");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const mudou = statusNovo !== relato.status || (nota.trim() || null) !== (relato.moderator_note ?? null);

  async function salvar() {
    setSalvando(true);
    setErro(null);
    try {
      await relatos.moderar(relato.id, { status: statusNovo, moderator_note: nota.trim() || null });
      onSalvo();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : "Não consegui salvar.");
    } finally {
      setSalvando(false);
    }
  }

  const autor = relato.author;
  return (
    <li style={{ padding: 14, borderRadius: 10, background: "#0c0c10", display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "baseline" }}>
        <span style={{ fontSize: 12, color: relato.kind === "reclamacao" ? C.ambar : C.verde }}>
          {relato.kind === "reclamacao" ? "Reclamação" : "Sugestão"}
        </span>
        <span style={{ fontSize: 12, color: TEXT.muted }}>
          {autor.name ?? "Conta removida"}
          {autor.username ? ` · @${autor.username}` : ""}
          {autor.email ? ` · ${autor.email}` : ""}
        </span>
        <span style={{ marginLeft: "auto", fontSize: 11.5, color: TEXT.faint }}>
          {new Date(relato.created_at).toLocaleString("pt-BR")}
        </span>
      </div>
      <p style={{ margin: 0, fontSize: 14, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{relato.message}</p>
      {relato.has_attachment ? <FotoDoRelato id={relato.id} /> : null}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "flex-end" }}>
        <div style={{ width: 170 }}>
          <label htmlFor={`status-${relato.id}`} style={{ fontSize: 11.5, color: TEXT.faint, display: "block", marginBottom: 4 }}>
            Status
          </label>
          <Select id={`status-${relato.id}`} value={statusNovo} options={OPCOES_STATUS} onChange={setStatusNovo} />
        </div>
        <div className="field" style={{ margin: 0, flex: 1, minWidth: 200 }}>
          <label htmlFor={`nota-${relato.id}`}>Resposta para quem relatou</label>
          <input
            id={`nota-${relato.id}`}
            className="input"
            maxLength={2000}
            value={nota}
            placeholder="Opcional — aparece em Seus relatos"
            onChange={(evento) => setNota(evento.target.value)}
          />
        </div>
        <button type="button" className="btn btn-primary" disabled={!mudou || salvando} onClick={() => void salvar()}>
          {salvando ? "Salvando…" : "Salvar"}
        </button>
      </div>
      {erro ? <p role="alert" style={{ margin: 0, fontSize: 12.5, color: C.ambar }}>{erro}</p> : null}
    </li>
  );
}

export function ModeracaoRelatos() {
  const [situacao, setSituacao] = useState<Situacao>("abertos");
  const lista = useQuery(() => relatos.moderacao(situacao), [situacao]);

  return (
    <Panel pad={16.8} style={{ boxShadow: `0 0 0 1px ${C.ambar}33` }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 11.2, marginBottom: 12 }}>
        <Kicker>Moderação</Kicker>
        {lista.data ? (
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>
            {lista.data.length} {lista.data.length === 1 ? "relato" : "relatos"}
          </span>
        ) : null}
        <Segmented
          name="moderacao-situacao"
          label="Situação dos relatos"
          value={situacao}
          options={SITUACOES}
          onChange={setSituacao}
          style={{ marginLeft: "auto" }}
        />
      </div>
      {lista.loading && !lista.data ? <p style={{ fontSize: 12.5, color: TEXT.faint, margin: 0 }}>Carregando…</p> : null}
      {lista.error ? <p role="alert" style={{ fontSize: 12.5, color: C.ambar, margin: 0 }}>{lista.error}</p> : null}
      {lista.data && lista.data.length === 0 ? (
        <p style={{ fontSize: 13, color: TEXT.muted, margin: 0 }}>Nenhum relato {situacao === "abertos" ? "em aberto" : "aqui"}.</p>
      ) : null}
      {lista.data && lista.data.length > 0 ? (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8.4 }}>
          {lista.data.map((relato) => (
            <ItemModeracao key={`${relato.id}-${relato.status}`} relato={relato} onSalvo={lista.reload} />
          ))}
        </ul>
      ) : null}
    </Panel>
  );
}
