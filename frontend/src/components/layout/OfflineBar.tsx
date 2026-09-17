/**
 * A faixa que conta o estado da rede.
 *
 * Aparece só quando há algo a dizer. Um indicador permanente de "online" é
 * ruído: a ausência de aviso já é a informação, e uma faixa fixa roubaria
 * altura de tela num aparelho onde ela é escassa.
 *
 * As quatro coisas que ela pode dizer, em ordem de urgência:
 *
 * 1. Escritas recusadas pelo servidor — alguém precisa saber que um registro
 *    não vingou, senão o app terá mentido ao dizer "guardado".
 * 2. Sem rede, com fila — o que a pessoa fez está guardado e vai subir.
 * 3. Sem rede, sem fila — o que está na tela é o que o aparelho já tinha.
 * 4. Versão nova instalada e esperando.
 */

import { useOffline } from "@/hooks/useOffline";
import { useT } from "@/lib/i18n";
import { ACC4, C, SIZE, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";

const BASE: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8.4,
  padding: "7px 11.2px",
  borderRadius: 8,
  fontSize: 12,
  lineHeight: 1.35,
};

export function OfflineBar() {
  const t = useT();
  const { online, pendingCount, syncing, discarded, updateReady, applyUpdate, sync } = useOffline();

  if (discarded > 0) {
    return (
      <div
        role="alert"
        style={{
          ...BASE,
          color: "rgba(233,233,237,.86)",
          background: "rgba(207,162,94,.10)",
          boxShadow: `inset 0 0 0 1px ${C.ambar}55`,
        }}
      >
        <Icon name="wifiOff" size={14} />
        <span style={{ flex: 1, minWidth: 0 }}>
          {discarded === 1
            ? t("offline.recusadaSing")
            : t("offline.recusadaPlural", { n: discarded })}
        </span>
      </div>
    );
  }

  if (!online) {
    return (
      <div
        role="status"
        style={{
          ...BASE,
          color: "rgba(233,233,237,.78)",
          background: "rgba(233,233,237,.05)",
          boxShadow: "inset 0 0 0 1px rgba(233,233,237,.12)",
        }}
      >
        <Icon name="wifiOff" size={14} />
        <span style={{ flex: 1, minWidth: 0 }}>
          {pendingCount > 0
            ? pendingCount === 1
              ? t("offline.semConexaoFilaSing", { n: pendingCount })
              : t("offline.semConexaoFilaPlural", { n: pendingCount })
            : t("offline.semConexao")}
        </span>
      </div>
    );
  }

  if (pendingCount > 0) {
    return (
      <div
        role="status"
        style={{
          ...BASE,
          color: "rgba(233,233,237,.78)",
          background: "rgba(145,132,217,.09)",
          boxShadow: "inset 0 0 0 1px rgba(145,132,217,.28)",
        }}
      >
        <span style={{ flex: 1, minWidth: 0 }}>
          {syncing
            ? t("offline.enviando")
            : pendingCount === 1
              ? t("offline.aguardaSing", { n: pendingCount })
              : t("offline.aguardaPlural", { n: pendingCount })}
        </span>
        {syncing ? null : (
          <button
            type="button"
            className="btn btn-ghost"
            style={{ fontSize: SIZE.apoio, padding: "2px 6px" }}
            onClick={() => void sync()}
          >
            <Icon name="send" size={13} />
            {t("offline.enviarAgora")}
          </button>
        )}
      </div>
    );
  }

  if (updateReady) {
    return (
      <div
        role="status"
        style={{
          ...BASE,
          color: TEXT.strong,
          background: "rgba(145,132,217,.09)",
          boxShadow: "inset 0 0 0 1px rgba(145,132,217,.28)",
        }}
      >
        <span style={{ flex: 1, minWidth: 0 }}>{t("offline.versaoNova")}</span>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ fontSize: SIZE.apoio, padding: "2px 6px", color: ACC4 }}
          onClick={applyUpdate}
        >
          <Icon name="refresh" size={13} />
          {t("offline.atualizar")}
        </button>
      </div>
    );
  }

  return null;
}
