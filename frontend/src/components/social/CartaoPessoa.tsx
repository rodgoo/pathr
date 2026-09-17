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
import type { PessoaCartao, SequenciaDupla } from "@/api/types";
import { CardDeConquista } from "@/components/social/CardDeConquista";
import { Icon } from "@/components/ui/icons";
import { marcoAtingido, proximoMarco } from "@/lib/conquista";
import { fotoDe } from "@/lib/fotos";
import { MarcaDaTecnologia, identidade } from "@/lib/tecnologias";
import { ACC, ACC3, C, HAIRLINE, TEXT, tint } from "@/lib/tokens";
import { useT } from "@/lib/i18n";

export type AcaoDeAmizade = "convidar" | "aceitar" | "desfazer";

/** O tom de um `.btn-tom`: a cor do significado da ação. */
const tom = (cor: string) => ({ "--tom": cor }) as CSSProperties;

/** O degrau de senioridade, pela chave do dicionário. */
const SENIORIDADE: Record<string, string> = {
  estagio: "senioridade.estagio",
  junior: "senioridade.junior",
  pleno: "senioridade.pleno",
  senior: "senioridade.senior",
  especialista: "senioridade.especialista",
  lideranca: "senioridade.lideranca",
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
    // Da memória de fotos (lib/fotos): a lista de amigos, o pop-up e o card
    // usam a mesma foto sem baixá-la de novo.
    void fotoDe(pessoa.username, () => social.avatar(pessoa.username)).then((guardada) => {
      if (vivo) setUrl(guardada);
    });
    return () => {
      vivo = false;
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
  onDemo,
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
  /**
   * Só com `somenteLeitura`: em vez da API, avisa qual ação foi pedida, para
   * a página de apresentação simular o resultado na tela sem sair do navegador.
   */
  onDemo?: (acao: AcaoDeAmizade) => void;
}) {
  const t = useT();
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [confirmandoSaida, setConfirmandoSaida] = useState(false);

  async function agir(acao: () => Promise<unknown>, tipo: AcaoDeAmizade) {
    if (somenteLeitura) {
      onDemo?.(tipo);
      setConfirmandoSaida(false);
      return;
    }
    setOcupado(true);
    setErro(null);
    try {
      await acao();
      onMudou();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : t("pessoa.erro"));
    } finally {
      setOcupado(false);
      setConfirmandoSaida(false);
    }
  }

  const lugar = [pessoa.city, pessoa.state].filter(Boolean).join(" · ");
  const sobre = [pessoa.senioridade ? (SENIORIDADE[pessoa.senioridade] ? t(SENIORIDADE[pessoa.senioridade]) : pessoa.senioridade) : null, pessoa.cargo]
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
              <span style={{ color: TEXT.faint }}>{t("pessoa.objetivo")} </span>
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
              {t("pessoa.mesmaStack")}
            </div>
          ) : emComum.size > 0 ? (
            <div style={{ fontSize: 12, color: TEXT.faint }}>
              {t(emComum.size === 1 ? "pessoa.umaEmComum" : "pessoa.emComum", { n: emComum.size })}
            </div>
          ) : null}
          <ul aria-label={t("pessoa.stack")} style={{ display: "flex", flexWrap: "wrap", gap: 5, margin: 0, padding: 0, listStyle: "none" }}>
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

      {pessoa.relacao === "amigos" && pessoa.sequencia ? (
        <SequenciaJuntos pessoa={pessoa} sequencia={pessoa.sequencia} />
      ) : null}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "center", marginTop: "auto" }}>
        {pessoa.relacao === "nenhuma" ? (
          <button type="button" className="btn btn-tom" style={tom(ACC)} disabled={ocupado}
            onClick={() => void agir(() => social.convidar(pessoa.username), "convidar")}>
            <Icon name="plus" size={15} />
            {ocupado ? t("pessoa.enviando") : t("pessoa.adicionar")}
          </button>
        ) : null}

        {pessoa.relacao === "recebido" && id ? (
          <>
            <button type="button" className="btn btn-tom" style={tom(C.verde)} disabled={ocupado}
              onClick={() => void agir(() => social.aceitar(id), "aceitar")}>
              <Icon name="check" size={15} />
              {t("pessoa.aceitar")}
            </button>
            <button type="button" className="btn btn-tom-leve" style={tom(C.rosa)} disabled={ocupado}
              onClick={() => void agir(() => social.desfazer(id), "desfazer")}>
              <Icon name="x" size={15} />
              {t("pessoa.recusar")}
            </button>
          </>
        ) : null}

        {pessoa.relacao === "enviado" && id ? (
          <>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: C.ambar }}>
              <Icon name="clock" size={14} />
              {t("pessoa.conviteEnviado")}
            </span>
            <button type="button" className="btn btn-tom-leve" style={tom(C.rosa)} disabled={ocupado}
              onClick={() => void agir(() => social.desfazer(id), "desfazer")}>
              <Icon name="x" size={14} />
              {t("pessoa.cancelar")}
            </button>
          </>
        ) : null}

        {pessoa.relacao === "amigos" && id ? (
          confirmandoSaida ? (
            <>
              <span style={{ fontSize: 12.5, color: TEXT.muted }}>{t("pessoa.desfazerPergunta")}</span>
              <button type="button" className="btn btn-tom" style={tom(C.rosa)} disabled={ocupado}
                onClick={() => void agir(() => social.desfazer(id), "desfazer")}>
                <Icon name="trash" size={14} />
                {t("pessoa.desfazer")}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setConfirmandoSaida(false)}>
                {t("pessoa.manter")}
              </button>
            </>
          ) : (
            <>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: C.verde }}>
                <Icon name="users" size={14} />
                {t("pessoa.amigos")}
              </span>
              <button type="button" className="btn btn-ghost" style={{ fontSize: 12, color: TEXT.faint }}
                onClick={() => setConfirmandoSaida(true)}>
                {t("pessoa.desfazerAmizade")}
              </button>
            </>
          )
        ) : null}
      </div>

      {erro ? <p role="alert" style={{ margin: 0, fontSize: 12, color: C.ambar }}>{erro}</p> : null}
    </article>
  );
}

