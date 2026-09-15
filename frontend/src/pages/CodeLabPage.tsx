/**
 * Laboratório de código: exemplos prontos que se percorre linha a linha.
 *
 * ## O que esta tela resolve
 *
 * Ler código pronto ensina pouco. A pessoa passa os olhos, reconhece as
 * palavras e segue — a mesma ilusão de competência que a explicação pelo
 * método Feynman existe para quebrar, só que com código. O que ensina é ver o
 * programa RODAR: a linha que executa agora, o que cada variável vale nesse
 * instante, e o que já foi impresso.
 *
 * É o que um depurador dá a quem já sabe montar um. Quem está aprendendo não
 * tem ambiente, não sabe pôr breakpoint, e desiste antes de chegar lá.
 *
 * ## Por que a tela diz que a execução é comentada
 *
 * O traço vem de um modelo de linguagem, não de uma máquina rodando o
 * programa. O servidor recusa traço incoerente com o código (o passo que
 * aponta para linha inexistente ou em branco), mas coerente não é o mesmo que
 * correto. Chamar isso de "execução real" seria vender precisão que não
 * existe, e a primeira conta errada destruiria a confiança na tela inteira.
 * Dizer o que é deixa a pessoa ler com o olho certo.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/api/client";
import { walkthroughs as walkthroughsApi } from "@/api/endpoints";
import { useAppState } from "@/hooks/useAppState";
import type { Walkthrough } from "@/api/types";
import { useMutation, useQuery } from "@/hooks/useApi";
import { ACC, ACC4, C, HAIRLINE, PANEL, TEXT } from "@/lib/tokens";
import { IconButton } from "@/components/ui/IconButton";
import { CodeBlock } from "@/components/quiz/CodeBlock";
import { Icon } from "@/components/ui/icons";
import { Segmented } from "@/components/ui/Segmented";
import { Select } from "@/components/ui/Select";
import { iconeDaLinguagem } from "@/lib/linguagens";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { Perguntar } from "@/components/duvidas/Perguntar";
import { ProgressoDaTarefa } from "@/components/ui/ProgressoDaTarefa";
import { CHAVE_DO_LABORATORIO, EVENTO_ABRIR_EXEMPLO } from "@/lib/laboratorio";

const MONO = "ui-monospace, Menlo, monospace";

/**
 * Onde a pessoa parou: qual exemplo e em que passo.
 *
 * Fora do `pathr:ui:v1` de propósito — aquele estado é a navegação, e é
 * reescrito a cada mudança de tela. Aqui a chave é só desta tela e sobrevive a
 * ir consultar outra coisa no meio de um traço de trinta passos, que é
 * exatamente quando a pessoa sai.
 */
const CHAVE = CHAVE_DO_LABORATORIO;

const NIVEIS = [
  { value: "iniciante", label: "Iniciante" },
  { value: "intermediario", label: "Intermediário" },
  { value: "avancado", label: "Avançado" },
];

const NOME_DO_NIVEL: Record<string, string> = {
  iniciante: "Iniciante",
  intermediario: "Intermediário",
  avancado: "Avançado",
};

/** Um exemplo que vale abrir agora, escolhido pelo servidor sem IA. */
interface Sugestao {
  language: string;
  language_label: string;
  topic: string;
  level: string;
  motivo: string;
  origem: "roadmap" | "trilha" | "proximo_nivel";
}

/** O laboratório desta pessoa (GET /walkthroughs/para-mim). */
interface ParaMim {
  /** Só as linguagens do perfil; todas quando o perfil não tem nenhuma. */
  linguagens: { id: string; rotulo: string; realce: string }[];
  do_perfil: boolean;
  sugestoes: Sugestao[];
}

interface Guardado {
  id: string;
  passo: number;
}

function ler(): Guardado | null {
  try {
    const bruto = window.localStorage.getItem(CHAVE);
    if (!bruto) return null;
    const dado = JSON.parse(bruto) as Partial<Guardado>;
    return dado.id ? { id: dado.id, passo: dado.passo ?? 0 } : null;
  } catch {
    return null;
  }
}

