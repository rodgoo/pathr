/**
 * A barra do topo no celular.
 *
 * Existe por três razões práticas, não por decoração.
 *
 * A primeira: instalado na tela de início, o app desenha por baixo da barra
 * de status do iPhone, e alguma coisa precisa ocupar esse espaço com o fundo
 * do produto — senão o relógio do sistema fica sobre o conteúdo. Por isso o
 * recuo do topo mora AQUI e não na moldura: a barra precisa pintar a faixa
 * inteira, de borda a borda, e não pode ter o respiro lateral da moldura ou
 * o conteúdo apareceria rolando pelas frestas.
 *
 * A segunda: a barra lateral carregava a meta e o progresso do roadmap, e ela
 * não existe nesta largura. Esses dois números são o que responde "estou indo
 * bem?", e é a pergunta que faz alguém abrir o app no celular.
 *
 * A terceira: ela é FIXA. Rolar uma tela longa não deveria custar a
 * referência de onde se está no plano — e é justamente rolando que a pergunta
 * aparece. A exceção é Configurações, que tem a própria fila de abas logo
 * abaixo do título e não ganha nada com duas faixas presas no topo.
 *
 * O vidro fosco é o mesmo recurso que as barras do iOS usam: o conteúdo passa
 * por baixo e continua legível como sombra, em vez de sumir atrás de um bloco
 * opaco.
 */

import { roadmap as roadmapApi } from "@/api/endpoints";
import { useAppState } from "@/hooks/useAppState";
import { useQuery } from "@/hooks/useApi";
import { ACC4, SIZE, TEXT } from "@/lib/tokens";
import { Logo } from "@/components/ui/Logo";
import { Meter } from "@/components/ui/primitives";

export function MobileHeader() {
  const { state } = useAppState();
  const plano = useQuery(() => roadmapApi.current(), []);

  const fixa = state.screen !== "config";
  // O título INTEIRO — "Backend sênior em 12 semanas", e não só o cargo. O
  // cargo sozinho perdia o prazo, que é metade do compromisso que a pessoa
  // assumiu ao gerar o plano.
  const titulo = plano.data?.title || plano.data?.target_role || "PathR";

  return (
    <header
      style={{
        position: fixa ? "sticky" : "static",
        top: 0,
        zIndex: 30,
        // A faixa da barra de status entra no padding da barra: é ela que
        // pinta esse espaço, de borda a borda.
        //
        // Recuo desigual de propósito: 22 em cima, 10 embaixo. O conteúdo
        // encosta na borda de baixo da barra, como nas barras do iOS, em vez
        // de flutuar no meio dela — e a faixa do relógio fica com a folga que
        // precisa. Num navegador de desktop o `--safe-top` é zero, e é o 22
        // que sustenta o respiro sozinho.
        padding: `calc(var(--safe-top) + 22px) calc(11.2px + var(--safe-right)) 10px calc(11.2px + var(--safe-left))`,
        background: "rgba(0,0,0,.78)",
        backdropFilter: "saturate(180%) blur(18px)",
        WebkitBackdropFilter: "saturate(180%) blur(18px)",
        boxShadow: "inset 0 -1px 0 0 rgba(233,233,237,.10)",
        display: "flex",
        alignItems: "center",
        gap: 9,
      }}
    >
      <Logo size={26} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13.5,
            fontWeight: 500,
            lineHeight: 1.25,
            // Duas linhas no máximo: o título completo cabe, e um plano com
            // um objetivo quilométrico não empurra o app tela abaixo.
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {titulo}
        </div>

        {plano.data ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8.4,
              marginTop: 5,
            }}
          >
            <Meter
              pct={plano.data.progress_pct}
              color={ACC4}
              label="Progresso do roadmap"
              style={{ flex: 1, minWidth: 40 }}
            />
            {/* A barra sozinha não diz de QUE ela é medida. Estes dois números
                são o que transforma um traço colorido em informação. */}
            <span style={{ fontSize: SIZE.rotulo, color: TEXT.muted, whiteSpace: "nowrap" }}>
              {plano.data.done_nodes} de {plano.data.total_nodes} módulos ·{" "}
              {plano.data.progress_pct}%
            </span>
          </div>
        ) : (
          <div style={{ fontSize: SIZE.rotulo, color: TEXT.faint, marginTop: 2 }}>
            {plano.loading ? "carregando o plano…" : "nenhum plano gerado ainda"}
          </div>
        )}
      </div>
    </header>
  );
}
