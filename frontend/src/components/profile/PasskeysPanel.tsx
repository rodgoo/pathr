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
import { chaveSuportada, esquecerChave, lembrarChave, mensagemDeErroDaChave } from "@/lib/passkeys";
import { C, HAIRLINE, TEXT } from "@/lib/tokens";
import { IconButton } from "@/components/ui/IconButton";
import { Kicker, Panel } from "@/components/ui/primitives";

type OpcoesDeCadastro = Parameters<typeof startRegistration>[0]["optionsJSON"];

function data(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("pt-BR") : "";
}

export function PasskeysPanel() {
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
      setAviso(
        "Chave de acesso criada. Na próxima entrada, é só usar o rosto, a digital ou o PIN deste aparelho.",
      );
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
      setErro(caught instanceof Error ? caught.message : "Não consegui remover a chave.");
    } finally {
      setOcupado(null);
    }
  }

  const chavesDaConta = lista.data ?? [];

  return (
    <Panel pad={16.8}>
      <Kicker style={{ display: "block", marginBottom: 5.6 }}>Chaves de acesso</Kicker>
      <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "72ch" }}>
        Entre com o rosto, a digital ou o PIN do aparelho, sem digitar senha. A chave fica presa ao
        PathR — uma página falsa não consegue usá-la — e já vale como segundo fator.
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
                  criada em {data(chave.created_at)}
                  {chave.last_used_at ? ` · usada em ${data(chave.last_used_at)}` : " · ainda não usada"}
                  {chave.backed_up ? " · sincronizada entre aparelhos" : ""}
                </div>
              </div>
              <IconButton
                icon="trash"
                label={ocupado === chave.id ? "Removendo…" : "Remover"}
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
          {ocupado === "criar" ? "Aguardando o aparelho…" : "Criar chave de acesso neste aparelho"}
        </button>
      ) : (
        <p style={{ fontSize: 12.5, color: TEXT.faint, margin: 0 }}>
          Este navegador não oferece chave de acesso. Em celulares e navegadores atuais ela aparece
          aqui.
        </p>
      )}

      {chavesDaConta.length > 0 ? (
        <p style={{ fontSize: 11.5, color: TEXT.faint, margin: "8.4px 0 0" }}>
          Remover aqui desliga a chave no PathR. O aparelho pode continuar guardando-a — apague-a
          também no gerenciador de senhas se quiser.
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