function gravar(valor: Guardado | null) {
  try {
    if (valor) window.localStorage.setItem(CHAVE, JSON.stringify(valor));
    else window.localStorage.removeItem(CHAVE);
  } catch {
    // Armazenamento bloqueado: a tela funciona, só não lembra.
  }
}

export function CodeLabPage() {
  const paraMim = useQuery(() => api.get<ParaMim>("/walkthroughs/para-mim"), []);
  const lista = useQuery(() => walkthroughsApi.list(), []);

  const [guardado] = useState(ler);
  const [abertoId, setAbertoId] = useState<string | null>(guardado?.id ?? null);

  // Só a lista basta para abrir um exemplo: ela já traz código e traço. Um
  // GET por id seria uma ida ao servidor para repetir o que está na mão.
  const aberto = useMemo(
    () => (lista.data ?? []).find((item) => item.id === abertoId) ?? null,
    [lista.data, abertoId],
  );

  // Um exemplo pedido fora daqui (o "Perguntar") com esta tela já aberta:
  // troca o exemplo aberto e recarrega a lista, que ainda não o tem.
  const { reload: recarregarLista } = lista;
  useEffect(() => {
    function abrir(evento: Event) {
      const id = (evento as CustomEvent<string>).detail;
      if (!id) return;
      setAbertoId(id);
      recarregarLista();
    }
    window.addEventListener(EVENTO_ABRIR_EXEMPLO, abrir);
    return () => window.removeEventListener(EVENTO_ABRIR_EXEMPLO, abrir);
  }, [recarregarLista]);

  // O exemplo guardado pode ter sido apagado noutro aparelho. Esquecer é
  // melhor que abrir a tela num estado que não existe mais.
  useEffect(() => {
    if (lista.data && abertoId && !lista.data.some((item) => item.id === abertoId)) {
      setAbertoId(null);
      gravar(null);
    }
  }, [lista.data, abertoId]);

  return (
    <div style={{ ...SCREEN_IN, display: "flex", flexDirection: "column", gap: 16.8 }}>
      <header>
        <Kicker style={{ display: "block", marginBottom: 5.6 }}>Laboratório de código</Kicker>
        <h1 style={{ fontSize: 23, fontWeight: 500, margin: 0 }}>
          Código pronto, percorrido linha a linha
        </h1>
        <p style={{ fontSize: 13, color: TEXT.muted, margin: "8.4px 0 0", maxWidth: "70ch" }}>
          Escolha o assunto e deixe a linguagem no automático, ou escolha você. Você recebe o código ou
          a configuração que se usa de verdade — um arquivo ou vários, como o workflow do GitHub e o
          teste que ele roda, ou Controller, Service e Entity — e o passo a passo da execução: qual
          linha de qual arquivo roda, o que cada variável vale naquele instante e o que saiu no
          terminal.
        </p>
      </header>

      <Sugestoes
        dados={paraMim.data}
        carregando={paraMim.loading}
        onCriado={(novo) => {
          lista.reload();
          paraMim.reload();
          setAbertoId(novo.id);
          gravar({ id: novo.id, passo: 0 });
        }}
      />

      <Gerador
        linguagens={paraMim.data?.linguagens ?? []}
        doPerfil={paraMim.data?.do_perfil ?? true}
        carregando={paraMim.loading}
        onCriado={(novo) => {
          lista.reload();
          paraMim.reload();
          setAbertoId(novo.id);
          gravar({ id: novo.id, passo: 0 });
        }}
      />

      {lista.error ? <ErrorState message={lista.error} onRetry={lista.reload} /> : null}
      {lista.loading && !lista.data ? <Loading label="Carregando seus exemplos…" /> : null}

      {aberto ? (
        <Depurador
          key={aberto.id}
          exemplo={aberto}
          passoInicial={guardado?.id === aberto.id ? guardado.passo : 0}
          onPasso={(passo) => gravar({ id: aberto.id, passo })}
          onFechar={() => {
            setAbertoId(null);
            gravar(null);
          }}
        />
      ) : null}

      <Biblioteca
        exemplos={lista.data ?? []}
        abertoId={abertoId}
        carregando={lista.loading}
        onAbrir={(item) => {
          setAbertoId(item.id);
          gravar({ id: item.id, passo: 0 });
        }}
        onRemovido={(id) => {
          if (id === abertoId) {
            setAbertoId(null);
            gravar(null);
          }
          lista.reload();
        }}
      />
    </div>
  );
}

