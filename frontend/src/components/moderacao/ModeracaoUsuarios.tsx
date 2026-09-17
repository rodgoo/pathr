/**
 * As contas cadastradas, para o super admin: nome, foto, e-mail, e banir.
 *
 * Aparece só para quem administra contas, mas não é a tela que protege nada —
 * o servidor responde 404 em /admin para qualquer outra conta.
 *
 * Banir e desbanir pedem a chave de acesso NA HORA: o botão abre o motivo, e
 * confirmar chama o leitor de digital (ou o PIN) do aparelho. Uma sessão
 * aberta sozinha não bane ninguém — ver routers/admin.py no backend.
 *
 * A lista não vai para o cache offline (`semCache`): são os e-mails de todas
 * as contas, e não devem ficar guardados no navegador de ninguém.
 */

import { useEffect, useState } from "react";
import { startAuthentication } from "@simplewebauthn/browser";
import { admin } from "@/api/endpoints";
import type { UsuarioAdmin } from "@/api/types";
import { useQuery } from "@/hooks/useApi";
import { useIdioma, useT, type Idioma, type Traduzir } from "@/lib/i18n";
import { fotoDe } from "@/lib/fotos";
import { C, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { Segmented } from "@/components/ui/Segmented";
import { Kicker, Panel } from "@/components/ui/primitives";

type Situacao = "todos" | "ativos" | "banidos";

// Só os valores no módulo; os rótulos saem no idioma ativo dentro do componente.
const SITUACOES: readonly Situacao[] = ["todos", "ativos", "banidos"];

const VERMELHO = "#e06c75";

function data(iso: string | null, idioma: Idioma): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString(idioma);
}

/** A assinatura da chave de acesso do admin, com a mensagem certa quando falha. */
async function assinarComChave(t: Traduzir) {
  const pedido = await admin.confirmacao();
  try {
    const credential = await startAuthentication({
      optionsJSON: pedido.options as unknown as Parameters<typeof startAuthentication>[0]["optionsJSON"],
    });
    return { challenge_id: pedido.challenge_id, credential };
  } catch (erro) {
    if (erro instanceof Error && erro.name === "NotAllowedError") {
      throw new Error(t("moderacao.usuarios.confirmacaoCancelada"));
    }
    throw erro;
  }
}

function Foto({ usuario }: { usuario: UsuarioAdmin }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let vivo = true;
    if (usuario.has_avatar) {
      void fotoDe(`admin:${usuario.id}`, () => admin.avatar(usuario.id)).then((u) => {
        if (vivo) setUrl(u);
      });
    }
    return () => {
      vivo = false;
    };
  }, [usuario.id, usuario.has_avatar]);
  const iniciais = (usuario.name || usuario.email).trim().slice(0, 1).toUpperCase();
  return url ? (
    <img src={url} alt="" width={40} height={40} style={{ width: 40, height: 40, borderRadius: "50%", objectFit: "cover", flex: "none" }} />
  ) : (
    <span
      aria-hidden
      style={{
        width: 40,
        height: 40,
        borderRadius: "50%",
        flex: "none",
        display: "grid",
        placeItems: "center",
        background: "rgba(233,233,237,.08)",
        color: TEXT.muted,
        fontSize: 15,
      }}
    >
      {iniciais}
    </span>
  );
}

function Selo({ cor, children }: { cor: string; children: React.ReactNode }) {
  return (
    <span style={{ fontSize: 11, padding: "1px 7px", borderRadius: 5, background: tint(cor, 14), color: cor }}>{children}</span>
  );
}

