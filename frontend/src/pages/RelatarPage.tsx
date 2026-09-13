/** Relatar: reclamação ou sugestão, na barra lateral de qualquer tela. */

import { RelatarTab } from "@/components/relatos/RelatarTab";
import { TEXT } from "@/lib/tokens";
import { SCREEN_IN } from "@/components/ui/primitives";

export function RelatarPage() {
  return (
    <div style={{ maxWidth: 760, ...SCREEN_IN }}>
      <h1 style={{ fontSize: 28, margin: "0 0 5.6px" }}>Relatar</h1>
      <p style={{ margin: "0 0 16.8px", fontSize: 13.5, color: TEXT.muted, maxWidth: "62ch" }}>
        Encontrou um problema ou tem uma ideia? O relato vai direto para quem cuida do PathR.
      </p>
      <RelatarTab />
    </div>
  );
}
