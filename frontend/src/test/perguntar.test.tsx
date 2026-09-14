/**
 * O "Perguntar": a pessoa à esquerda, o tutor à direita, e a pergunta final.
 *
 * O que se segura: abrir manda só onde a pessoa está (tipo + id + trecho), não
 * o conteúdo; a conversa mostra quem falou de que lado; depois da explicação
 * aparecem "Sim, entendi" e "Ainda não"; "Ainda não" pede outra explicação; e
 * a resposta do tutor é texto (um <script> nela não vira elemento).
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DuvidaConversa } from "@/api/types";
import { Perguntar } from "@/components/duvidas/Perguntar";
import { mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

const PERGUNTA_FINAL = "A explicação ficou clara? Conseguiu entender?";

const conversa = (mensagens: DuvidaConversa["mensagens"], extra: Partial<DuvidaConversa> = {}): DuvidaConversa => ({
  id: "d1",
  contexto_tipo: "laboratorio",
  contexto_titulo: "Modificadores de acesso",
  conceito: "private vs protected",
  status: "aberta",
  entendeu: null,
  criada_em: "2026-09-14T10:00:00+00:00",
  mensagens,
  ...extra,
});

const pessoa = (id: string, texto: string) => ({ id, papel: "pessoa" as const, texto, criada_em: null });
const tutor = (id: string, texto: string) => ({ id, papel: "tutor" as const, texto, criada_em: null });

describe("texto do tutor formatado", () => {
  it("parágrafos, listas, negrito e código viram elementos — e nada vira HTML", async () => {
    const { TextoFormatado } = await import("@/components/duvidas/TextoFormatado");
    const texto = [
      "Em Java, **modificadores de acesso** controlam quem vê um membro.",
      "",
      "- `public`: qualquer classe",
      "- `private`: só a própria classe",
      "",
      "```java",
      "private int privado = 20;",
      "```",
      "<img src=x onerror=alert(1)>",
      "",
      PERGUNTA_FINAL,
    ].join("\n");
    const { container } = render(<TextoFormatado texto={texto} />);
    expect(screen.getByText("modificadores de acesso").tagName).toBe("STRONG");
    const itens = screen.getAllByRole("listitem");
    expect(itens).toHaveLength(2);
    expect(within(itens[0]).getByText("public").tagName).toBe("CODE");
    expect(screen.getByLabelText("Código em java")).toHaveTextContent("private int privado = 20;");
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText(PERGUNTA_FINAL).tagName).toBe("P");
  });
});

describe("Perguntar", () => {
  it("abre com o contexto, mostra pessoa à esquerda e tutor à direita, e pergunta se ficou claro", async () => {
    let entendeuCorpo: unknown = null;
    const servidor = mockServer({
      "GET /duvidas": () => ({ body: [] }),
      "POST /duvidas": () => ({
        status: 201,
        body: conversa([
          pessoa("m1", "Por que o privado não aparece?"),
          tutor("m2", `private só existe dentro da classe.\n\`\`\`java\nprivate int x;\n\`\`\`\n<script>alert(1)</script>\n${PERGUNTA_FINAL}`),
        ]),
      }),
      "POST /duvidas/d1/entendeu": (pedido) => {
        entendeuCorpo = pedido.body;
        return {
          body: conversa([
            pessoa("m1", "Por que o privado não aparece?"),
            tutor("m2", `private só existe dentro da classe. ${PERGUNTA_FINAL}`),
            pessoa("m3", "Ainda não entendi."),
            tutor("m4", `Pense numa gaveta trancada. ${PERGUNTA_FINAL}`),
          ]),
        };
      },
    });
    const user = userEvent.setup();
    const { container } = render(<Perguntar contextoTipo="laboratorio" contextoRef="w1" trecho="Passo 5, linha 18" />);

    await user.click(screen.getByRole("button", { name: /Perguntar/ }));
    await user.type(screen.getByLabelText("Sua dúvida"), "Por que o privado não aparece?");
    await user.click(screen.getByRole("button", { name: /Enviar/ }));

    const conversaNaTela = await screen.findByRole("list", { name: "Conversa" });
    await within(conversaNaTela).findByLabelText("Tutor");
    const [primeira, segunda] = within(conversaNaTela).getAllByRole("listitem");
    expect(primeira).toHaveAccessibleName("Você");
    expect(primeira).toHaveStyle({ justifyContent: "flex-start" });
    expect(segunda).toHaveAccessibleName("Tutor");
    expect(segunda).toHaveStyle({ justifyContent: "flex-end" });
    expect(within(segunda).getByText("private int x;").tagName).toBe("PRE");
    // Campo e botão na mesma moldura; o botão é só o ícone, com nome acessível.
    const enviarBotao = screen.getByRole("button", { name: "Enviar" });
    expect(enviarBotao).toHaveTextContent("");
    expect(enviarBotao.closest("form")).toContainElement(screen.getByLabelText("Sua dúvida"));
    expect(enviarBotao.closest("form")).toHaveClass("compositor");
    expect(container.querySelector("script")).toBeNull();

    const envio = servidor.calls.find((c) => c.method === "POST" && c.url === "/duvidas");
    expect(envio?.body).toEqual({
      contexto_tipo: "laboratorio",
      contexto_ref: "w1",
      trecho: "Passo 5, linha 18",
      pergunta: "Por que o privado não aparece?",
    });

    const retorno = screen.getByRole("group", { name: "A explicação ficou clara?" });
    await user.click(within(retorno).getByRole("button", { name: "Ainda não" }));
    expect(await screen.findByText(/gaveta trancada/)).toBeInTheDocument();
    expect(entendeuCorpo).toEqual({ entendeu: false });
  });

  it("sugere exemplo para depurar, gera e abre no Laboratório", async () => {
    const aberta = conversa([
      pessoa("m1", "como o protected funciona na subclasse?"),
      { ...tutor("m2", `Assim: \`\`\`java\nclass B extends A {}\n\`\`\` ${PERGUNTA_FINAL}`), sugestoes: [{ linguagem: "java", topico: "subclasse acessando protected" }] },
    ]);
    let pedido: unknown = null;
    mockServer({
      "GET /duvidas": () => ({ body: [aberta] }),
      "POST /duvidas/d1/exemplo": (req) => {
        pedido = req.body;
        return { body: conversa([...aberta.mensagens, { ...tutor("m3", "Gerei um exemplo de **protected** em Java."), exemplo_id: "w9" }]) };
      },
    });
    const abriu = vi.fn();
    window.addEventListener("pathr:abrir-exemplo", abriu);
    const user = userEvent.setup();
    render(<Perguntar contextoTipo="laboratorio" contextoRef="w1" />);

    await user.click(screen.getByRole("button", { name: /Perguntar/ }));
    await user.click(await screen.findByRole("button", { name: /Gerar exemplo para depurar: subclasse acessando protected/ }));
    expect(pedido).toEqual({ linguagem: "java", topico: "subclasse acessando protected" });

    await user.click(await screen.findByRole("button", { name: /Abrir no depurador/ }));
    expect(abriu).toHaveBeenCalledTimes(1);
    expect(JSON.parse(window.localStorage.getItem("pathr:codigo") || "{}")).toEqual({ id: "w9", passo: 0 });
    window.removeEventListener("pathr:abrir-exemplo", abriu);
  });

  it("mostra a fala na hora e os pontinhos do tutor enquanto ele responde, sem barra", async () => {
    mockServer({ "GET /duvidas": () => ({ body: [] }) });
    // O servidor falso responde na hora; aqui a resposta do POST fica presa até
    // o teste soltar, para ver a tela no meio da espera.
    const fetchDoTeste = globalThis.fetch;
    let soltar: () => void = () => {};
    const resposta = conversa([pessoa("m1", "o que é um commit?"), tutor("m2", `Um registro. ${PERGUNTA_FINAL}`)]);
    vi.stubGlobal("fetch", (entrada: RequestInfo | URL, init?: RequestInit) => {
      if ((init?.method ?? "GET").toUpperCase() === "POST" && String(entrada).endsWith("/duvidas")) {
        return new Promise<Response>((resolve) => {
          soltar = () =>
            resolve(new Response(JSON.stringify(resposta), { status: 201, headers: { "Content-Type": "application/json" } }));
        });
      }
      return fetchDoTeste(entrada, init);
    });
    const user = userEvent.setup();
    render(<Perguntar contextoTipo="geral" />);
    await user.click(screen.getByRole("button", { name: /Perguntar/ }));
    await user.type(screen.getByLabelText("Sua dúvida"), "o que é um commit?");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("o que é um commit?")).toBeInTheDocument();
    expect(screen.getByLabelText("Tutor está escrevendo")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();

    soltar();
    expect(await screen.findByText(/Um registro/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Tutor está escrevendo")).not.toBeInTheDocument();
  });

  it("continua a conversa aberta e fecha ao entender", async () => {
    const aberta = conversa([pessoa("m1", "o que é push?"), tutor("m2", `Envia commits. ${PERGUNTA_FINAL}`)]);
    const servidor = mockServer({
      "GET /duvidas": () => ({ body: [aberta] }),
      "POST /duvidas/d1/mensagens": () => ({
        body: conversa([...aberta.mensagens, pessoa("m3", "e o pull?"), tutor("m4", `Traz commits. ${PERGUNTA_FINAL}`)]),
      }),
      "POST /duvidas/d1/entendeu": () => ({
        body: conversa([...aberta.mensagens, tutor("m5", "Ótimo! Esse tema fica guardado.")], { status: "entendida", entendeu: true }),
      }),
    });
    const user = userEvent.setup();
    render(<Perguntar contextoTipo="atividade" contextoRef="a1" />);

    await user.click(screen.getByRole("button", { name: /Perguntar/ }));
    expect(await screen.findByText(/Envia commits/)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Sua dúvida"), "e o pull?");
    await user.click(screen.getByRole("button", { name: /Enviar/ }));
    expect(await screen.findByText(/Traz commits/)).toBeInTheDocument();
    expect(servidor.calls.some((c) => c.url === "/duvidas/d1/mensagens")).toBe(true);

    await user.click(screen.getByRole("button", { name: /Sim, entendi/ }));
    expect(await screen.findByText(/Esse tema fica guardado/)).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "A explicação ficou clara?" })).not.toBeInTheDocument();
  });
});
