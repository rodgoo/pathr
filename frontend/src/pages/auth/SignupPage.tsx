/**
 * Cadastro.
 *
 * As regras de senha aparecem ANTES de a pessoa enviar, e são as mesmas que o
 * servidor aplica (backend/app/security.py). Repetir a regra nos dois lados é
 * duplicação consciente: o cliente evita uma ida ao servidor para dizer o
 * óbvio, e o servidor é quem realmente decide.
 */

import { useState, type FormEvent } from "react";
import { errorMessage, useAuth } from "@/hooks/useAuth";
import { AuthShell, Field, FormError } from "@/components/auth/AuthShell";
import { C, TEXT } from "@/lib/tokens";

function problems(password: string): string[] {
  const found: string[] = [];
  if (password.length < 10) found.push("ao menos 10 caracteres");
  if (!/[a-zA-Z]/.test(password)) found.push("ao menos uma letra");
  if (!/\d/.test(password)) found.push("ao menos um número");
  return found;
}

export function SignupPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  const { signup } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const missing = problems(password);
  const ready = name.trim().length >= 2 && email.includes("@") && missing.length === 0;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!ready) return;
    setPending(true);
    setError(null);
    try {
      await signup(name.trim(), email.trim(), password);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthShell
      title="Criar conta"
      subtitle="Envie seu currículo e o plano sai pronto, dividido em fases."
      footer={
        <>
          Já tem conta?{" "}
          <a href="/entrar" onClick={(e) => { e.preventDefault(); onNavigate("/entrar"); }}>
            Entrar
          </a>
        </>
      }
    >
      <form onSubmit={submit} noValidate>
        <FormError>{error}</FormError>

        <Field
          id="signup-name"
          label="Como quer ser chamado"
          autoComplete="name"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <Field
          id="signup-email"
          label="E-mail"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Field
          id="signup-password"
          label="Senha"
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />

        <ul
          aria-label="Requisitos da senha"
          style={{ listStyle: "none", padding: 0, margin: "0 0 14px", fontSize: 12 }}
        >
          {["ao menos 10 caracteres", "ao menos uma letra", "ao menos um número"].map((rule) => {
            const ok = password.length > 0 && !missing.includes(rule);
            return (
              <li key={rule} style={{ color: ok ? C.verde : TEXT.faint, display: "flex", gap: 6 }}>
                <span aria-hidden>{ok ? "✓" : "•"}</span>
                {rule}
              </li>
            );
          })}
        </ul>

        <button type="submit" className="btn btn-primary btn-block" disabled={pending || !ready}>
          {pending ? "Criando…" : "Criar conta"}
        </button>
      </form>
    </AuthShell>
  );
}
