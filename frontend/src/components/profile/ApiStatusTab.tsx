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
import { C, HAIRLINE, SIZE, TEXT, tint } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";

const ESTADO: Record<ApiIntegrationState, { rotulo: string; cor: string }> = {
  ok: { rotulo: "Funcionando", cor: C.verde },
  degradada: { rotulo: "Com problema", cor: C.ambar },
  erro: { rotulo: "Fora do ar", cor: C.rosa },
  nao_configurada: { rotulo: "Sem chave", cor: "#8a8d99" },
  sem_verificacao: { rotulo: "Aguardando uso", cor: C.azul },
};

// A ordem dos grupos: do que derruba o app inteiro ao que só tira uma fonte.
const ORDEM = ["Base", "Inteligência artificial", "E-mail", "Idiomas", "Material de estudo", "Vagas"];

function haQuanto(iso: string): string {
  const segundos = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (segundos < 60) return "agora há pouco";
  const minutos = Math.round(segundos / 60);
  return minutos === 1 ? "há 1 minuto" : `há ${minutos} minutos`;
}

const numero = (valor: number) => valor.toLocaleString("pt-BR");

export function ApiStatusTab() {
  const [pedidos, setPedidos] = useState(0);
  const relatorio = useQuery(() => statusApi.apis(pedidos > 0), [pedidos]);

  if (relatorio.loading && !relatorio.data) return <Loading label="Verificando as integrações…" />;
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
                ? `${problemas} ${problemas === 1 ? "integração com problema" : "integrações com problema"}`
                : "Tudo o que está configurado responde"}
            </div>
            <div style={{ fontSize: 12.5, color: TEXT.muted, marginTop: 3 }}>
              {dados.resumo.ok ?? 0} funcionando · {configuradas} de {dados.itens.length} configuradas · verificado{" "}
              {haQuanto(dados.verificado_em)}
            </div>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={verificando || espera > 0}
            onClick={onVerificar}
            title={espera > 0 ? "Cada verificação gasta um pouco de cota." : undefined}
          >
            <Icon name="refresh" size={15} />
            {verificando ? "Verificando…" : espera > 0 ? `Verificar de novo em ${espera}s` : "Verificar agora"}
          </button>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 11.2, marginTop: 11.2 }}>
          {(Object.keys(ESTADO) as ApiIntegrationState[]).map((estado) => (
            <span
              key={estado}
              style={{ fontSize: 11.5, color: TEXT.faint, display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <Ponto cor={ESTADO[estado].cor} />
              {ESTADO[estado].rotulo} · {dados.resumo[estado] ?? 0}
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
        Tavily, Brave e Remotive não são chamados só para checar: gastam crédito ou pedem poucas chamadas. Para
        eles vale o resultado do último uso real. As chaves ficam no servidor e nunca aparecem aqui.
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
  const { rotulo, cor } = ESTADO[item.estado];
  return (
    <div
      role="group"
      aria-label={`${item.nome}: ${rotulo}`}
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "5.6px 14px",
        padding: "11.2px 0",
        borderTop: primeira ? "none" : `1px solid ${HAIRLINE}`,
      }}
    >
      <div style={{ flex: "1 1 280px", minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8.4, flexWrap: "wrap" }}>
          <Ponto cor={cor} />
          <span style={{ fontSize: SIZE.corpo, color: TEXT.full }}>{item.nome}</span>
          {item.modelo ? <span style={{ fontSize: 11, color: TEXT.faint }}>{item.modelo}</span> : null}
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
      <div style={{ textAlign: "right", minWidth: 110 }}>
        <div style={{ fontSize: 12.5, color: cor }}>{rotulo}</div>
        {item.latencia_ms !== null ? (
          <div style={{ fontSize: 11, color: TEXT.faint }}>{numero(item.latencia_ms)} ms</div>
        ) : null}
      </div>
    </div>
  );
}

function Uso({ item }: { item: ApiIntegration }) {
  const uso = item.uso;
  if (!uso) return null;
  const estilo = { fontSize: 11.5, color: TEXT.faint, marginTop: 5, paddingLeft: 16.4 };

  if (uso.hoje) {
    return (
      <div style={estilo}>
        Hoje: {numero(uso.hoje.requisicoes)} {uso.hoje.requisicoes === 1 ? "requisição" : "requisições"} ·{" "}
        {numero(uso.hoje.tokens)} tokens
      </div>
    );
  }
  if (uso.limite) {
    const pct = Math.min(100, Math.round(((uso.usados ?? 0) / uso.limite) * 100));
    return (
      <div style={estilo}>
        <div>
          {numero(uso.usados ?? 0)} de {numero(uso.limite)} {uso.unidade} ({pct}%)
        </div>
        <div
          role="meter"
          aria-label={`Uso de ${item.nome}`}
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
        {numero(uso.restantes)} {uso.unidade}
      </div>
    );
  }
  return null;
}
