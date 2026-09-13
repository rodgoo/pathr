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

import { useEffect, useState, type CSSProperties } from "react";
import { social } from "@/api/endpoints";
import type { PessoaCartao } from "@/api/types";
import { Icon } from "@/components/ui/icons";
import { MarcaDaTecnologia, identidade } from "@/lib/tecnologias";
import { ACC, ACC3, C, HAIRLINE, TEXT, tint } from "@/lib/tokens";

/** O tom de um `.btn-tom`: a cor do significado da ação. */
const tom = (cor: string) => ({ "--tom": cor }) as CSSProperties;

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
  const emComum = new Set(pessoa.em_comum ?? []);

  return (
    <article
      aria-label={`${pessoa.name}, @${pessoa.username}`}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 11.2,
        padding: 14,
        borderRadius: 12,
        background: "#0c0c10",
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
        <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
          {pessoa.mesma_stack ? (
            <div style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: C.verde }}>
              <Icon name="check" size={13} />
              Vocês possuem a mesma stack
            </div>
          ) : emComum.size > 0 ? (
            <div style={{ fontSize: 12, color: TEXT.faint }}>
              {emComum.size === 1 ? "1 tecnologia em comum" : `${emComum.size} tecnologias em comum`}
            </div>
          ) : null}
          <ul aria-label="Stack" style={{ display: "flex", flexWrap: "wrap", gap: 5, margin: 0, padding: 0, listStyle: "none" }}>
            {pessoa.stack.map((tecnologia) => {
              const { cor } = identidade(tecnologia);
              // Em comum com quem olha: contorno mais forte e um ✓ — é o
              // motivo mais concreto para adicionar alguém.
              const comum = emComum.has(tecnologia);
              return (
                <li
                  key={tecnologia}
                  title={comum ? `${tecnologia} · vocês dois estudam` : tecnologia}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 5,
                    padding: "3px 8px",
                    borderRadius: 6,
                    fontSize: 11.5,
                    color: TEXT.full,
                    background: tint(cor, comum ? 20 : 10),
                    border: `1px solid ${tint(cor, comum ? 70 : 32)}`,
                  }}
                >
                  <MarcaDaTecnologia nome={tecnologia} lado={13} />
                  {tecnologia}
                  {comum ? <Icon name="check" size={11} style={{ color: C.verde }} /> : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "center", marginTop: "auto" }}>
        {pessoa.relacao === "nenhuma" ? (
          <button type="button" className="btn btn-tom" style={tom(ACC)} disabled={ocupado}
            onClick={() => void agir(() => social.convidar(pessoa.username))}>
            <Icon name="plus" size={15} />
            {ocupado ? "Enviando…" : "Adicionar"}
          </button>
        ) : null}

        {pessoa.relacao === "recebido" && id ? (
          <>
            <button type="button" className="btn btn-tom" style={tom(C.verde)} disabled={ocupado}
              onClick={() => void agir(() => social.aceitar(id))}>
              <Icon name="check" size={15} />
              Aceitar
            </button>
            <button type="button" className="btn btn-tom-leve" style={tom(C.rosa)} disabled={ocupado}
              onClick={() => void agir(() => social.desfazer(id))}>
              <Icon name="x" size={15} />
              Recusar
            </button>
          </>
        ) : null}

        {pessoa.relacao === "enviado" && id ? (
          <>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: C.ambar }}>
              <Icon name="clock" size={14} />
              Convite enviado
            </span>
            <button type="button" className="btn btn-tom-leve" style={tom(C.rosa)} disabled={ocupado}
              onClick={() => void agir(() => social.desfazer(id))}>
              <Icon name="x" size={14} />
              Cancelar
            </button>
          </>
        ) : null}

        {pessoa.relacao === "amigos" && id ? (
          confirmandoSaida ? (
            <>
              <span style={{ fontSize: 12.5, color: TEXT.muted }}>Desfazer a amizade?</span>
              <button type="button" className="btn btn-tom" style={tom(C.rosa)} disabled={ocupado}
                onClick={() => void agir(() => social.desfazer(id))}>
                <Icon name="trash" size={14} />
                Desfazer
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setConfirmandoSaida(false)}>
                Manter
              </button>
            </>
          ) : (
            <>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: C.verde }}>
                <Icon name="user" size={14} />
                Amigos
              </span>
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
