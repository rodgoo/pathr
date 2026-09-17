/**
 * Chaves de acesso, na aba Conta.
 *
 * Criar uma chave aqui é o que liga a entrada pelo rosto, pela digital ou pelo
 * PIN do aparelho. A lista mostra onde cada chave foi criada e quando foi
 * usada, para quem perder um celular saber qual apagar.
 *
 * Todo botão é `type="button"`: o painel mora dentro do formulário de dados
 * pessoais, e um botão sem tipo enviaria aquele formulário.
 */

import { useState } from "react";
import { startRegistration } from "@simplewebauthn/browser";
import { passkeys as passkeysApi } from "@/api/endpoints";
import type { Passkey } from "@/api/types";
import { useQuery } from "@/hooks/useApi";
import { useIdioma, useT } from "@/lib/i18n";
import { chaveSuportada, esquecerChave, lembrarChave, mensagemDeErroDaChave } from "@/lib/passkeys";
import { C, HAIRLINE, TEXT } from "@/lib/tokens";
import { IconButton } from "@/components/ui/IconButton";
import { Kicker, Panel } from "@/components/ui/primitives";

type OpcoesDeCadastro = Parameters<typeof startRegistration>[0]["optionsJSON"];

function data(iso: string | null, idioma: string): string {
  return iso ? new Date(iso).toLocaleDateString(idioma) : "";
}

export function PasskeysPanel() {
  const t = useT();
  const { idioma } = useIdioma();
  const lista = useQuery(() => passkeysApi.list(), []);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const suportada = chaveSuportada();

  async function criar() {
    setOcupado("criar");
    setErro(null);
    setAviso(null);
    try {
      const pedido = await passkeysApi.registerOptions();
      const credencial = await startRegistration({
        optionsJSON: pedido.options as unknown as OpcoesDeCadastro,
      });
      await passkeysApi.registerVerify(pedido.challenge_id, credencial);
      lembrarChave();
      setAviso(t("passkeys.criada"));
      lista.reload();
    } catch (caught) {
      const mensagem = mensagemDeErroDaChave(caught);
      if (mensagem) setErro(mensagem);
    } finally {
      setOcupado(null);
    }
  }

  async function remover(chave: Passkey) {
    setOcupado(chave.id);
    setErro(null);
    setAviso(null);
    try {
      await passkeysApi.remove(chave.id);
      // Sem chave nenhuma na conta, a tela de entrada deixa de oferecer a
      // chave como caminho principal neste aparelho.
      if ((lista.data ?? []).filter((c) => c.id !== chave.id).length === 0) esquecerChave();
      lista.reload();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : t("passkeys.erroRemover"));
    } finally {
      setOcupado(null);
    }
  }

  const chavesDaConta = lista.data ?? [];

  return (
    <Panel pad={16.8}>
      <Kicker style={{ display: "block", marginBottom: 5.6 }}>{t("passkeys.titulo")}</Kicker>
      <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "72ch" }}>
        {t("passkeys.explica")}
      </p>

      {chavesDaConta.length > 0 ? (
        <ul style={{ listStyle: "none", margin: "0 0 11.2px", padding: 0 }}>
          {chavesDaConta.map((chave) => (
            <li
              key={chave.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 11.2,
                padding: "8.4px 0",
                borderTop: `1px solid ${HAIRLINE}`,
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13.5 }}>{chave.name}</div>
                <div style={{ fontSize: 11.5, color: TEXT.faint }}>
                  {t("passkeys.criadaEm", { data: data(chave.created_at, idioma) })}
                  {chave.last_used_at
                    ? t("passkeys.usadaEm", { data: data(chave.last_used_at, idioma) })
                    : t("passkeys.aindaNaoUsada")}
                  {chave.backed_up ? t("passkeys.sincronizada") : ""}
                </div>
              </div>
              <IconButton
                icon="trash"
                label={ocupado === chave.id ? t("passkeys.removendo") : t("passkeys.remover")}
                color={C.ambar}
                disabled={ocupado === chave.id}
                onClick={() => void remover(chave)}
              />
            </li>
          ))}
        </ul>
      ) : null}

      {suportada ? (
        <button
          type="button"
          className="btn btn-secondary"
          disabled={ocupado === "criar"}
          onClick={() => void criar()}
        >
          {ocupado === "criar" ? t("passkeys.aguardando") : t("passkeys.criar")}
        </button>
      ) : (
        <p style={{ fontSize: 12.5, color: TEXT.faint, margin: 0 }}>
          {t("passkeys.semSuporte")}
        </p>
      )}

      {chavesDaConta.length > 0 ? (
        <p style={{ fontSize: 11.5, color: TEXT.faint, margin: "8.4px 0 0" }}>
          {t("passkeys.notaRemover")}
        </p>
      ) : null}

      {aviso ? (
        <p role="status" style={{ fontSize: 12.5, color: C.verde, margin: "8.4px 0 0" }}>
          {aviso}
        </p>
      ) : null}
      {erro ? (
        <p role="alert" style={{ fontSize: 12.5, color: C.ambar, margin: "8.4px 0 0" }}>
          {erro}
        </p>
      ) : null}
    </Panel>
  );
}
