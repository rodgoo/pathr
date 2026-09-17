/**
 * Recursos: liga cada funcionalidade do app para Todos, só Admin, ou Ninguém.
 *
 * A tela é só do super admin (o SettingsPage decide se mostra a aba). Quem
 * DECIDE o acesso é o servidor: aqui a gente lê `GET /admin/recursos`, mostra
 * um toggle de três estados por recurso e grava a escolha em
 * `PUT /admin/recursos/{chave}`. O que cada usuário enxerga vem de
 * `GET /features`, resolvido no backend — esta tela nunca aplica a regra.
 *
 * Componente autossuficiente de propósito (chama `api` direto, com os tipos
 * declarados aqui): assim ele compila mesmo antes de ser montado no
 * SettingsPage e antes de os endpoints entrarem em api/endpoints.ts.
 */

import { useState } from "react";
import { api } from "@/api/client";
import { useMutation, useQuery } from "@/hooks/useApi";
import { useT } from "@/lib/i18n";
import { Segmented, type SegmentedOption } from "@/components/ui/Segmented";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";
import { C, TEXT, tint } from "@/lib/tokens";

type EstadoDoRecurso = "todos" | "admin" | "ninguem";

interface RecursoFlag {
  key: string;
  label: string;
  description: string;
  state: EstadoDoRecurso;
  default: EstadoDoRecurso;
}

const COR: Record<EstadoDoRecurso, string> = {
  todos: C.verde,
  admin: C.azul,
  ninguem: TEXT.faint,
};

function LinhaDoRecurso({ recurso, onTrocado }: { recurso: RecursoFlag; onTrocado: (estado: EstadoDoRecurso) => void }) {
  const t = useT();
  const opcoes: readonly SegmentedOption<EstadoDoRecurso>[] = [
    { value: "todos", label: t("recursos.todos") },
    { value: "admin", label: t("recursos.admin") },
    { value: "ninguem", label: t("recursos.ninguem") },
  ];
  const explica: Record<EstadoDoRecurso, string> = {
    todos: t("recursos.explicaTodos"),
    admin: t("recursos.explicaAdmin"),
    ninguem: t("recursos.explicaNinguem"),
  };
  const [estado, setEstado] = useState<EstadoDoRecurso>(recurso.state);
  const [erro, setErro] = useState<string | null>(null);
  const salvar = useMutation((novo: EstadoDoRecurso) =>
    api.put<{ key: string; state: EstadoDoRecurso }>(`/admin/recursos/${encodeURIComponent(recurso.key)}`, {
      state: novo,
    }),
  );

  async function trocar(novo: EstadoDoRecurso) {
    if (novo === estado) return;
    const anterior = estado;
    setEstado(novo); // otimista
    setErro(null);
    const ok = await salvar.run(novo);
    if (ok) {
      onTrocado(novo);
    } else {
      setEstado(anterior); // desfaz se o servidor recusou
      setErro(t("recursos.erroSalvar"));
    }
  }

  return (
    <li
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: "12px 0",
        borderTop: "1px solid rgba(233,233,237,.1)",
      }}
    >
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 14.5, color: TEXT.full }}>{recurso.label}</span>
        {estado !== recurso.default ? (
          <span
            style={{ fontSize: 11, color: C.ambar, padding: "1px 7px", borderRadius: 999, background: tint(C.ambar, 12) }}
          >
            {t("recursos.mudadoDoPadrao")}
          </span>
        ) : null}
      </div>
      <p style={{ margin: 0, fontSize: 12.5, color: TEXT.muted, maxWidth: "64ch", lineHeight: 1.5 }}>
        {recurso.description}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px 12px" }}>
        <Segmented
          name={`recurso-${recurso.key}`}
          label={t("recursos.quemVe", { nome: recurso.label })}
          options={opcoes}
          value={estado}
          onChange={(novo) => void trocar(novo)}
          style={{ maxWidth: 320 }}
        />
        <span style={{ fontSize: 12, color: COR[estado] }}>
          {salvar.pending ? t("recursos.salvando") : explica[estado]}
        </span>
      </div>
      {erro ? <span role="alert" style={{ fontSize: 12, color: C.ambar }}>{erro}</span> : null}
    </li>
  );
}

export function RecursosFlags() {
  const t = useT();
  const recursos = useQuery(() => api.getSemCache<RecursoFlag[]>("/admin/recursos"), []);

  return (
    <Panel pad={16.8}>
      <Kicker tone="muted" style={{ display: "block", marginBottom: 4 }}>
        {t("recursos.titulo")}
      </Kicker>
      <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 8px", maxWidth: "64ch" }}>
        {t("recursos.explicaPre")}
        <strong style={{ color: C.verde, fontWeight: 500 }}>{t("recursos.todosUsuarios")}</strong>
        {t("recursos.explicaMid1")}
        <strong style={{ color: C.azul, fontWeight: 500 }}>{t("recursos.administradores")}</strong>
        {t("recursos.explicaMid2")}
        <strong style={{ fontWeight: 500 }}>{t("recursos.ninguemForte")}</strong>
        {t("recursos.explicaFim")}
      </p>

      {recursos.loading ? <Loading label={t("recursos.buscando")} /> : null}
      {recursos.error ? <ErrorState message={recursos.error} onRetry={recursos.reload} /> : null}
      {recursos.data && recursos.data.length > 0 ? (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {recursos.data.map((recurso) => (
            <LinhaDoRecurso
              key={recurso.key}
              recurso={recurso}
              onTrocado={(estado) =>
                recursos.set((atual) =>
                  (atual ?? []).map((item) => (item.key === recurso.key ? { ...item, state: estado } : item)),
                )
              }
            />
          ))}
        </ul>
      ) : null}
    </Panel>
  );
}
