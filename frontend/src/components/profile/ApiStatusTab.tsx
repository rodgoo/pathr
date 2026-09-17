/**
 * O estado de cada integração externa do app.
 *
 * Cada linha diz três coisas: se o serviço responde, o que ele sustenta no
 * app (para quem lê saber o que parou de funcionar) e, quando o provedor
 * informa, quanto já se usou da cota. A chave nunca vem do servidor.
 *
 * "Verificar agora" existe, mas o servidor segura o intervalo mínimo: cada
 * verificação gasta um pouco de cota do YouTube e da Adzuna.
 */

import { useState } from "react";
import { status as statusApi } from "@/api/endpoints";
import type { ApiIntegration, ApiIntegrationState, ApiStatusReport } from "@/api/types";
import { useQuery } from "@/hooks/useApi";
import { useIdioma, useT, type Traduzir } from "@/lib/i18n";
import { C, HAIRLINE, SIZE, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";

// O rótulo de cada estado vem do dicionário (apiStatus.estado.<estado>).
const CORES: Record<ApiIntegrationState, string> = {
  ok: C.verde,
  degradada: C.ambar,
  erro: C.rosa,
  nao_configurada: "#8a8d99",
  sem_verificacao: C.azul,
};

const rotuloEstado = (estado: ApiIntegrationState, t: Traduzir) => t(`apiStatus.estado.${estado}`);

// A ordem dos grupos: do que derruba o app inteiro ao que só tira uma fonte.
// São os valores de `categoria` que o servidor devolve — não se traduzem, senão
// o filtro por categoria deixa de casar.
const ORDEM = ["Base", "Inteligência artificial", "E-mail", "Idiomas", "Material de estudo", "Vagas"];

function haQuanto(iso: string, t: Traduzir): string {
  const segundos = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (segundos < 60) return t("apiStatus.agoraHaPouco");
  const minutos = Math.round(segundos / 60);
  return minutos === 1 ? t("apiStatus.haUmMinuto") : t("apiStatus.haMinutos", { n: minutos });
}

const numero = (valor: number, idioma: string) => valor.toLocaleString(idioma);

export function ApiStatusTab() {
  const t = useT();
  const [pedidos, setPedidos] = useState(0);
  const relatorio = useQuery(() => statusApi.apis(pedidos > 0), [pedidos]);

  if (relatorio.loading && !relatorio.data) return <Loading label={t("apiStatus.verificandoLoading")} />;
  if (relatorio.error) return <ErrorState message={relatorio.error} onRetry={relatorio.reload} />;
  if (!relatorio.data) return null;

  return (
    <Relatorio
      dados={relatorio.data}
      verificando={relatorio.loading}
      onVerificar={() => setPedidos((vezes) => vezes + 1)}
    />
  );
}

function Relatorio({
  dados,
  verificando,
  onVerificar,
}: {
  dados: ApiStatusReport;
  verificando: boolean;
  onVerificar: () => void;
}) {
  const t = useT();
  const grupos = ORDEM.map((categoria) => ({
    categoria,
    itens: dados.itens.filter((item) => item.categoria === categoria),
  })).filter((grupo) => grupo.itens.length > 0);
  const configuradas = dados.itens.filter((item) => item.configurada).length;
  const problemas = (dados.resumo.erro ?? 0) + (dados.resumo.degradada ?? 0);
  const espera = dados.pode_atualizar_em_s;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <Panel pad={16.8}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 11.2 }}>
          <div style={{ flex: "1 1 260px" }}>
            <div style={{ fontSize: SIZE.titulo, color: problemas ? C.ambar : C.verde }}>
              {problemas
                ? problemas === 1
                  ? t("apiStatus.problemaSing", { n: problemas })
                  : t("apiStatus.problemaPlural", { n: problemas })
                : t("apiStatus.tudoResponde")}
            </div>
            <div style={{ fontSize: 12.5, color: TEXT.muted, marginTop: 3 }}>
              {t("apiStatus.resumoLinha", {
                ok: dados.resumo.ok ?? 0,
                conf: configuradas,
                total: dados.itens.length,
                quando: haQuanto(dados.verificado_em, t),
              })}
            </div>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={verificando || espera > 0}
            onClick={onVerificar}
            title={espera > 0 ? t("apiStatus.gastaCota") : undefined}
          >
            <Icon name="refresh" size={15} />
            {verificando
              ? t("apiStatus.verificando")
              : espera > 0
                ? t("apiStatus.verificarEm", { s: espera })
                : t("apiStatus.verificarAgora")}
          </button>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 11.2, marginTop: 11.2 }}>
          {(Object.keys(CORES) as ApiIntegrationState[]).map((estado) => (
            <span
              key={estado}
              style={{ fontSize: 11.5, color: TEXT.faint, display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <Ponto cor={CORES[estado]} />
              {rotuloEstado(estado, t)} · {dados.resumo[estado] ?? 0}
            </span>
          ))}
        </div>
      </Panel>

      {grupos.map((grupo) => (
        <Panel key={grupo.categoria} pad={16.8}>
          <section aria-label={grupo.categoria}>
            <Kicker style={{ display: "block", marginBottom: 5.6 }}>{grupo.categoria}</Kicker>
            {grupo.itens.map((item, posicao) => (
              <Linha key={item.id} item={item} primeira={posicao === 0} />
            ))}
          </section>
        </Panel>
      ))}

      <p style={{ margin: 0, fontSize: 11.5, color: TEXT.faint, maxWidth: "76ch", lineHeight: 1.5 }}>
        {t("apiStatus.rodape")}
      </p>
    </div>
  );
}

