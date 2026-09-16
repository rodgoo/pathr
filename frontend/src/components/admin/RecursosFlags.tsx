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

const OPCOES: readonly SegmentedOption<EstadoDoRecurso>[] = [
  { value: "todos", label: "Todos" },
  { value: "admin", label: "Admin" },
  { value: "ninguem", label: "Ninguém" },
];

const EXPLICA: Record<EstadoDoRecurso, string> = {
  todos: "Ligado para todos os usuários.",
  admin: "Só administradores veem.",
  ninguem: "Desligado para todo mundo.",
};

const COR: Record<EstadoDoRecurso, string> = {
  todos: C.verde,
  admin: C.azul,
  ninguem: TEXT.faint,
};

function LinhaDoRecurso({ recurso, onTrocado }: { recurso: RecursoFlag; onTrocado: (estado: EstadoDoRecurso) => void }) {
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
      setErro("Não consegui salvar. Tente de novo.");
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
            mudado do padrão
          </span>
        ) : null}
      </div>
      <p style={{ margin: 0, fontSize: 12.5, color: TEXT.muted, maxWidth: "64ch", lineHeight: 1.5 }}>
        {recurso.description}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px 12px" }}>
        <Segmented
          name={`recurso-${recurso.key}`}
          label={`Quem vê ${recurso.label}`}
          options={OPCOES}
          value={estado}
          onChange={(novo) => void trocar(novo)}
          style={{ maxWidth: 320 }}
        />
        <span style={{ fontSize: 12, color: COR[estado] }}>
          {salvar.pending ? "Salvando…" : EXPLICA[estado]}
        </span>
      </div>
      {erro ? <span role="alert" style={{ fontSize: 12, color: C.ambar }}>{erro}</span> : null}
    </li>
  );
}

export function RecursosFlags() {
  const recursos = useQuery(() => api.getSemCache<RecursoFlag[]>("/admin/recursos"), []);

  return (
    <Panel pad={16.8}>
      <Kicker tone="muted" style={{ display: "block", marginBottom: 4 }}>
        Recursos
      </Kicker>
      <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 8px", maxWidth: "64ch" }}>
        Ligue cada recurso para <strong style={{ color: C.verde, fontWeight: 500 }}>todos os usuários</strong>, só para{" "}
        <strong style={{ color: C.azul, fontWeight: 500 }}>administradores</strong>, ou para{" "}
        <strong style={{ fontWeight: 500 }}>ninguém</strong>. A mudança vale na próxima vez que a pessoa abrir a tela.
      </p>

      {recursos.loading ? <Loading label="Buscando recursos…" /> : null}
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
