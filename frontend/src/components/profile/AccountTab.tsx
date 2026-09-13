/**
 * Conta: nome, preferências e senha.
 *
 * O e-mail aparece mas não é editável: trocá-lo exigiria confirmar o novo
 * endereço antes de valer, e esse fluxo ainda não existe no backend. Mostrar
 * um campo que não salva seria pior que mostrá-lo bloqueado.
 */

import { useEffect, useRef, useState, type FormEvent } from "react";
import { auth as authApi, profile as profileApi, social } from "@/api/endpoints";
import { useAuth } from "@/hooks/useAuth";
import { useMutation, useQuery } from "@/hooks/useApi";
import { C, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { ErrorState, Loading } from "@/components/ui/States";
import { PasswordField } from "@/components/auth/AuthShell";
import { Kicker, Panel } from "@/components/ui/primitives";
import { Select } from "@/components/ui/Select";
import { PasskeysPanel } from "./PasskeysPanel";
import { CampoUsername } from "@/components/social/CampoUsername";

/**
 * Os degraus de senioridade que o app entende.
 *
 * Uma lista fechada, e não texto livre: a senioridade entra no cálculo do
 * plano e é comparada com o que o objetivo exige. "pleno", "Pleno" e "PL"
 * digitados à mão seriam três valores diferentes para a mesma coisa, e o
 * roadmap sairia calibrado errado sem ninguém entender por quê.
 */
// O vocabulário é o de `pathr_profile.seniority` (ver backend/app/models.py).
/** O que se lê na tela. O valor gravado continua sendo o do vocabulário. */
const ROTULO_SENIORIDADE: Record<(typeof SENIORIDADES)[number], string> = {
  estagio: "Estágio",
  junior: "Júnior",
  pleno: "Pleno",
  senior: "Sênior",
  especialista: "Especialista",
  lideranca: "Liderança",
};

const SENIORIDADES = ["estagio", "junior", "pleno", "senior", "especialista", "lideranca"] as const;

export function AccountTab() {
  const { user, refresh } = useAuth();
  const profile = useQuery(() => profileApi.get(), []);
  const [name, setName] = useState(user?.name ?? "");
  const [username, setUsername] = useState(user?.username ?? "");
  const [usernameOk, setUsernameOk] = useState(true);
  const [role, setRole] = useState("");
  const [seniority, setSeniority] = useState("");
  const [years, setYears] = useState("");
  const [hours, setHours] = useState("8");
  const [saved, setSaved] = useState(false);

  const save = useMutation(async () => {
    await authApi.me();
    await profileApi.updateAccount({ name: name.trim() });
    const novoUsername = username.trim().replace(/^@+/, "").toLowerCase();
    // Só quando mudou: regravar o mesmo @ gastaria uma consulta e, se outra
    // pessoa tivesse o nome parecido, ainda poderia falhar à toa.
    if (novoUsername && novoUsername !== user?.username) {
      await social.trocarUsername(novoUsername);
    }
    await profileApi.update({
      current_role: role.trim() || null,
      seniority: seniority.trim() || null,
      // Vazio é "não quero dizer", e é diferente de zero — que é a resposta
      // legítima de quem está começando agora.
      years_experience: years.trim() === "" ? null : Number(years),
      weekly_hours: Number(hours) || 8,
    });
    await refresh();
  });

  /**
   * O formulário recebe o que está gravado UMA vez.
   *
   * Antes a condição era "ainda não tem cargo preenchido", o que errava dos
   * dois lados: quem nunca preencheu o cargo nunca via as próprias horas
   * (ficavam em 8, o padrão), e quem apagava o campo para digitar outro tinha
   * o valor antigo escrito de volta por cima na renderização seguinte.
   */
  const hidratado = useRef(false);
  useEffect(() => {
    if (hidratado.current || !profile.data) return;
    hidratado.current = true;
    setRole(profile.data.current_role ?? "");
    setSeniority(profile.data.seniority ?? "");
    setYears(
      profile.data.years_experience === null ? "" : String(profile.data.years_experience),
    );
    setHours(String(profile.data.weekly_hours));
  }, [profile.data]);

  if (profile.loading) return <Loading />;
  if (profile.error) return <ErrorState message={profile.error} onRetry={profile.reload} />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaved(false);
    const result = await save.run();
    if (result !== null) setSaved(true);
  }

  return (
    <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <Panel pad={16.8}>
        <Kicker style={{ display: "block", marginBottom: 14 }}>Dados pessoais</Kicker>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))",
            gap: 11.2,
          }}
        >
          <div className="field">
            <label htmlFor="account-name">Como quer ser chamado</label>
            <input
              id="account-name"
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <CampoUsername
            id="account-username"
            value={username}
            onChange={setUsername}
            nome={name}
            atual={user?.username}
            onEstado={setUsernameOk}
          />
          <div className="field">
            <label htmlFor="account-email">E-mail</label>
            <input id="account-email" className="input" value={user?.email ?? ""} disabled />
          </div>
          <div className="field">
            <label htmlFor="account-role">Cargo atual</label>
            <input
              id="account-role"
              className="input"
              placeholder="ex: Desenvolvedor frontend"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="account-seniority">Senioridade</label>
            <Select
              id="account-seniority"
              value={seniority}
              onChange={setSeniority}
              placeholder="Não informar"
              options={[
                // Uma opção explícita para desfazer: sem ela, quem escolheu
                // uma senioridade não teria como voltar a não informar.
                { value: "", label: "Não informar" },
                ...SENIORIDADES.map((nivel) => ({ value: nivel, label: ROTULO_SENIORIDADE[nivel] })),
              ]}
            />
          </div>
          <div className="field">
            <label htmlFor="account-years">Tempo de experiência (anos)</label>
            <input
              id="account-years"
              className="input"
              type="number"
              min={0}
              max={60}
              step={0.5}
              placeholder="ex: 3"
              value={years}
              onChange={(event) => setYears(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="account-hours">Horas de estudo por semana</label>
            <input
              id="account-hours"
              className="input"
              type="number"
              min={1}
              max={80}
              value={hours}
              onChange={(event) => setHours(event.target.value)}
            />
          </div>
        </div>

        {save.error ? <ErrorState message={save.error} /> : null}

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, marginTop: 14, alignItems: "center" }}>
          <button type="submit" className="btn btn-primary" disabled={save.pending || !usernameOk}>
            <Icon name="check" size={15} />
            {save.pending ? "Salvando…" : "Salvar alterações"}
          </button>
          {saved ? <span style={{ fontSize: 12.5, color: C.verde }}>Salvo.</span> : null}
        </div>
      </Panel>

      <ChangePassword />
      <PasskeysPanel />
      <Sessions />
    </form>
  );
}