/**
 * Vários exemplos para abrir agora: o que o roadmap está pedindo, o nível da
 * pessoa em cada linguagem e o próximo passo. Um clique gera — não é preciso
 * saber o que pedir para começar.
 */
function Sugestoes({
  dados,
  carregando,
  onCriado,
}: {
  dados: ParaMim | null;
  carregando: boolean;
  onCriado: (novo: Walkthrough) => void;
}) {
  const { dispatch } = useAppState();
  const [gerando, setGerando] = useState<string | null>(null);
  const criar = useMutation((sugestao: Sugestao) =>
    walkthroughsApi.create(sugestao.language, sugestao.topic, sugestao.level),
  );

  if (carregando && !dados) return <Loading label="Montando sugestões para você…" />;
  if (!dados) return null;

  if (!dados.do_perfil) {
    return (
      <Panel pad={16.8}>
        <EmptyState
          title="Marque as linguagens que você estuda"
          description="O laboratório mostra só as linguagens do seu perfil e sugere exemplos pelo seu nível e pelo seu roadmap. Por enquanto, todas aparecem no gerador abaixo."
          action={
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => dispatch({ type: "navigate", screen: "config", settingsTab: "skills" })}
            >
              <Icon name="code" size={15} />
              Escolher linguagens
            </button>
          }
        />
      </Panel>
    );
  }
  if (!dados.sugestoes.length) return null;

  async function gerar(sugestao: Sugestao) {
    setGerando(sugestao.topic);
    const novo = await criar.run(sugestao);
    setGerando(null);
    if (novo) onCriado(novo);
  }

  return (
    <Panel pad={16.8}>
      <Kicker style={{ display: "block", marginBottom: 5.6 }}>Sugestões para você</Kicker>
      <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "72ch" }}>
        Pelo seu roadmap, pelo seu nível em cada linguagem e pelo que você ainda não abriu. Um clique gera o
        exemplo com o passo a passo.
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 250px), 1fr))",
          gap: 8.4,
        }}
      >
        {dados.sugestoes.map((sugestao) => {
          const esta = gerando === sugestao.topic;
          return (
            <button
              key={`${sugestao.language}-${sugestao.topic}`}
              type="button"
              disabled={Boolean(gerando)}
              onClick={() => void gerar(sugestao)}
              aria-label={`Gerar exemplo: ${sugestao.topic} em ${sugestao.language_label}`}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 6,
                textAlign: "left",
                padding: 11.2,
                borderRadius: 8,
                font: "inherit",
                cursor: gerando ? "wait" : "pointer",
                color: TEXT.full,
                background: esta ? "rgba(145,132,217,.13)" : "rgba(233,233,237,.03)",
                border: `1px solid ${sugestao.origem === "roadmap" ? ACC : "rgba(233,233,237,.12)"}`,
                opacity: gerando && !esta ? 0.55 : 1,
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5, color: TEXT.muted }}>
                <span style={{ width: 16, height: 16, display: "inline-grid", placeItems: "center" }}>
                  {iconeDaLinguagem(sugestao.language)}
                </span>
                {sugestao.language_label} · {NOME_DO_NIVEL[sugestao.level] ?? sugestao.level}
              </span>
              <span style={{ fontSize: 13.5, lineHeight: 1.35 }}>{sugestao.topic}</span>
              {/* O motivo sempre no pé do cartão (`marginTop: auto`): com
                  títulos de duas ou três linhas lado a lado, ele ficava em
                  alturas diferentes em cada cartão da mesma fileira. */}
              <span
                style={{
                  fontSize: 11.5,
                  color: sugestao.origem === "roadmap" ? ACC4 : TEXT.faint,
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 5,
                  marginTop: "auto",
                  paddingTop: 4,
                }}
              >
                <Icon
                  name={sugestao.origem === "roadmap" ? "road" : sugestao.origem === "proximo_nivel" ? "trend" : "flag"}
                  size={13}
                  style={{ flex: "none", marginTop: 2 }}
                />
                {esta ? "Escrevendo o exemplo…" : sugestao.motivo}
              </span>
            </button>
          );
        })}
      </div>
      <ProgressoDaTarefa
        ativo={Boolean(gerando)}
        chave="laboratorio-gerar"
        etapas={["Escolhendo os arquivos", "Escrevendo o código", "Conferindo se é o que se usa de verdade", "Montando o passo a passo"]}
        duracaoMs={25_000}
        style={{ marginTop: 11.2 }}
      />
      {criar.error ? <ErrorState message={criar.error} /> : null}
    </Panel>
  );
}

