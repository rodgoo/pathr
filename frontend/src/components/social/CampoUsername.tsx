/**
 * O campo do @, com a resposta de "está livre?" enquanto se digita.
 *
 * Descobrir que o nome já tem dono só no envio do formulário é voltar três
 * campos atrás e tentar de novo às cegas. Aqui a resposta chega enquanto a
 * pessoa ainda está no campo, e quando o nome está ocupado as alternativas
 * aparecem prontas para tocar — as mesmas que o servidor aceitaria.
 *
 * No cadastro o campo pode ficar vazio: a conta nasce com um @ derivado do
 * nome. Mas vazio não é invisível — a tela diz QUAL @ a pessoa vai ganhar,
 * para ninguém descobrir depois que virou `@rodrigo_carvalho2`.
 */

import { useEffect, useRef, useState } from "react";
import { social } from "@/api/endpoints";
import type { DisponibilidadeUsername } from "@/api/types";
import { useT } from "@/lib/i18n";
import { C, TEXT } from "@/lib/tokens";
import { Chip } from "@/components/ui/Chip";

/** Espera entre a última tecla e a consulta: uma por pausa, não uma por letra. */
const ESPERA_MS = 400;

export function CampoUsername({
  id,
  value,
  onChange,
  nome = "",
  atual,
  label,
  onEstado,
}: {
  id: string;
  value: string;
  onChange: (valor: string) => void;
  /** O nome completo, para sugerir e para prever o @ de quem deixa vazio. */
  nome?: string;
  /** O @ que a pessoa já tem: ele é "livre" para ela, ainda que tenha dono. */
  atual?: string;
  label?: string;
  /** Avisa o formulário se o que está digitado pode ser enviado. */
  onEstado?: (pronto: boolean) => void;
}) {
  const t = useT();
  const [resposta, setResposta] = useState<DisponibilidadeUsername | null>(null);
  const [consultando, setConsultando] = useState(false);
  const pedido = useRef(0);

  const limpo = value.trim().replace(/^@+/, "").toLowerCase();
  const ehOAtual = Boolean(atual) && limpo === atual;

  useEffect(() => {
    const numero = ++pedido.current;
    if (ehOAtual) {
      setResposta(null);
      setConsultando(false);
      onEstado?.(true);
      return undefined;
    }
    // Vazio só consulta se há nome para prever o @ automático.
    if (!limpo && nome.trim().length < 2) {
      setResposta(null);
      onEstado?.(true);
      return undefined;
    }
    setConsultando(true);
    const timer = window.setTimeout(() => {
      social
        .disponivel(limpo, nome.trim())
        .then((dados) => {
          // Resposta de uma tecla antiga chegando depois da nova: descarta.
          if (numero !== pedido.current) return;
          setResposta(dados);
          onEstado?.(!limpo || dados.disponivel);
        })
        .catch(() => {
          if (numero !== pedido.current) return;
          // Sem resposta, deixa enviar: o servidor confere de novo no cadastro.
          setResposta(null);
          onEstado?.(true);
        })
        .finally(() => {
          if (numero === pedido.current) setConsultando(false);
        });
    }, ESPERA_MS);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [limpo, nome, ehOAtual]);

  const livre = Boolean(limpo) && resposta?.disponivel;
  const ocupado = Boolean(limpo) && resposta && !resposta.disponivel;

  return (
    <div className="field" style={{ marginBottom: 11.2 }}>
      <label htmlFor={id}>{label ?? t("amigos.campoUsername.label")}</label>
      <div style={{ position: "relative" }}>
        <span
          aria-hidden
          style={{
            position: "absolute",
            left: 10,
            top: "50%",
            transform: "translateY(-50%)",
            color: TEXT.faint,
            fontSize: 14,
            pointerEvents: "none",
          }}
        >
          @
        </span>
        <input
          id={id}
          className="input"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          maxLength={25}
          placeholder={!limpo && resposta?.sugestoes[0] ? resposta.sugestoes[0] : t("amigos.campoUsername.placeholder")}
          value={value}
          aria-invalid={ocupado ? true : undefined}
          aria-describedby={`${id}-status`}
          onChange={(evento) => onChange(evento.target.value.replace(/\s/g, ""))}
          style={{ paddingLeft: 24 }}
        />
      </div>

      <div id={`${id}-status`} role="status" style={{ fontSize: 11.5, marginTop: 5, minHeight: 16 }}>
        {consultando ? <span style={{ color: TEXT.faint }}>{t("amigos.campoUsername.conferindo")}</span> : null}
        {!consultando && ehOAtual ? <span style={{ color: TEXT.faint }}>{t("amigos.campoUsername.seuAtual")}</span> : null}
        {!consultando && livre ? <span style={{ color: C.verde }}>@{limpo} {t("amigos.campoUsername.estaLivre")}</span> : null}
        {!consultando && !limpo && resposta?.sugestoes[0] ? (
          <span style={{ color: TEXT.faint }}>
            {t("amigos.campoUsername.seVazio")} <strong style={{ color: TEXT.muted }}>@{resposta.sugestoes[0]}</strong>.
          </span>
        ) : null}
        {!consultando && ocupado ? (
          <span style={{ color: C.ambar }}>{resposta?.problema}</span>
        ) : null}
      </div>

      {!consultando && ocupado && resposta && resposta.sugestoes.length > 0 ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginTop: 6 }}>
          {resposta.sugestoes.map((sugestao) => (
            <Chip key={sugestao} active={false} title={t("amigos.campoUsername.usar", { usuario: sugestao })} onClick={() => onChange(sugestao)}>
              @{sugestao}
            </Chip>
          ))}
        </div>
      ) : null}
    </div>
  );
}
