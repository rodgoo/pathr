/**
 * A foto de perfil, e as iniciais quando não há foto.
 *
 * A imagem é buscada como blob e não posta direto num `<img src>` apontando
 * para a API: o app vive em pathr.notter.com.br e a API em
 * api.pathr.notter.com.br, e a tag `img` não manda o cookie de sessão para
 * outro host — a foto voltaria 401. Buscando pelo cliente, o cookie vai
 * junto, e a foto continua sendo de quem está logado, não de quem descobrir
 * o endereço.
 *
 * As iniciais deixam de ser a única opção e passam a ser o estado "sem foto".
 * Elas continuam sendo o fallback de todo mundo que não enviou nada, e de
 * quem enviou mas cuja imagem não carregou agora.
 */

import { useEffect, useState } from "react";
import { esquecerFoto, fotoDe } from "@/lib/fotos";
import { profile as profileApi } from "@/api/endpoints";
import { useAuth } from "@/hooks/useAuth";
import { ACC3, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";

const LADO = 64;

/** Botão de texto pequeno sob a foto: ícone e nome, sem a caixa de botão. */
const ACAO = {
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  padding: "3px 2px",
  minHeight: 0,
  fontSize: 12,
} as const;

/** "Ana Paula Souza" -> "AP". Duas letras bastam para reconhecer. */
function iniciais(nome: string): string {
  return (
    nome
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((parte) => parte[0]?.toUpperCase())
      .join("") || "?"
  );
}

const ACEITOS = "image/jpeg,image/png,image/webp";

export function Avatar({ nome, editavel = false }: { nome: string; editavel?: boolean }) {
  const { user, refresh } = useAuth();
  const [url, setUrl] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const temFoto = Boolean(user?.has_avatar);

  useEffect(() => {
    if (!temFoto) {
      setUrl(null);
      return;
    }
    let vivo = true;
    // Da memória de fotos (lib/fotos): a mesma foto não é baixada de novo a
    // cada tela. Sem foto, as iniciais aparecem e o perfil segue utilizável.
    void fotoDe("eu", () => profileApi.avatar()).then((guardada) => {
      if (vivo) setUrl(guardada);
    });
    return () => {
      vivo = false;
    };
  }, [temFoto]);

  async function enviar(arquivo: File) {
    setErro(null);
    setOcupado(true);
    try {
      await profileApi.uploadAvatar(arquivo);
      esquecerFoto("eu");
      // O `has_avatar` mora na sessão: sem recarregar, a tela continuaria
      // achando que não há foto e nem tentaria buscá-la.
      await refresh();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : "Não consegui enviar a imagem.");
    } finally {
      setOcupado(false);
    }
  }

  async function remover() {
    setErro(null);
    setOcupado(true);
    try {
      await profileApi.removeAvatar();
      esquecerFoto("eu");
      await refresh();
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : "Não consegui remover a imagem.");
    } finally {
      setOcupado(false);
    }
  }

  const quadrado = {
    width: LADO,
    height: LADO,
    borderRadius: 16,
    display: "grid",
    placeItems: "center",
    overflow: "hidden",
    background: "rgba(233,233,237,.07)",
    boxShadow: "inset 0 0 0 1px rgba(233,233,237,.16)",
  } as const;

  const figura = url ? (
    <img
      src={url}
      alt={`Foto de perfil de ${nome}`}
      style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
    />
  ) : (
    <span aria-hidden style={{ fontSize: 22, color: ACC3 }}>
      {iniciais(nome)}
    </span>
  );

  if (!editavel) {
    return <div style={{ ...quadrado, flex: "none" }}>{figura}</div>;
  }

  return (
    <div style={{ flex: "none", display: "flex", flexDirection: "column", gap: 5.6 }}>
      <div style={quadrado}>{figura}</div>

      {/* Ícone COM o nome da ação, empilhados sob a foto. Só ícones lado a
          lado pediam adivinhar o que cada um fazia — a câmera parecia "tirar
          foto" — e, com a área de toque de 44px cada, ficavam mais largos que a
          própria foto e longe um do outro. */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2 }}>
        {/* Um `label` com input escondido, e não um botão que dispara o
            input por código: assim o seletor de arquivo abre por clique e
            por teclado sem nenhum script no meio. */}
        <label
          className="btn btn-ghost"
          style={{
            ...ACAO,
            cursor: ocupado ? "default" : "pointer",
            color: ocupado ? TEXT.faint : ACC3,
          }}
        >
          <Icon name={temFoto ? "pencil" : "upload"} size={13} />
          {ocupado ? "Enviando…" : temFoto ? "Alterar" : "Enviar foto"}
          <input
            type="file"
            accept={ACEITOS}
            disabled={ocupado}
            style={{ display: "none" }}
            onChange={(event) => {
              const arquivo = event.target.files?.[0];
              // Limpa o valor para que escolher O MESMO arquivo de novo
              // (depois de um erro, por exemplo) volte a disparar o evento.
              event.target.value = "";
              if (arquivo) void enviar(arquivo);
            }}
          />
        </label>
        {temFoto ? (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => void remover()}
            disabled={ocupado}
            style={{ ...ACAO, color: TEXT.muted }}
          >
            <Icon name="trash" size={13} />
            Remover
          </button>
        ) : null}
      </div>

      {erro ? (
        <span role="alert" style={{ fontSize: 11, color: "#cfa25e", maxWidth: 160 }}>
          {erro}
        </span>
      ) : null}
    </div>
  );
}