/** O formulário que pede um exemplo novo, com qualquer assunto. */
function Gerador({
  linguagens,
  doPerfil,
  carregando,
  onCriado,
}: {
  linguagens: { id: string; rotulo: string }[];
  doPerfil: boolean;
  carregando: boolean;
  onCriado: (novo: Walkthrough) => void;
}) {
  const [language, setLanguage] = useState("auto");
  const [topic, setTopic] = useState("");
  const [level, setLevel] = useState("iniciante");

  // A linguagem escolhida precisa estar na lista que o servidor mandou. Ela
  // começa pelo automático: quem pede "GitHub e testes" não precisa saber que
  // isso é um YAML chamando um teste — e escolher Java ali gerava um programa
  // Java fingindo ser o GitHub.
  useEffect(() => {
    if (linguagens.length && !linguagens.some((item) => item.id === language)) {
      setLanguage(linguagens[0].id);
    }
  }, [linguagens, language]);

  const criar = useMutation(() => walkthroughsApi.create(language, topic.trim(), level));

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (topic.trim().length < 2) return;
    const novo = await criar.run();
    if (novo) {
      setTopic("");
      onCriado(novo);
    }
  }

  return (
    <Panel pad={16.8}>
      <form onSubmit={enviar} style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
        <div style={{ display: "flex", gap: 11.2, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 190 }}>
            <label htmlFor="codelab-linguagem" style={{ fontSize: 11.5, color: TEXT.faint }}>
              {doPerfil ? "Linguagem ou arquivo" : "Linguagem"}
            </label>
            <Select
              id="codelab-linguagem"
              value={language}
              onChange={setLanguage}
              disabled={carregando || linguagens.length === 0}
              options={linguagens.map((item) => ({
                value: item.id,
                label: item.rotulo,
                icon: iconeDaLinguagem(item.id),
              }))}
            />
          </div>

          <label
            style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1, minWidth: 220 }}
          >
            <span style={{ fontSize: 11.5, color: TEXT.faint }}>Assunto</span>
            <input
              className="input"
              value={topic}
              maxLength={120}
              placeholder="GitHub Actions rodando os testes, API com Controller e Entity, closures…"
              onChange={(evento) => setTopic(evento.target.value)}
            />
          </label>
        </div>

        <div style={{ display: "flex", gap: 11.2, flexWrap: "wrap", alignItems: "center" }}>
          <Segmented
            name="codelab-nivel"
            label="Nível"
            options={NIVEIS}
            value={level}
            onChange={(valor) => setLevel(valor)}
          />
          <button
            type="submit"
            className="btn btn-primary"
            style={{ marginLeft: "auto" }}
            disabled={criar.pending || topic.trim().length < 2}
          >
            <Icon name="plus" size={15} />
            {criar.pending ? "Escrevendo o exemplo…" : "Gerar exemplo"}
          </button>
        </div>

        {criar.pending ? (
          <p style={{ fontSize: 11.5, color: TEXT.faint, margin: 0 }}>
            Leva alguns segundos: os arquivos e o traço de execução saem juntos. Antes de aparecer
            aqui, o conteúdo é conferido (sintaxe, versões atuais, estrutura de projeto real) e o
            traço, contra cada arquivo.
          </p>
        ) : null}
        {criar.error ? <ErrorState message={criar.error} /> : null}
      </form>
    </Panel>
  );
}

/**
 * O passo a passo em si.
 *
 * O código fica em cima e os painéis embaixo, e não lado a lado: no celular a
 * coluna dupla espremeria o código a ponto de quebrar linha, que é justamente
 * o que torna um traço ilegível.
 */
