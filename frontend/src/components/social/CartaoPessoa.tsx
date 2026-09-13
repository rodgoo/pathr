/**
 * Uma pessoa, do jeito que outra conta a vê.
 *
 * Nome, @, foto, onde mora, o que quer ser e em que tecnologias está — o
 * suficiente para decidir se aquele contato ajuda no que se estuda, e nada
 * que sirva para achar a pessoa fora do app. O servidor já não manda e-mail
 * nem nascimento; este componente não teria onde mostrá-los.
 *
 * O botão muda com a relação, e é um só por vez: "Adicionar", "Aceitar",
 * "Convite enviado", "Amigos". Dois botões iguais em dois lugares do cartão
 * fariam a pessoa se perguntar qual dos dois vale.
 */

import { useEffect, useState } from "react";
import { social } from "@/api/endpoints";
import type { PessoaCartao } from "@/api/types";
import { ACC3, C, HAIRLINE, TEXT } from "@/lib/tokens";

const SENIORIDADE: Record<string, string> = {
  estagio: "Estágio",
  junior: "Júnior",
  pleno: "Pleno",
  senior: "Sênior",
  especialista: "Especialista",
  lideranca: "Liderança",
};

function iniciais(nome: string): string {
  return (
    nome
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((parte) => parte[0]?.toUpperCase())
      .join("") || "?"
  );
}

/** A foto pela API, com a sessão; as iniciais enquanto não chega ou se não há. */
export function FotoDePessoa({ pessoa, lado = 48 }: { pessoa: PessoaCartao; lado?: number }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!pessoa.has_avatar) return undefined;
    let vivo = true;
    let criada: string | null = null;
    social
      .avatar(pessoa.username)
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
  }, [pessoa.username, pessoa.has_avatar]);

  return (
    <span
      aria-hidden
      style={{
        width: lado,
        height: lado,
        flex: "none",
        borderRadius: lado / 4,
        overflow: "hidden",
        display: "grid",
        placeItems: "center",
        background: "rgba(145,132,217,.14)",
        color: ACC3,
        fontSize: lado * 0.36,
        fontWeight: 500,
      }}
    >
      {url ? (
        <img src={url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      ) : (
        iniciais(pessoa.name)
      )}
    </span>
  );
}

export function CartaoPessoa({
  pessoa,
  onMudou,
  somenteLeitura = false,
}: {
  pessoa: PessoaCartao;
  /** A relação mudou no servidor: quem mostra a lista recarrega. */
  onMudou: () => void;
  /**
   * Cartão de exemplo (a página de apresentação): os botões aparecem, mas
   * nenhum chama a API. Não confiar só no `inert` da moldura — navegador
   * sem suporte a ele deixaria um visitante disparar um convite.
   */
  somenteLeitura?: boolean;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [confirmandoSaida, setConfirmandoSaida] = useState(false);

  async function agir(acao: () => Promise<unknown>) {
    if (somenteLeitura) return;
    setOcupado(true);
    setErro(null);
    try {
      await acao();
      onMudou();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : "Não consegui concluir.");
    } finally {
      setOcupado(false);
      setConfirmandoSaida(false);
    }
  }

  const lugar = [pessoa.city, pessoa.state].filter(Boolean).join(" · ");
  const sobre = [pessoa.senioridade ? SENIORIDADE[pessoa.senioridade] ?? pessoa.senioridade : null, pessoa.cargo]
    .filter(Boolean)
    .join(" · ");
  const id = pessoa.friendship_id;

  return (
    <article
      aria-label={`${pessoa.name}, @${pessoa.username}`}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 11.2,
        padding: 14,
        borderRadius: 12,
        background: "#1b1d2b",
        boxShadow: `inset 0 0 0 1px ${HAIRLINE}`,
        minWidth: 0,
      }}
    >
      <div style={{ display: "flex", gap: 11.2, alignItems: "center", minWidth: 0 }}>
        <FotoDePessoa pessoa={pessoa} />
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14.5, color: TEXT.strong, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {pessoa.name}
          </div>
          <div style={{ fontSize: 12, color: ACC3 }}>@{pessoa.username}</div>
          {lugar ? <div style={{ fontSize: 11.5, color: TEXT.faint, marginTop: 2 }}>{lugar}</div> : null}
        </div>
      </div>

      {pessoa.objetivo || sobre ? (
        <div style={{ fontSize: 12.5, color: TEXT.muted, lineHeight: 1.45 }}>
          {pessoa.objetivo ? (
            <div>
              <span style={{ color: TEXT.faint }}>Objetivo: </span>
              {pessoa.objetivo}
            </div>
          ) : null}
          {sobre ? <div style={{ color: TEXT.faint, marginTop: 2 }}>{sobre}</div> : null}
        </div>
      ) : null}

      {pessoa.stack.length > 0 ? (
        <ul aria-label="Stack" style={{ display: "flex", flexWrap: "wrap", gap: 5, margin: 0, padding: 0, listStyle: "none" }}>
          {pessoa.stack.map((tecnologia) => (
            <li key={tecnologia} className="tag tag-outline" style={{ fontSize: 11 }}>
              {tecnologia}
            </li>
          ))}
        </ul>
      ) : null}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "center", marginTop: "auto" }}>
        {pessoa.relacao === "nenhuma" ? (
          <button type="button" className="btn btn-primary" disabled={ocupado}
            onClick={() => void agir(() => social.convidar(pessoa.username))}>
            {ocupado ? "Enviando…" : "Adicionar"}
          </button>
        ) : null}

        {pessoa.relacao === "recebido" && id ? (
          <>
            <button type="button" className="btn btn-primary" disabled={ocupado}
              onClick={() => void agir(() => social.aceitar(id))}>
              Aceitar
            </button>
            <button type="button" className="btn btn-ghost" disabled={ocupado}
              onClick={() => void agir(() => social.desfazer(id))}>
              Recusar
            </button>
          </>
        ) : null}

        {pessoa.relacao === "enviado" && id ? (
          <>
            <span style={{ fontSize: 12.5, color: TEXT.faint }}>Convite enviado</span>
            <button type="button" className="btn btn-ghost" disabled={ocupado}
              onClick={() => void agir(() => social.desfazer(id))}>
              Cancelar
            </button>
          </>
        ) : null}

        {pessoa.relacao === "amigos" && id ? (
          confirmandoSaida ? (
            <>
              <span style={{ fontSize: 12.5, color: TEXT.muted }}>Desfazer a amizade?</span>
              <button type="button" className="btn btn-ghost" style={{ color: C.ambar }} disabled={ocupado}
                onClick={() => void agir(() => social.desfazer(id))}>
                Desfazer
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setConfirmandoSaida(false)}>
                Manter
              </button>
            </>
          ) : (
            <>
              <span style={{ fontSize: 12.5, color: C.verde }}>Amigos</span>
              <button type="button" className="btn btn-ghost" style={{ fontSize: 12, color: TEXT.faint }}
                onClick={() => setConfirmandoSaida(true)}>
                Desfazer amizade
              </button>
            </>
          )
        ) : null}
      </div>

      {erro ? <p role="alert" style={{ margin: 0, fontSize: 12, color: C.ambar }}>{erro}</p> : null}
    </article>
  );
}
