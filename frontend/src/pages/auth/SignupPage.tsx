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
} from "@/components/auth/AuthShell";
import { Icon } from "@/components/ui/icons";
import { useT } from "@/lib/i18n";
import type { City } from "@/api/types";
import { CidadeDoCadastro } from "@/components/auth/CidadeDoCadastro";
import { Turnstile, turnstileLigado } from "@/components/auth/Turnstile";
import { CampoUsername } from "@/components/social/CampoUsername";
import { C, TEXT } from "@/lib/tokens";

/** Idade mínima, igual à do servidor (backend/app/schemas/auth.py). */
const IDADE_MINIMA = 18;

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
  const t = useT();
  const { signup } = useAuth();
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  // O @ digitado pode ser enviado? Vazio pode: o servidor escolhe um.
  const [usernameOk, setUsernameOk] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [birthDate, setBirthDate] = useState("");
  // A cidade só vale escolhida da lista (ou reconhecida): é o que traz a UF
  // certa e o nome como o IBGE escreve.
  const [cidade, setCidade] = useState<City | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  // Anti-robô: o campo isca fica fora da tela (só robô preenche) e o token do
  // Turnstile, quando ligado. A chave troca depois de um envio que falhou,
  // porque o token vale uma vez só.
  const [isca, setIsca] = useState("");
  const [captcha, setCaptcha] = useState<string | null>(null);
  const [chaveDoDesafio, setChaveDoDesafio] = useState(0);

  const missing = problems(password);
  const ready =
    name.trim().length >= 2 &&
    email.includes("@") &&
    missing.length === 0 &&
    birthDate !== "" &&
    cidade !== null &&
    usernameOk &&
    (!turnstileLigado || Boolean(captcha));

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
        city: cidade?.nome ?? "",
        state: cidade?.uf ?? "",
        username: username.trim().replace(/^@+/, ""),
        website: isca,
        captcha: captcha ?? "",
      });
      setDone(detail);
    } catch (caught) {
      setError(errorMessage(caught));
      setCaptcha(null);
      setChaveDoDesafio((valor) => valor + 1);
    } finally {
      setPending(false);
    }
  }

  // Passo seguinte ao envio: a conta existe, mas ninguém entra sem confirmar.
  if (done) {
    return (
      <AuthShell title={t("auth.cadastro.confirme")} subtitle={done} icon="mail">
        <p style={{ fontSize: 13, color: TEXT.faint, margin: "0 0 16.8px" }}>
          {t("auth.cadastro.enviamosLink")}{" "}
          <strong style={{ color: "rgba(233,233,237,.9)" }}>{email.trim()}</strong>.{" "}
          {t("auth.cadastro.validade")}
        </p>
        <button
          type="button"
          className="btn btn-primary btn-block"
          onClick={() => onNavigate("/entrar")}
        >
          {t("auth.cadastro.irParaEntrar")}
          <Icon name="seta" size={17} className="auth-seta" />
        </button>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title={t("auth.cadastro.titulo")}
      icon="userPlus"
      subtitle={t("auth.cadastro.sub")}
      footer={
        <>
          {t("auth.cadastro.jaTem")}{" "}
          <a href="/entrar" onClick={(e) => { e.preventDefault(); onNavigate("/entrar"); }}>
            {t("auth.login.titulo")}
          </a>
        </>
      }
    >
      <form onSubmit={submit} noValidate>
        <FormError>{error}</FormError>

        {/* Campo isca: fora da tela e fora do Tab; leitor de tela não o anuncia.
            Pessoa real nunca preenche; robô que completa tudo, sim. */}
        <div aria-hidden="true" style={{ position: "absolute", left: "-10000px", width: 1, height: 1, overflow: "hidden" }}>
          <label htmlFor="signup-website">{t("auth.cadastro.isca")}</label>
          <input
            id="signup-website"
            name="website"
            type="text"
            tabIndex={-1}
            autoComplete="off"
            value={isca}
            onChange={(event) => setIsca(event.target.value)}
          />
        </div>

        <Field
          id="signup-name"
          label={t("auth.cadastro.nome")}
          icon="user"
          autoComplete="name"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        {/* Logo depois do nome: é dele que sai a sugestão de @, e a pessoa vê a
            ligação entre os dois enquanto ainda está olhando para o nome. */}
        <CampoUsername
          id="signup-username"
          value={username}
          onChange={setUsername}
          nome={name}
          onEstado={setUsernameOk}
        />
        <Field
          id="signup-email"
          label={t("auth.campos.email")}
          icon="mail"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Field
          id="signup-birth-date"
          label={t("auth.cadastro.nascimento")}
          type="date"
          autoComplete="bday"
          hint={`É preciso ter ao menos ${IDADE_MINIMA} anos.`}
          max={maxBirthDate()}
          required
          value={birthDate}
          onChange={(event) => setBirthDate(event.target.value)}
        />

        <CidadeDoCadastro id="signup-city" escolhida={cidade} onEscolher={setCidade} />

        <PasswordField
          id="signup-password"
          label={t("auth.campos.senha")}
          icon="lock"
          autoComplete="new-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />

        <ul
          aria-label={t("auth.cadastro.requisitos")}
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

        <Turnstile key={chaveDoDesafio} onToken={setCaptcha} />

        <button type="submit" className="btn btn-primary btn-block" disabled={pending || !ready}>
          {pending ? null : <Icon name="userPlus" size={17} />}
          {pending ? t("auth.cadastro.criando") : t("auth.cadastro.titulo")}
        </button>
      </form>
    </AuthShell>
  );
}