function Depurador({
  exemplo,
  passoInicial,
  onPasso,
  onFechar,
}: {
  exemplo: Walkthrough;
  passoInicial: number;
  onPasso: (passo: number) => void;
  onFechar: () => void;
}) {
  const passos = exemplo.steps;
  const total = passos.length;
  // O passo guardado pode não existir mais se o exemplo mudou de tamanho.
  const [indice, setIndice] = useState(() =>
    Math.min(Math.max(passoInicial, 0), Math.max(total - 1, 0)),
  );
  const [rodando, setRodando] = useState(false);

  useEffect(() => {
    onPasso(indice);
  }, [indice, onPasso]);

  const ir = useCallback(
    (destino: number) => {
      setIndice(() => {
        const alvo = Math.min(Math.max(destino, 0), Math.max(total - 1, 0));
        // Chegou ao fim: parar sozinho, senão o botão fica dizendo "pausar"
        // num traço que não anda mais.
        if (alvo === total - 1) setRodando(false);
        return alvo;
      });
    },
    [total],
  );

  // Execução automática: um passo por segundo e meio, tempo de ler a frase do
  // passo antes do próximo. Mais rápido vira animação, e animação não ensina.
  const temporizador = useRef<number | null>(null);
  useEffect(() => {
    if (!rodando) return;
    temporizador.current = window.setTimeout(() => ir(indice + 1), 1500);
    return () => {
      if (temporizador.current !== null) window.clearTimeout(temporizador.current);
    };
  }, [rodando, indice, ir]);

  // Setas do teclado: quem percorre trinta passos não quer trinta cliques.
  useEffect(() => {
    function tecla(evento: KeyboardEvent) {
      const alvo = evento.target as HTMLElement | null;
      // Não sequestra as setas de quem está digitando no formulário acima.
      if (alvo && /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName)) return;
      if (evento.key === "ArrowRight") {
        setRodando(false);
        ir(indice + 1);
      } else if (evento.key === "ArrowLeft") {
        setRodando(false);
        ir(indice - 1);
      }
    }
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [indice, ir]);

  const passo = passos[indice];
  const linhaAtual = passo ? passo.linha - 1 : null;

  // Os arquivos do exemplo. Exemplo antigo (anterior aos vários arquivos)
  // chega sem `files` de um cache velho: vira o arquivo único que ele é.
  const arquivos = useMemo(
    () =>
      exemplo.files?.length
        ? exemplo.files
        : [
            {
              caminho: exemplo.language_label,
              linguagem: exemplo.language,
              rotulo: exemplo.language_label,
              realce: exemplo.highlight,
              linhas: exemplo.lines,
            },
          ],
    [exemplo],
  );
  const arquivoDoPasso = passo?.arquivo ?? arquivos[0].caminho;

  // A aba acompanha o passo: a requisição sai do Controller e entra no
  // Service, e a tela vai junto. A pessoa pode abrir outra aba para olhar; o
  // próximo passo traz de volta para onde a execução está.
  const [arquivoVisto, setArquivoVisto] = useState(arquivoDoPasso);
  useEffect(() => {
    setArquivoVisto(arquivoDoPasso);
  }, [arquivoDoPasso, indice]);
  const atual = arquivos.find((arquivo) => arquivo.caminho === arquivoVisto) ?? arquivos[0];
  const variosArquivos = arquivos.length > 1;
  const linhaDoPasso = passo
    ? (arquivos.find((arquivo) => arquivo.caminho === arquivoDoPasso)?.linhas[passo.linha - 1] ?? "").trim()
    : "";

  // A saída acumula. Um painel que mostrasse só a linha do passo atual faria a
  // impressão anterior sumir ao avançar — o oposto do que se precisa ver.
  const saida = useMemo(
    () =>
      passos
        .slice(0, indice + 1)
        .map((item) => item.saida)
        .filter(Boolean)
        .join("\n"),
    [passos, indice],
  );

  return (
    <Panel pad={16.8}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 8.4,
          flexWrap: "wrap",
          marginBottom: 11.2,
        }}
      >
        <h2 style={{ fontSize: 17, fontWeight: 500, margin: 0 }}>{exemplo.title}</h2>
        <span className="tag tag-outline">{exemplo.language_label}</span>
        <span className="tag tag-outline">{exemplo.level}</span>
        <button
          type="button"
          className="btn btn-ghost btn-icon"
          aria-label="Fechar exemplo"
          title="Fechar"
          style={{ marginLeft: "auto", alignSelf: "center" }}
          onClick={onFechar}
        >
          <Icon name="x" size={16} />
        </button>
      </div>

      {exemplo.summary ? (
        <p style={{ fontSize: 13, color: TEXT.muted, margin: "0 0 14px", maxWidth: "74ch" }}>
          {exemplo.summary}
        </p>
      ) : null}

      {variosArquivos ? (
        <div
          role="tablist"
          aria-label="Arquivos do exemplo"
          style={{ display: "flex", gap: 4, overflowX: "auto", marginBottom: 8.4, paddingBottom: 2 }}
        >
          {arquivos.map((arquivo) => {
            const selecionado = arquivo.caminho === atual.caminho;
            const executando = total > 0 && arquivo.caminho === arquivoDoPasso;
            return (
              <button
                key={arquivo.caminho}
                type="button"
                role="tab"
                aria-selected={selecionado}
                title={arquivo.caminho}
                onClick={() => setArquivoVisto(arquivo.caminho)}
                style={{
                  flex: "none",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "5.6px 9.8px",
                  borderRadius: 6,
                  border: "none",
                  font: "inherit",
                  fontFamily: MONO,
                  fontSize: 12,
                  cursor: "pointer",
                  color: selecionado ? TEXT.full : TEXT.muted,
                  background: selecionado ? "rgba(233,233,237,.08)" : "transparent",
                  boxShadow: executando ? `inset 0 -2px 0 ${ACC}` : "none",
                }}
              >
                <span style={{ width: 14, height: 14, display: "inline-grid", placeItems: "center" }} aria-hidden>
                  {iconeDaLinguagem(arquivo.linguagem)}
                </span>
                {nomeDoArquivo(arquivo.caminho)}
              </button>
            );
          })}
        </div>
      ) : null}

      <CodeBlock
        label={`Arquivo ${atual.caminho}`}
        lines={atual.linhas}
        filename={variosArquivos ? atual.caminho : atual.rotulo}
        meta={total > 0 ? `passo ${indice + 1} de ${total}` : "sem passo a passo"}
        generico={atual.realce !== "java"}
        // A linha marcada só no arquivo onde o passo acontece: marcar a mesma
        // linha em outro arquivo apontaria para o lugar errado.
        highlight={linhaAtual === null || atual.caminho !== arquivoDoPasso ? null : { from: linhaAtual, to: linhaAtual }}
      />

      {total === 0 ? (
        <p
          role="status"
          style={{ fontSize: 12.5, color: C.ambar, margin: "11.2px 0 0", maxWidth: "74ch" }}
        >
          O passo a passo deste exemplo não saiu coerente com o código, então não é exibido —
          mostrar um traço que não bate com o programa ensinaria errado. O código acima continua
          valendo; gere de novo para tentar outro traço.
        </p>
      ) : (
        <>
          <Controles
            indice={indice}
            total={total}
            rodando={rodando}
            onIr={(destino) => {
              setRodando(false);
              ir(destino);
            }}
            onAlternar={() => {
              if (!rodando && indice === total - 1) ir(0);
              setRodando((atual) => !atual);
            }}
          />

          <div
            style={{
              display: "grid",
              gap: 11.2,
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              marginTop: 14,
            }}
          >
            <AcaoDoPasso passo={passo} numero={indice + 1} arquivo={variosArquivos ? arquivoDoPasso : null} />
            <Estado variaveis={passo?.estado ?? []} />
            <Saida texto={saida} />
          </div>
        </>
      )}

      {exemplo.concepts.length > 0 ? (
        <div style={{ marginTop: 14, display: "flex", gap: 5.6, flexWrap: "wrap" }}>
          {exemplo.concepts.map((conceito) => (
            <span key={conceito} className="tag tag-outline">
              {conceito}
            </span>
          ))}
        </div>
      ) : null}

      <div style={{ marginTop: 14 }}>
        <Perguntar
          contextoTipo="laboratorio"
          contextoRef={exemplo.id}
          trecho={
            passo
              ? `Passo ${indice + 1}, ${variosArquivos ? `${arquivoDoPasso} ` : ""}linha ${passo.linha} (${linhaDoPasso}): ${passo.acao}`
              : undefined
          }
        />
      </div>

      <p style={{ fontSize: 11, color: TEXT.faint, margin: "14px 0 0", maxWidth: "74ch" }}>
        A execução aqui é comentada, não medida: o passo a passo foi escrito junto com o código e
        conferido contra ele, mas o programa não roda num interpretador de verdade. Para o exemplo
        valer como certeza, rode-o você mesmo.
      </p>
    </Panel>
  );
}

