/**
 * Conta: nome, preferências e senha.
 *
 * O e-mail aparece mas não é editável: trocá-lo exigiria confirmar o novo
 * endereço antes de valer, e esse fluxo ainda não existe no backend. Mostrar
 * um campo que não salva seria pior que mostrá-lo bloqueado.
 */

import { useState, type FormEvent } from "react";
import { auth as authApi, profile as profileApi } from "@/api/endpoints";
import { useAuth } from "@/hooks/useAuth";
import { useMutation, useQuery } from "@/hooks/useApi";
import { C, TEXT } from "@/lib/tokens";
import { ErrorState, Loading } from "@/components/ui/States";
import { PasswordField } from "@/components/auth/AuthShell";
import { Kicker, Panel } from "@/components/ui/primitives";
import { PasskeysPanel } from "./PasskeysPanel";

export function AccountTab() {
  const { user, refresh } = useAuth();
  const profile = useQuery(() => profileApi.get(), []);
  const [name, setName] = useState(user?.name ?? "");
  const [role, setRole] = useState("");
  const [hours, setHours] = useState("8");
  const [saved, setSaved] = useState(false);

  const save = useMutation(async () => {
    await authApi.me();
    await profileApi.updateAccount({ name: name.trim() });
    await profileApi.update({
      current_role: role.trim() || null,
      weekly_hours: Number(hours) || 8,
    });
    await refresh();
  });

  if (profile.loading) return <Loading />;
  if (profile.error) return <ErrorState message={profile.error} onRetry={profile.reload} />;

  // Sincroniza os campos com o servidor na primeira renderização com dados.
  if (profile.data && role === "" && profile.data.current_role) {
    setRole(profile.data.current_role);
    setHours(String(profile.data.weekly_hours));
  }

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
          <button type="submit" className="btn btn-primary" disabled={save.pending}>
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
