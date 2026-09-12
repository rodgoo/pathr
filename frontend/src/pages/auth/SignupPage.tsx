/**
 * Cadastro.
 *
 * As regras de senha aparecem ANTES de a pessoa enviar, e são as mesmas que o
 * servidor aplica (backend/app/security.py). Repetir a regra nos dois lados é
 * duplicação consciente: o cliente evita uma ida ao servidor para dizer o
 * óbvio, e o servidor é quem realmente decide.
 *
 * O cadastro NÃO loga. Termina numa tela dizendo para abrir o e-mail, porque
 * a entrada passou a exigir confirmação — ver a regra no backend, em
 * routers/auth.py.
 */

import { useState, type FormEvent } from "react";
import { errorMessage, useAuth } from "@/hooks/useAuth";
import {
  AuthShell,
  Field,
  FormError,
  PasswordField,
  SelectField,
} from "@/components/auth/AuthShell";
import { UFS } from "@/lib/ufs";
import { C, TEXT } from "@/lib/tokens";

/** Idade mínima, igual à do servidor (backend/app/schemas/auth.py). */
const IDADE_MINIMA = 14;

function problems(password: string): string[] {
  const found: string[] = [];
  if (password.length < 10) found.push("ao menos 10 caracteres");
  if (!/[a-zA-Z]/.test(password)) found.push("ao menos uma letra");
  if (!/\d/.test(password)) found.push("ao menos um número");
  return found;
}

/** A data mais recente que ainda satisfaz a idade mínima. */
function maxBirthDate(): string {
  const hoje = new Date();
  hoje.setFullYear(hoje.getFullYear() - IDADE_MINIMA);
  return hoje.toISOString().slice(0, 10);
}

export function SignupPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  const { signup } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  const missing = problems(password);
  const ready =
    name.trim().length >= 2 &&
    email.includes("@") &&
    missing.length === 0 &&
    birthDate !== "" &&
    city.trim().length >= 2 &&
    state !== "";

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!ready) return;
    setPending(true);
    setError(null);
    try {
      const detail = await signup({
        name: name.trim(),
        email: email.trim(),
        password,
        birth_date: birthDate,
        city: city.trim(),
        state,
      });
      setDone(detail);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setPending(false);
    }
  }

  // Passo seguinte ao envio: a conta existe, mas ninguém entra sem confirmar.
  if (done) {
    return (
      <AuthShell title="Confirme seu e-mail" subtitle={done}>
        <p style={{ fontSize: 13, color: TEXT.faint, margin: "0 0 16.8px" }}>
          Enviamos um link para <strong style={{ color: "rgba(233,233,237,.9)" }}>{email.trim()}</strong>.
          O link vale por três dias. Se não chegar, olhe também o spam.
        </p>
        <button
          type="button"
          className="btn btn-primary btn-block"
          onClick={() => onNavigate("/entrar")}
        >
          Ir para entrar
        </button>
      </AuthShell>
    );
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
          id="signup-birth-date"
          label="Data de nascimento"
          type="date"
          autoComplete="bday"
          hint={`É preciso ter ao menos ${IDADE_MINIMA} anos.`}
          max={maxBirthDate()}
          required
          value={birthDate}
          onChange={(event) => setBirthDate(event.target.value)}
        />

        <div style={{ display: "grid", gridTemplateColumns: "1fr 96px", gap: 8.4 }}>
          <Field
            id="signup-city"
            label="Cidade onde mora"
            autoComplete="address-level2"
            required
            value={city}
            onChange={(event) => setCity(event.target.value)}
          />
          <SelectField
            id="signup-state"
            label="UF"
            required
            placeholder="—"
            value={state}
            onChange={setState}
            options={UFS.map((uf) => ({ value: uf, label: uf }))}
          />
        </div>

        <PasswordField
          id="signup-password"
          label="Senha"
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