function Controles({
  indice,
  total,
  rodando,
  onIr,
  onAlternar,
}: {
  indice: number;
  total: number;
  rodando: boolean;
  onIr: (destino: number) => void;
  onAlternar: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8.4,
        flexWrap: "wrap",
        marginTop: 11.2,
      }}
    >
      <IconButton icon="undo" label="Voltar ao início" tone="secondary" onClick={() => onIr(0)} disabled={indice === 0} />
      <IconButton
        icon="arrowLeft"
        label="Passo anterior"
        tone="secondary"
        onClick={() => onIr(indice - 1)}
        disabled={indice === 0}
      />
      <IconButton
        icon="arrowRight"
        label="Próximo passo"
        tone="primary"
        onClick={() => onIr(indice + 1)}
        disabled={indice >= total - 1}
      />
      <button
        type="button"
        className="btn btn-ghost"
        onClick={onAlternar}
        aria-label={rodando ? "Pausar a execução automática" : "Executar passo a passo sozinho"}
      >
        <Icon name={rodando ? "dots" : "play"} size={14} />
        <span style={{ marginLeft: 5.6 }}>{rodando ? "Pausar" : "Executar"}</span>
      </button>

      <div
        role="progressbar"
        aria-valuemin={1}
        aria-valuemax={total}
        aria-valuenow={indice + 1}
        aria-label="Passo da execução"
        style={{
          flex: 1,
          minWidth: 120,
          height: 3,
          borderRadius: 2,
          background: "rgba(233,233,237,.10)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${total > 1 ? (indice / (total - 1)) * 100 : 100}%`,
            height: "100%",
            background: ACC,
            transition: "width .2s ease",
          }}
        />
      </div>
      <span style={{ fontSize: 11.5, color: TEXT.faint, fontFamily: MONO }}>
        {indice + 1}/{total}
      </span>
    </div>
  );
}