function LinhaUsuario({ usuario, onMudou }: { usuario: UsuarioAdmin; onMudou: () => void }) {
  const t = useT();
  const { idioma } = useIdioma();
  const [abrindo, setAbrindo] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const banido = Boolean(usuario.banned_at);
  const podeBanir = !usuario.voce && !usuario.is_super_admin;

  async function confirmar() {
    setEnviando(true);
    setErro(null);
    try {
      const assinatura = await assinarComChave(t);
      if (banido) await admin.desbanir(usuario.id, assinatura);
      else await admin.banir(usuario.id, { motivo: motivo.trim(), ...assinatura });
      setAbrindo(false);
      setMotivo("");
      onMudou();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : t("moderacao.usuarios.erroConcluir"));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <li style={{ padding: 12, borderRadius: 10, background: "#0c0c10", display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11.2, flexWrap: "wrap" }}>
        <Foto usuario={usuario} />
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: 6 }}>
            <strong style={{ fontWeight: 500, fontSize: 14, color: TEXT.full }}>{usuario.name || t("moderacao.usuarios.semNome")}</strong>
            {usuario.username ? <span style={{ fontSize: 12, color: TEXT.faint }}>@{usuario.username}</span> : null}
            {usuario.voce ? <Selo cor={C.azul}>{t("moderacao.usuarios.selos.voce")}</Selo> : null}
            {usuario.is_super_admin ? <Selo cor={C.teal}>{t("moderacao.usuarios.selos.admin")}</Selo> : null}
            {banido ? <Selo cor={VERMELHO}>{t("moderacao.usuarios.selos.banido")}</Selo> : null}
            {!usuario.email_verified ? <Selo cor={C.ambar}>{t("moderacao.usuarios.selos.emailNaoConfirmado")}</Selo> : null}
          </div>
          <div style={{ fontSize: 12.5, color: TEXT.muted, overflowWrap: "anywhere" }}>{usuario.email}</div>
          <div style={{ fontSize: 11.5, color: TEXT.faint }}>
            {t("moderacao.usuarios.entrouEm", { data: data(usuario.created_at, idioma) })}
            {banido ? t("moderacao.usuarios.banidoEm", { data: data(usuario.banned_at, idioma) }) : ""}
          </div>
          {banido && usuario.banned_reason ? (
            <div style={{ fontSize: 12, color: TEXT.muted, marginTop: 2 }}>{t("moderacao.usuarios.motivoLabel", { motivo: usuario.banned_reason })}</div>
          ) : null}
        </div>
        {podeBanir && !abrindo ? (
          <button
            type="button"
            className="btn btn-ghost"
            style={{ fontSize: 12.5, color: banido ? C.verde : VERMELHO }}
            onClick={() => {
              setErro(null);
              setAbrindo(true);
            }}
          >
            <Icon name={banido ? "undo" : "lock"} size={14} />
            {banido ? t("moderacao.usuarios.desbanir") : t("moderacao.usuarios.banir")}
          </button>
        ) : null}
      </div>

      {abrindo ? (
        <div
          role="group"
          aria-label={banido ? t("moderacao.usuarios.desbanirAria", { nome: usuario.name }) : t("moderacao.usuarios.banirAria", { nome: usuario.name })}
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8.4,
            padding: 11.2,
            borderRadius: 8,
            boxShadow: `inset 0 0 0 1px ${tint(banido ? C.verde : VERMELHO, 40)}`,
          }}
        >
          {banido ? (
            <p style={{ margin: 0, fontSize: 12.5, color: TEXT.strong }}>
              {t("moderacao.usuarios.avisoDesbanir")}
            </p>
          ) : (
            <>
              <p style={{ margin: 0, fontSize: 12.5, color: TEXT.strong }}>
                {t("moderacao.usuarios.avisoBanir")}
              </p>
              <div className="field" style={{ margin: 0 }}>
                <label htmlFor={`motivo-${usuario.id}`}>{t("moderacao.usuarios.motivoCampo")}</label>
                <textarea
                  id={`motivo-${usuario.id}`}
                  className="input"
                  maxLength={500}
                  value={motivo}
                  onChange={(evento) => setMotivo(evento.target.value)}
                  style={{ minHeight: 64 }}
                />
              </div>
            </>
          )}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "center" }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={enviando || (!banido && motivo.trim().length < 3)}
              onClick={() => void confirmar()}
              style={banido ? undefined : { background: VERMELHO, borderColor: VERMELHO }}
            >
              <Icon name="fingerprint" size={15} />
              {enviando ? t("moderacao.usuarios.aguardandoChave") : t("moderacao.usuarios.confirmarChave")}
            </button>
            <button type="button" className="btn btn-ghost" disabled={enviando} onClick={() => setAbrindo(false)}>
              {t("moderacao.usuarios.cancelar")}
            </button>
          </div>
          {erro ? (
            <div role="alert" style={{ fontSize: 12.5, color: C.ambar }}>
              {erro}
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

export function ModeracaoUsuarios() {
  const t = useT();
  const [busca, setBusca] = useState("");
  const [termo, setTermo] = useState("");
  const [situacao, setSituacao] = useState<Situacao>("todos");
  const lista = useQuery(() => admin.usuarios(termo, situacao), [termo, situacao]);
  const situacoes = SITUACOES.map((value) => ({ value, label: t(`moderacao.usuarios.situacoes.${value}`) }));

  // Espera a pessoa parar de digitar antes de buscar.
  useEffect(() => {
    const timer = window.setTimeout(() => setTermo(busca.trim()), 350);
    return () => window.clearTimeout(timer);
  }, [busca]);

  const usuarios = lista.data?.usuarios ?? [];

  return (
    <Panel pad={16.8} style={{ boxShadow: `0 0 0 1px ${tint(VERMELHO, 25)}`, marginBottom: 16.8 }}>
      <section aria-label={t("moderacao.usuarios.secaoAria")}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 11.2, marginBottom: 12 }}>
          <Kicker>{t("moderacao.usuarios.titulo")}</Kicker>
          {lista.data ? (
            <span style={{ fontSize: 11.5, color: TEXT.faint }}>
              {usuarios.length} {t(usuarios.length === 1 ? "moderacao.usuarios.conta" : "moderacao.usuarios.contas")}
              {usuarios.length >= lista.data.limite ? t("moderacao.usuarios.maisRecentes") : ""}
            </span>
          ) : null}
          <Segmented
            name="usuarios-situacao"
            label={t("moderacao.usuarios.situacaoLabel")}
            value={situacao}
            options={situacoes}
            onChange={setSituacao}
            style={{ marginLeft: "auto" }}
          />
        </div>
        <div className="field" style={{ margin: "0 0 12px" }}>
          <label htmlFor="usuarios-busca">{t("moderacao.usuarios.buscar")}</label>
          <input
            id="usuarios-busca"
            className="input"
            type="search"
            placeholder={t("moderacao.usuarios.buscarPlaceholder")}
            value={busca}
            onChange={(evento) => setBusca(evento.target.value)}
          />
        </div>
        {lista.loading && !lista.data ? <p style={{ fontSize: 12.5, color: TEXT.faint, margin: 0 }}>{t("moderacao.usuarios.carregando")}</p> : null}
        {lista.error ? (
          <p role="alert" style={{ fontSize: 12.5, color: C.ambar, margin: 0 }}>
            {lista.error}
          </p>
        ) : null}
        {lista.data && usuarios.length === 0 ? (
          <p style={{ fontSize: 13, color: TEXT.muted, margin: 0 }}>{t("moderacao.usuarios.vazio")}</p>
        ) : null}
        {usuarios.length > 0 ? (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8.4 }}>
            {usuarios.map((usuario) => (
              <LinhaUsuario key={`${usuario.id}-${usuario.banned_at ?? ""}`} usuario={usuario} onMudou={lista.reload} />
            ))}
          </ul>
        ) : null}
      </section>
    </Panel>
  );
}