/**
 * Troca de senha.
 *
 * Pede a senha atual porque quem estiver numa sessão sequestrada não deveria
 * conseguir trocar a senha e expulsar o dono. O backend mantém ESTA sessão
 * viva e derruba as outras.
 */
function ChangePassword() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [done, setDone] = useState(false);
  const change = useMutation(() => authApi.changePassword(currentPassword, newPassword));

  return (
    <Panel pad={16.8}>
      <Kicker style={{ display: "block", marginBottom: 14 }}>Senha</Kicker>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))",
          gap: 11.2,
        }}
      >
        <PasswordField
          id="current-password"
          label="Senha atual"
          autoComplete="current-password"
          value={currentPassword}
          onChange={(event) => setCurrentPassword(event.target.value)}
        />
        <PasswordField
          id="new-password"
          label="Nova senha"
          autoComplete="new-password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
        />
      </div>

      {change.error ? <ErrorState message={change.error} /> : null}

      <div style={{ display: "flex", gap: 8.4, marginTop: 14, alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={change.pending || !currentPassword || newPassword.length < 10}
          onClick={async () => {
            setDone(false);
            const result = await change.run();
            if (result) {
              setDone(true);
              setCurrentPassword("");
              setNewPassword("");
            }
          }}
        >
          {change.pending ? "Alterando…" : "Alterar senha"}
        </button>
        {done ? (
          <span style={{ fontSize: 12.5, color: C.verde }}>
            Senha alterada. As outras sessões foram encerradas.
          </span>
        ) : (
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>
            Ao menos 10 caracteres, com letra e número.
          </span>
        )}
      </div>
    </Panel>
  );
}

/** Encerrar as sessões abertas — o botão de quando um dispositivo se perde. */
function Sessions() {
  const { logout } = useAuth();
  const [done, setDone] = useState(false);
  const logoutAll = useMutation(() => authApi.logoutAll());

  return (
    <Panel pad={16.8} style={{ boxShadow: "0 0 0 1px rgba(233,233,237,.16)" }}>
      <Kicker tone="muted" style={{ display: "block", marginBottom: 8.4 }}>
        Sessões
      </Kicker>
      <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "62ch" }}>
        Encerra o acesso em todos os aparelhos, inclusive neste. Use se perdeu um dispositivo ou
        suspeita que alguém entrou na sua conta.
      </p>
      <div style={{ display: "flex", gap: 8.4, alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={logoutAll.pending || done}
          onClick={async () => {
            const result = await logoutAll.run();
            if (result) {
              setDone(true);
              await logout();
            }
          }}
        >
          {logoutAll.pending ? "Encerrando…" : "Sair de todos os dispositivos"}
        </button>
        {logoutAll.error ? (
          <span style={{ fontSize: 12, color: "#cfa25e" }}>{logoutAll.error}</span>
        ) : null}
      </div>
    </Panel>
  );
}