/**
 * A sequência de estudos com este amigo: quantos dias seguidos os dois
 * estudaram, quem ainda falta hoje, e — num marco (7, 30, 60, 90…) — o card
 * para compartilhar.
 */
function SequenciaJuntos({ pessoa, sequencia }: { pessoa: PessoaCartao; sequencia: SequenciaDupla }) {
  const t = useT();
  const [abrindo, setAbrindo] = useState(false);
  const primeiro = pessoa.name.split(/\s+/)[0] ?? pessoa.name;
  const { atual, hoje_voce, hoje_amigo } = sequencia;
  const marco = marcoAtingido(atual);
  const cor = atual > 0 ? "#e2794a" : TEXT.faint;

  let hoje: string;
  if (hoje_voce && hoje_amigo) hoje = t("sequencia.ambosHoje");
  else if (hoje_voce) hoje = t("sequencia.faltaAmigo", { nome: primeiro });
  else if (hoje_amigo) hoje = t("sequencia.faltaVoce", { nome: primeiro });
  else hoje = atual > 0 ? t("sequencia.mantenham") : t("sequencia.comecar");

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
        padding: "9px 11px",
        borderRadius: 9,
        background: tint("#e2794a", atual > 0 ? 9 : 4),
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13, color: TEXT.strong }}>
        <Icon name="fogo" size={16} style={{ color: cor }} fill={atual > 0 ? cor : "none"} fillOpacity={atual > 0 ? 0.35 : undefined} />
        {atual > 0 ? (
          <span>
            <strong style={{ color: cor }}>{atual}</strong>{" "}
            {atual === 1 ? t("sequencia.diaJuntos") : t("sequencia.diasJuntos")}
          </span>
        ) : (
          <span style={{ color: TEXT.muted }}>{t("sequencia.semSequencia")}</span>
        )}
        {sequencia.recorde > atual ? (
          <span style={{ marginLeft: "auto", fontSize: 11, color: TEXT.faint }}>
            {t("sequencia.recorde", { n: sequencia.recorde })}
          </span>
        ) : null}
      </div>
      <div style={{ fontSize: 12, color: TEXT.muted }}>
        {hoje}
        {atual > 0 && !marco
          ? ` ${t("sequencia.faltamParaCard", { faltam: proximoMarco(atual) - atual, alvo: proximoMarco(atual) })}`
          : ""}
      </div>
      {marco ? (
        <button
          type="button"
          className="btn btn-tom"
          style={{ ...tom("#e2794a"), alignSelf: "flex-start" }}
          onClick={() => setAbrindo(true)}
        >
          <Icon name="award" size={15} />
          {t("sequencia.cardDias", { n: marco })}
        </button>
      ) : null}
      {abrindo && marco ? <CardDeConquista amigo={pessoa} dias={marco} onFechar={() => setAbrindo(false)} /> : null}
    </div>
  );
}
