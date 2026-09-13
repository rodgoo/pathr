/**
 * O pop-up de amizade: "X te mandou um convite" e "X aceitou seu convite".
 *
 * Aparece no canto superior direito, com foto, nome e stack da outra pessoa,
 * e some sozinho em 5 segundos (pausa enquanto o mouse ou o foco estão nele).
 * No convite, aceitar e recusar resolvem ali mesmo.
 *
 * ## Quando aparece
 *
 * O servidor avisa as telas abertas da pessoa no instante do convite ou do
 * aceite (routers/social.py → eventos), e a lista de novidades é reconsultada.
 * Sem o aviso (rede instável), uma consulta a cada minuto pega o atraso.
 *
 * Cada novidade aparece UMA vez, em qualquer aparelho: ao mostrar, ela é
 * marcada como vista no servidor. Como o pop-up some rápido, o item Amigos da
 * navegação NÃO pisca: um item de menu piscando em amarelo competia com a
 * tela inteira, e o contador de convites em Amigos já diz que há o que ver.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { social } from "@/api/endpoints";
import type { NovidadeDeAmizade } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useQuery } from "@/hooks/useApi";
import { ACC, ACC3, C, TEXT, tint } from "@/lib/tokens";
import { dataRevision } from "@/offline/status";
import { FotoDePessoa } from "@/components/social/CartaoPessoa";
import { Icon } from "@/components/ui/icons";
import { IconButton } from "@/components/ui/IconButton";

const VISIVEL_MS = 5000;
const RECONSULTA_MS = 60_000;

/** `duracaoMs` existe para o teste; na tela vale o padrão de 5 segundos. */
export function AvisosDeAmizade({ duracaoMs = VISIVEL_MS }: { duracaoMs?: number } = {}) {
  const novidades = useQuery(() => social.novidades(), []);
  const [abertos, setAbertos] = useState<NovidadeDeAmizade[]>([]);
  const mostrados = useRef(new Set<string>());

  // O minuto de segurança, para quando o aviso instantâneo não chegar.
  const { reload } = novidades;
  useEffect(() => {
    const intervalo = window.setInterval(reload, RECONSULTA_MS);
    return () => window.clearInterval(intervalo);
  }, [reload]);

  useEffect(() => {
    const novas = (novidades.data ?? []).filter(
      (item) => !mostrados.current.has(`${item.tipo}:${item.friendship_id}`),
    );
    if (!novas.length) return;
    novas.forEach((item) => mostrados.current.add(`${item.tipo}:${item.friendship_id}`));
    setAbertos((atuais) => [...atuais, ...novas]);
    void social
      .marcarVistas(novas.map((item) => ({ friendship_id: item.friendship_id, tipo: item.tipo })))
      .catch(() => undefined); // sem marcar, o pior é o aviso reaparecer uma vez
  }, [novidades.data]);

  const fechar = useCallback((item: NovidadeDeAmizade) => {
    setAbertos((atuais) => atuais.filter((a) => a !== item));
  }, []);

  return (
    <>
      <style>{`
        @keyframes pathr-aviso-entra { from { opacity: 0; transform: translateY(-8px) } to { opacity: 1; transform: none } }
      `}</style>
      {abertos.length ? (
        <div
          aria-live="polite"
          style={{
            position: "fixed",
            top: "calc(12px + var(--safe-top, 0px))",
            right: "calc(12px + var(--safe-right, 0px))",
            zIndex: 70,
            display: "flex",
            flexDirection: "column",
            gap: 8.4,
            width: "min(360px, calc(100vw - 24px))",
          }}
        >
          {abertos.map((item) => (
            <Aviso key={`${item.tipo}:${item.friendship_id}`} item={item} duracaoMs={duracaoMs} onFechar={() => fechar(item)} />
          ))}
        </div>
      ) : null}
    </>
  );
}

function Aviso({ item, duracaoMs, onFechar }: { item: NovidadeDeAmizade; duracaoMs: number; onFechar: () => void }) {
  const { dispatch } = useAppState();
  const [pausado, setPausado] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const { pessoa } = item;
  const primeiro = pessoa.name.split(/\s+/)[0] ?? pessoa.name;

  // Numa referência: o pai recria `onFechar` a cada renderização, e com ele na
  // dependência o relógio de 5s recomeçaria a cada atualização da lista.
  const fecharRef = useRef(onFechar);
  fecharRef.current = onFechar;

  useEffect(() => {
    if (pausado || ocupado || erro) return undefined;
    const temporizador = window.setTimeout(() => fecharRef.current(), duracaoMs);
    return () => window.clearTimeout(temporizador);
  }, [pausado, ocupado, erro, duracaoMs]);

  async function responder(acao: () => Promise<unknown>) {
    setOcupado(true);
    setErro(null);
    try {
      await acao();
      // A lista de amigos e o contador da barra reconsultam.
      dataRevision.bump();
      onFechar();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : "Não consegui responder.");
      setOcupado(false);
    }
  }

  return (
    <div
      role={item.tipo === "convite" ? "alertdialog" : "status"}
      aria-label={item.tipo === "convite" ? `${pessoa.name} te mandou um convite de amizade` : `${pessoa.name} aceitou seu convite`}
      onMouseEnter={() => setPausado(true)}
      onMouseLeave={() => setPausado(false)}
      onFocus={() => setPausado(true)}
      onBlur={() => setPausado(false)}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 10,
        padding: 13,
        borderRadius: 12,
        background: "#0c0c10",
        boxShadow: `inset 0 0 0 1px ${tint(ACC, 45)}, 0 16px 40px rgba(0,0,0,.55)`,
        animation: "pathr-aviso-entra .2s ease-out",
      }}
    >
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <FotoDePessoa pessoa={pessoa} lado={42} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 13.5, color: TEXT.strong, lineHeight: 1.35 }}>
            {item.tipo === "convite" ? (
              <>
                <strong>{primeiro}</strong> te mandou um convite de amizade
              </>
            ) : (
              <>
                <strong>{primeiro}</strong> aceitou seu convite
              </>
            )}
          </div>
          <div style={{ fontSize: 12, color: ACC3 }}>@{pessoa.username}</div>
        </div>
        <IconButton icon="x" label="Fechar aviso" onClick={onFechar} style={{ alignSelf: "flex-start" }} />
      </div>

      {pessoa.stack.length ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {pessoa.stack.slice(0, 4).map((tecnologia) => (
            <span
              key={tecnologia}
              style={{
                fontSize: 11,
                padding: "2px 7px",
                borderRadius: 5,
                background: "rgba(233,233,237,.07)",
                color: (pessoa.em_comum ?? []).includes(tecnologia) ? C.verde : TEXT.muted,
              }}
            >
              {tecnologia}
            </span>
          ))}
        </div>
      ) : null}

      {erro ? <div style={{ fontSize: 12, color: C.ambar }}>{erro}</div> : null}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {item.tipo === "convite" ? (
          <>
            <button
              type="button"
              className="btn btn-primary"
              disabled={ocupado}
              onClick={() => void responder(() => social.aceitar(item.friendship_id))}
            >
              <Icon name="check" size={15} />
              Aceitar
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={ocupado}
              onClick={() => void responder(() => social.desfazer(item.friendship_id))}
            >
              <Icon name="x" size={15} />
              Recusar
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              dispatch({ type: "navigate", screen: "amigos" });
              onFechar();
            }}
          >
            <Icon name="users" size={15} />
            Ver amigos
          </button>
        )}
      </div>
    </div>
  );
}