/** O que aconteceu neste passo. É a frase que a pessoa lê antes de avançar. */
function AcaoDoPasso({
  passo,
  numero,
  arquivo,
}: {
  passo: Walkthrough["steps"][number] | undefined;
  numero: number;
  /** Com vários arquivos, em qual deles o passo acontece. */
  arquivo: string | null;
}) {
  return (
    <Caixa titulo={`Passo ${numero}`}>
      {passo ? (
        <>
          <div style={{ fontSize: 11.5, color: ACC, fontFamily: MONO, marginBottom: 5.6, overflowWrap: "anywhere" }}>
            {arquivo ? `${nomeDoArquivo(arquivo)} · ` : ""}linha {passo.linha}
          </div>
          <p style={{ fontSize: 13, lineHeight: 1.55, margin: 0, color: "rgba(233,233,237,.88)" }}>
            {passo.acao}
          </p>
        </>
      ) : (
        <p style={{ fontSize: 12.5, color: TEXT.faint, margin: 0 }}>—</p>
      )}
    </Caixa>
  );
}

/** As variáveis vivas, com o valor no fim do passo atual. */
function Estado({ variaveis }: { variaveis: { nome: string; valor: string }[] }) {
  return (
    <Caixa titulo="Variáveis agora">
      {variaveis.length === 0 ? (
        <p style={{ fontSize: 12.5, color: TEXT.faint, margin: 0 }}>
          Nenhuma variável definida ainda.
        </p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: MONO }}>
          <tbody>
            {variaveis.map((variavel) => (
              <tr key={variavel.nome}>
                <td
                  style={{
                    padding: "2.8px 8.4px 2.8px 0",
                    fontSize: 12,
                    color: ACC4,
                    verticalAlign: "top",
                    whiteSpace: "nowrap",
                  }}
                >
                  {variavel.nome}
                </td>
                <td
                  style={{
                    padding: "2.8px 0",
                    fontSize: 12,
                    color: "rgba(233,233,237,.88)",
                    wordBreak: "break-word",
                  }}
                >
                  {variavel.valor}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Caixa>
  );
}

/** Tudo que o programa imprimiu até aqui. */
function Saida({ texto }: { texto: string }) {
  return (
    <Caixa titulo="Saída até aqui">
      {texto ? (
        <pre
          style={{
            margin: 0,
            fontFamily: MONO,
            fontSize: 12,
            lineHeight: 1.6,
            color: C.verde,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {texto}
        </pre>
      ) : (
        <p style={{ fontSize: 12.5, color: TEXT.faint, margin: 0 }}>
          Nada saiu no terminal ainda.
        </p>
      )}
    </Caixa>
  );
}

/** `ProdutoController.java` de `src/main/java/.../ProdutoController.java`. */
function nomeDoArquivo(caminho: string) {
  return caminho.split("/").pop() || caminho;
}

function Caixa({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div style={{ background: PANEL, borderRadius: 8, padding: 11.2, minWidth: 0 }}>
      <Kicker style={{ display: "block", marginBottom: 8.4 }}>{titulo}</Kicker>
      {children}
    </div>
  );
}

/** Os exemplos que a pessoa já pediu. */
function Biblioteca({
  exemplos,
  abertoId,
  carregando,
  onAbrir,
  onRemovido,
}: {
  exemplos: Walkthrough[];
  abertoId: string | null;
  carregando: boolean;
  onAbrir: (item: Walkthrough) => void;
  onRemovido: (id: string) => void;
}) {
  const [removendo, setRemovendo] = useState<string | null>(null);

  async function remover(item: Walkthrough) {
    setRemovendo(item.id);
    try {
      await walkthroughsApi.remove(item.id);
      onRemovido(item.id);
    } finally {
      setRemovendo(null);
    }
  }

  if (carregando && exemplos.length === 0) return null;
  if (exemplos.length === 0) {
    return (
      <EmptyState
        title="Nenhum exemplo ainda"
        description="Escolha a linguagem e o assunto acima. O exemplo fica guardado aqui para você voltar quantas vezes quiser."
      />
    );
  }

  return (
    <section>
      <Kicker style={{ display: "block", marginBottom: 8.4 }}>Seus exemplos</Kicker>
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {exemplos.map((item) => {
          const ativo = item.id === abertoId;
          return (
            <li
              key={item.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 11.2,
                padding: "8.4px 0",
                borderTop: `1px solid ${HAIRLINE}`,
              }}
            >
              <button
                type="button"
                className="btn btn-ghost"
                style={{
                  flex: 1,
                  minWidth: 0,
                  justifyContent: "flex-start",
                  textAlign: "left",
                  color: ativo ? ACC : undefined,
                }}
                onClick={() => onAbrir(item)}
              >
                <Icon name="code" size={14} />
                <span style={{ marginLeft: 8.4, flex: 1, minWidth: 0 }}>
                  <span style={{ display: "block", fontSize: 13.5 }}>{item.title}</span>
                  <span style={{ display: "block", fontSize: 11.5, color: TEXT.faint }}>
                    {item.language_label} · {item.topic}
                    {(item.files?.length ?? 0) > 1 ? ` · ${item.files.length} arquivos` : ""}
                    {item.steps.length > 0
                      ? ` · ${item.steps.length} passos`
                      : " · sem passo a passo"}
                  </span>
                </span>
              </button>
              <IconButton
                icon="trash"
                label={removendo === item.id ? "Removendo…" : "Remover"}
                color={C.ambar}
                disabled={removendo === item.id}
                onClick={() => void remover(item)}
              />
            </li>
          );
        })}
      </ul>
    </section>
  );
}
