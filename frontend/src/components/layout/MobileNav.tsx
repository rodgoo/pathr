/**
 * A navegação do celular: uma barra fixa embaixo.
 *
 * A barra lateral não encolhe bem. Numa tela de 390px ela comeria metade da
 * largura, e o conteúdo — que é texto de estudo — ficaria numa coluna estreita
 * demais para ler. Embaixo, ela some do caminho e cai onde o polegar alcança.
 *
 * São três destinos e um "Mais". Os três são os que se visita várias vezes
 * por sessão; cursos, vagas, código, idiomas, conta, currículo e ajustes ficam na
 * folha que o "Mais" abre. A alternativa — oito ícones de 40px — daria uma
 * barra em que ninguém acerta o que quer.
 *
 * Cada alvo tem 58px de altura de propósito: a diretriz da Apple põe o piso
 * do toque em 44px, e o rótulo sob o ícone pede o resto.
 *
 * A barra NÃO some enquanto se digita, embora isso pareça uma boa ideia. A
 * tentativa existiu e foi retirada: os rádios invisíveis do controle
 * segmentado também são `<input>`, então abrir a tela de Idiomas contava como
 * "digitando"; e quando um campo focado é desmontado, o `focusout` não vem —
 * a barra sumia e não voltava mais, deixando o app sem navegação nenhuma.
 * O iOS já empurra uma barra fixa para baixo do teclado, e o conteúdo já
 * reserva a altura dela no AppShell. Não havia problema a resolver.
 */

import { useState } from "react";
import { useAppState } from "@/hooks/useAppState";
import { useAuth } from "@/hooks/useAuth";
import { ACC4, PANEL, TEXT } from "@/lib/tokens";
import type { Screen } from "@/types";
import { Icon, type IconName } from "@/components/ui/icons";

interface Destino {
  label: string;
  screen: Screen;
  icon: IconName;
}

const BARRA: Destino[] = [
  { label: "Início", screen: "home", icon: "home" },
  { label: "Roadmap", screen: "roadmap", icon: "road" },
  { label: "Trilha", screen: "modulo", icon: "book" },
];

const FOLHA: Destino[] = [
  { label: "Cursos", screen: "cursos", icon: "award" },
  { label: "Vagas", screen: "vagas", icon: "suitcase" },
  { label: "Código", screen: "codigo", icon: "code" },
  { label: "Idiomas", screen: "ingles", icon: "flag" },
  { label: "Amigos", screen: "amigos", icon: "users" },
  { label: "Perfil e tags", screen: "perfil", icon: "user" },
  { label: "Currículo", screen: "cv", icon: "file" },
  { label: "Relatar", screen: "relatar", icon: "flag" },
  { label: "Configurações", screen: "config", icon: "cog" },
];

/** A altura que o conteúdo precisa reservar para não ficar sob a barra. */
export const ALTURA_DA_BARRA = 58;

