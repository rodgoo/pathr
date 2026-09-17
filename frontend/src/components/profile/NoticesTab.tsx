/**
 * Avisos e privacidade.
 *
 * Duas coisas na mesma aba porque respondem à mesma pergunta: o que este app
 * faz com você e com o que é seu. Em cima, o que ele tem permissão de mandar;
 * embaixo, como levar os dados embora ou apagar tudo.
 *
 * Cada interruptor grava sozinho, na hora. Um botão "Salvar preferências"
 * criaria o estado em que a tela mostra desligado e o servidor continua
 * mandando e-mail — o pior tipo de erro numa tela de consentimento.
 *
 * O padrão de cada aviso vem do servidor (`AVISOS` em routers/profile.py), e
 * não daqui: se os dois lados guardassem o padrão, mudá-lo exigiria dois
 * deploys coordenados e, entre eles, a tela mentiria.
 */

import { useEffect, useState } from "react";
import { auth as authApi, profile as profileApi } from "@/api/endpoints";
import type { Profile } from "@/api/types";
import { useAuth } from "@/hooks/useAuth";
import { useQuery } from "@/hooks/useApi";
import { useT } from "@/lib/i18n";
import { C, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";
import { PrivacidadeSocial } from "@/components/social/PrivacidadeSocial";

// O título e o detalhe de cada aviso vêm do dicionário (notices.avisos.<chave>).
const AVISOS: readonly string[] = [
  "lembrete_diario",
  "resumo_semanal",
  "novidades",
  "correcao_pronta",
  "sequencia_em_risco",
];

export function NoticesTab() {
  const t = useT();
  const { user, logout } = useAuth();
  const carregado = useQuery(() => profileApi.get(), []);
  const [avisos, setAvisos] = useState<Record<string, boolean>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);

  useEffect(() => {
    const vindos = carregado.data?.notifications;
    if (vindos) setAvisos(vindos);
  }, [carregado.data]);

  if (carregado.loading) return <Loading />;
  if (carregado.error) return <ErrorState message={carregado.error} onRetry={carregado.reload} />;

  async function alternar(chave: string) {
    const proximo = !avisos[chave];
    // Otimista: a caixa responde ao clique na hora. Se o servidor recusar, ela
    // volta — e o erro aparece, em vez de a tela seguir mostrando um estado
    // que não é o do servidor.
    setAvisos((atual) => ({ ...atual, [chave]: proximo }));
    setErro(null);
    try {
      await profileApi.update({ notifications: { [chave]: proximo } } as Partial<Profile>);
    } catch (caught) {
      setAvisos((atual) => ({ ...atual, [chave]: !proximo }));
      setErro(caught instanceof Error ? caught.message : t("notices.erroSalvar"));
    }
  }

  async function exportar() {
    setOcupado("export");
    setErro(null);
    try {
      const dados = await profileApi.exportData();
      // Monta o arquivo no navegador: o servidor devolve o conteúdo, e não um
      // link, para não deixar um arquivo com dado pessoal esperando num
      // storage até alguém lembrar de apagá-lo.
      const blob = new Blob([JSON.stringify(dados, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `pathr-meus-dados-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : t("notices.erroExportar"));
    } finally {
      setOcupado(null);
    }
  }

  async function sairDeTudo() {
    setOcupado("logout");
    try {
      await authApi.logoutAll();
      await logout();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : t("notices.erroSair"));
      setOcupado(null);
    }
  }

  async function excluir() {
    setOcupado("delete");
    try {
      await profileApi.deleteAccount();
      await logout();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : t("notices.erroExcluir"));
      setOcupado(null);
      setConfirmando(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <Panel pad={16.8}>
        <Kicker style={{ display: "block", marginBottom: 4 }}>{t("notices.notificacoesEmail")}</Kicker>
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px" }}>{user?.email}</p>

        <div style={{ display: "flex", flexDirection: "column", gap: 5.6 }}>
          {AVISOS.map((chave) => (
            <label
              key={chave}
              style={{
                display: "flex",
                gap: 11.2,
                alignItems: "flex-start",
                padding: "11.2px 14px",
                borderRadius: 8,
                background: "#0c0c10",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={Boolean(avisos[chave])}
                onChange={() => void alternar(chave)}
                style={{ marginTop: 2, flex: "none", accentColor: "#9184d9" }}
              />
              <span style={{ minWidth: 0 }}>
                <span style={{ display: "block", fontSize: 13.5 }}>{t(`notices.avisos.${chave}.titulo`)}</span>
                <span style={{ display: "block", fontSize: 11.5, color: TEXT.faint, marginTop: 3 }}>
                  {t(`notices.avisos.${chave}.detalhe`)}
                </span>
              </span>
            </label>
          ))}
        </div>
      </Panel>

      <PrivacidadeSocial />

      <Panel pad={16.8}>
        <Kicker style={{ display: "block", marginBottom: 11.2 }}>{t("notices.conta")}</Kicker>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "center" }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => void exportar()}
            disabled={ocupado === "export"}
          >
            {ocupado === "export" ? t("notices.preparando") : t("notices.exportar")}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => void sairDeTudo()}
            disabled={ocupado === "logout"}
          >
            {ocupado === "logout" ? t("notices.encerrando") : t("notices.sairTodos")}
          </button>
          {confirmando ? null : (
            <button
              type="button"
              onClick={() => setConfirmando(true)}
              style={{
                border: 0,
                background: "transparent",
                font: "inherit",
                fontSize: 13,
                color: C.ambar,
                cursor: "pointer",
                padding: "7px 4px",
              }}
            >
              {t("notices.excluirConta")}
            </button>
          )}
        </div>

        {confirmando ? (
          <div
            role="alertdialog"
            aria-label={t("notices.confirmarExclusao")}
            style={{
              marginTop: 11.2,
              padding: 14,
              borderRadius: 8,
              background: "rgba(207,162,94,.10)",
              borderLeft: `2px solid ${C.ambar}`,
            }}
          >
            <p style={{ margin: "0 0 11.2px", fontSize: 13, lineHeight: 1.55 }}>
              {t("notices.avisoExclusao")}
            </p>
            <div style={{ display: "flex", gap: 8.4, flexWrap: "wrap" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setConfirmando(false)}
              >
                <Icon name="x" size={15} />
                {t("notices.cancelar")}
              </button>
              <button
                type="button"
                onClick={() => void excluir()}
                disabled={ocupado === "delete"}
                style={{
                  padding: "8px 16px",
                  borderRadius: 8,
                  font: "inherit",
                  fontSize: 13,
                  cursor: "pointer",
                  border: `1px solid ${C.ambar}`,
                  background: "transparent",
                  color: C.ambar,
                }}
              >
                {ocupado === "delete" ? t("notices.excluindo") : t("notices.excluirDefinitivo")}
              </button>
            </div>
          </div>
        ) : null}

        <p style={{ margin: "11.2px 0 0", fontSize: 12, color: TEXT.faint, lineHeight: 1.55 }}>
          {t("notices.privacidadePre")}{" "}
          <a href="/privacidade" target="_blank" rel="noopener" style={{ color: "inherit" }}>
            {t("notices.politicaPrivacidade")}
          </a>
          .
        </p>
      </Panel>

      {erro ? <ErrorState message={erro} /> : null}
    </div>
  );
}
