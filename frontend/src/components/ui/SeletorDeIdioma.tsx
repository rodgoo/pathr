/**
 * O seletor de idioma: ícone de globo e o nome do idioma, escrito nele mesmo.
 *
 * "Español" e não "Espanhol": quem precisa trocar o idioma é justamente quem
 * não lê o idioma atual da tela, e o nome nativo é o único rótulo que essa
 * pessoa reconhece com certeza.
 *
 * `flutuante` é a forma da página de apresentação: canto inferior direito,
 * acima de tudo, visível antes de qualquer clique. Dentro do app, o mesmo
 * componente entra inteiro na largura do formulário de Configurações.
 */

import { Select } from "@/components/ui/Select";
import { Icon } from "@/components/ui/icons";
import { IDIOMAS, useIdioma, useT, type Idioma } from "@/lib/i18n";
import { PANEL } from "@/lib/tokens";

export function SeletorDeIdioma({
  id = "seletor-de-idioma",
  flutuante = false,
  aoTrocar,
  disabled = false,
}: {
  id?: string;
  /** Fixo no canto inferior direito, para a página de apresentação. */
  flutuante?: boolean;
  /** Chamado depois de trocar — é por aqui que Configurações grava na conta. */
  aoTrocar?: (idioma: Idioma) => void;
  disabled?: boolean;
}) {
  const { idioma, trocarIdioma } = useIdioma();
  const t = useT();

  const seletor = (
    <Select
      id={id}
      value={idioma}
      label={t("idioma.escolher")}
      disabled={disabled}
      options={IDIOMAS.map((item) => ({
        value: item.codigo,
        label: item.nome,
        icon: <Icon name="globe" size={16} />,
      }))}
      onChange={(novo) => {
        trocarIdioma(novo);
        aoTrocar?.(novo);
      }}
    />
  );

  if (!flutuante) return seletor;

  return (
    <div
      style={{
        position: "fixed",
        right: "calc(14px + var(--safe-right))",
        bottom: "calc(14px + var(--safe-bottom))",
        zIndex: 30,
        minWidth: 176,
        borderRadius: 10,
        background: PANEL,
        boxShadow: "0 8px 24px rgba(0,0,0,.35), 0 0 0 1px rgba(233,233,237,.10)",
        padding: 6,
      }}
    >
      {seletor}
    </div>
  );
}