function Ponto({ cor }: { cor: string }) {
  return (
    <span
      aria-hidden
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: 4,
        background: cor,
        boxShadow: `0 0 0 3px ${tint(cor, 18)}`,
        flex: "none",
      }}
    />
  );
}

function Linha({ item, primeira }: { item: ApiIntegration; primeira: boolean }) {
  const t = useT();
  const { idioma } = useIdioma();
  const rotulo = rotuloEstado(item.estado, t);
  const cor = CORES[item.estado];
  return (
    <div
      role="group"
      aria-label={t("apiStatus.linhaAria", { nome: item.nome, estado: rotulo })}
      style={{
        padding: "11.2px 0",
        borderTop: primeira ? "none" : `1px solid ${HAIRLINE}`,
      }}
    >
      <div style={{ minWidth: 0 }}>
        {/* Estado e tempo de resposta na linha do nome, à direita. Numa coluna
            própria, no celular ela descia para baixo da descrição e ficava
            flutuando no meio do cartão. */}
        <div style={{ display: "flex", alignItems: "baseline", gap: 8.4 }}>
          <span style={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: 8.4, flexWrap: "wrap" }}>
            <Ponto cor={cor} />
            <span style={{ fontSize: SIZE.corpo, color: TEXT.full }}>{item.nome}</span>
            {item.modelo ? <span style={{ fontSize: 11, color: TEXT.faint }}>{item.modelo}</span> : null}
          </span>
          <span style={{ flex: "none", textAlign: "right", whiteSpace: "nowrap" }}>
            <span style={{ fontSize: 12.5, color: cor }}>{rotulo}</span>
            {item.latencia_ms !== null ? (
              <span style={{ fontSize: 11, color: TEXT.faint }}> · {numero(item.latencia_ms, idioma)} ms</span>
            ) : null}
          </span>
        </div>
        <div style={{ fontSize: 12, color: TEXT.muted, marginTop: 3, paddingLeft: 16.4 }}>{item.para_que}</div>
        {item.detalhe ? (
          <div
            style={{ fontSize: 12, color: item.estado === "ok" ? TEXT.faint : cor, marginTop: 3, paddingLeft: 16.4 }}
          >
            {item.detalhe}
          </div>
        ) : null}
        <Uso item={item} />
      </div>
    </div>
  );
}

function Uso({ item }: { item: ApiIntegration }) {
  const t = useT();
  const { idioma } = useIdioma();
  const uso = item.uso;
  if (!uso) return null;
  const estilo = { fontSize: 11.5, color: TEXT.faint, marginTop: 5, paddingLeft: 16.4 };

  if (uso.hoje) {
    return (
      <div style={estilo}>
        {t("apiStatus.hoje", {
          req: numero(uso.hoje.requisicoes, idioma),
          rotulo:
            uso.hoje.requisicoes === 1
              ? t("apiStatus.requisicaoSing")
              : t("apiStatus.requisicaoPlural"),
          tokens: numero(uso.hoje.tokens, idioma),
        })}
      </div>
    );
  }
  if (uso.limite) {
    const pct = Math.min(100, Math.round(((uso.usados ?? 0) / uso.limite) * 100));
    return (
      <div style={estilo}>
        <div>
          {t("apiStatus.deLimitePct", {
            usados: numero(uso.usados ?? 0, idioma),
            limite: numero(uso.limite, idioma),
            unidade: uso.unidade ?? "",
            pct,
          })}
        </div>
        <div
          role="meter"
          aria-label={t("apiStatus.usoDe", { nome: item.nome })}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          style={{ height: 4, maxWidth: 240, borderRadius: 2, background: "rgba(233,233,237,.1)", marginTop: 4 }}
        >
          <div
            style={{ width: `${pct}%`, height: "100%", borderRadius: 2, background: pct >= 90 ? C.ambar : C.verde }}
          />
        </div>
      </div>
    );
  }
  if (uso.restantes !== undefined) {
    return (
      <div style={estilo}>
        {numero(uso.restantes, idioma)} {uso.unidade}
      </div>
    );
  }
  return null;
}
