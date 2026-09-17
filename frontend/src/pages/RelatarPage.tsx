/** Relatar: reclamação ou sugestão, na barra lateral de qualquer tela. */

import { RelatarTab } from "@/components/relatos/RelatarTab";
import { useT } from "@/lib/i18n";
import { TEXT } from "@/lib/tokens";
import { SCREEN_IN } from "@/components/ui/primitives";

export function RelatarPage() {
  const t = useT();
  return (
    <div style={{ maxWidth: 760, ...SCREEN_IN }}>
      <h1 style={{ fontSize: 28, margin: "0 0 5.6px" }}>{t("relatar.titulo")}</h1>
      <p style={{ margin: "0 0 16.8px", fontSize: 13.5, color: TEXT.muted, maxWidth: "62ch" }}>
        {t("relatar.subtitulo")}
      </p>
      <RelatarTab />
    </div>
  );
}