export function MobileNav() {
  const { state, dispatch } = useAppState();
  const { logout } = useAuth();
  const [abriuMais, setAbriuMais] = useState(false);

  const vaiPara = (screen: Screen) => {
    dispatch({ type: "navigate", screen });
    setAbriuMais(false);
  };

  // A tela de material não tem aba própria: ela pertence a de onde veio, e
  // apagar a barra inteira enquanto se lê um artigo tiraria a referência de
  // onde a pessoa está.
  const telaAtiva = state.screen === "material" ? state.resourceReturn : state.screen;
  const naFolha = FOLHA.some((item) => item.screen === telaAtiva);

  return (
    <>
      {abriuMais ? (
        <>
          {/* O véu fecha a folha ao ser tocado. Um `button` e não uma `div`
              porque fechar é uma ação, e teclado e leitor de tela precisam
              alcançá-la. */}
          <button
            type="button"
            aria-label="Fechar menu"
            onClick={() => setAbriuMais(false)}
            style={{
              position: "fixed",
              inset: 0,
              border: 0,
              background: "rgba(10,11,18,.55)",
              zIndex: 40,
            }}
          />
          <div
            role="dialog"
            aria-label="Mais destinos"
            style={{
              position: "fixed",
              insetInline: 0,
              // ACIMA da barra, não atrás dela. Com as duas em `bottom: 0` a
              // barra ficava por cima e comia o último item da folha — o
              // "Sair" existia, respondia ao teclado, e não dava para ver.
              bottom: `calc(${ALTURA_DA_BARRA}px + var(--safe-bottom))`,
              zIndex: 41,
              paddingTop: 11.2,
              paddingBottom: 11.2,
              paddingLeft: "calc(11.2px + var(--safe-left))",
              paddingRight: "calc(11.2px + var(--safe-right))",
              // Numa tela curta (iPhone deitado) a folha rola em vez de
              // empurrar os itens para fora do alcance.
              maxHeight: `calc(100dvh - ${ALTURA_DA_BARRA}px - var(--safe-top) - var(--safe-bottom))`,
              overflowY: "auto",
              background: PANEL,
              borderRadius: "14px 14px 0 0",
              boxShadow: "0 -1px 0 0 #222228",
              display: "flex",
              flexDirection: "column",
              gap: 2.8,
              animation: "noc-in .16s ease-out",
            }}
          >
            {FOLHA.map((item) => (
              <ItemDaFolha
                key={item.screen}
                item={item}
                ativo={telaAtiva === item.screen}
                onClick={() => vaiPara(item.screen)}
              />
            ))}
            <button
              type="button"
              className="btn btn-ghost"
              style={{ justifyContent: "flex-start", gap: 11.2, minHeight: 46, paddingInline: 11.2 }}
              onClick={() => void logout()}
            >
              <Icon name="signOut" size={17} />
              Sair
            </button>
          </div>
        </>
      ) : null}

      <nav
        aria-label="Navegação principal"
        style={{
          position: "fixed",
          insetInline: 0,
          bottom: 0,
          zIndex: 42,
          display: "grid",
          // Uma coluna por destino, mais a do "Mais". Fixar o número deixava
          // uma coluna vazia sempre que um destino mudava para a folha.
          gridTemplateColumns: `repeat(${BARRA.length + 1},1fr)`,
          background: PANEL,
          boxShadow: "0 -1px 0 0 #222228",
          // O indicador de gestos do iPhone mora aqui embaixo; em paisagem, a
          // Dynamic Island come uma das laterais. Os tres `env` sao o que
          // impede um botao de cair debaixo de qualquer um dos dois.
          paddingBottom: "var(--safe-bottom)",
          paddingLeft: "var(--safe-left)",
          paddingRight: "var(--safe-right)",
        }}
      >
        {BARRA.map((item) => (
          <BotaoDaBarra
            key={item.screen}
            item={item}
            ativo={telaAtiva === item.screen}
            onClick={() => vaiPara(item.screen)}
          />
        ))}
        <BotaoDaBarra
          item={{ label: "Mais", screen: "config", icon: "dots" }}
          ativo={naFolha || abriuMais}
          expandido={abriuMais}
          onClick={() => setAbriuMais((aberto) => !aberto)}
        />
      </nav>
    </>
  );
}

function BotaoDaBarra({
  item,
  ativo,
  expandido,
  onClick,
}: {
  item: Destino;
  ativo: boolean;
  expandido?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={ativo && expandido === undefined ? "page" : undefined}
      aria-expanded={expandido}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 3,
        minHeight: ALTURA_DA_BARRA,
        padding: "6px 2px",
        border: 0,
        background: "none",
        font: "inherit",
        fontSize: 10,
        letterSpacing: ".01em",
        cursor: "pointer",
        color: ativo ? ACC4 : "rgba(233,233,237,.55)",
        // A cor sozinha não pode carregar o estado: quem não a distingue
        // precisa da marca acima do ícone para saber onde está.
        boxShadow: ativo ? `inset 0 2px 0 0 ${ACC4}` : "none",
      }}
    >
      {/* Cheio quando é a aba atual. É assim que o iOS diz "você está aqui", e
          quem usa iPhone lê isso antes de reparar na cor. */}
      <Icon name={item.icon} size={20} filled={ativo} />
      <span>{item.label}</span>
    </button>
  );
}

function ItemDaFolha({
  item,
  ativo,
  onClick,
}: {
  item: Destino;
  ativo: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={ativo ? "page" : undefined}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 11.2,
        minHeight: 46,
        padding: "0 11.2px",
        border: 0,
        borderRadius: 8,
        font: "inherit",
        fontSize: 14.5,
        textAlign: "left",
        cursor: "pointer",
        background: ativo ? "rgba(145,132,217,.13)" : "transparent",
        color: ativo ? ACC4 : TEXT.full,
      }}
    >
      <Icon name={item.icon} size={17} />
      {item.label}
    </button>
  );
}
