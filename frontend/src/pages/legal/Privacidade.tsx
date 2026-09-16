/**
 * Política de privacidade e uso de dados (LGPD, Lei 13.709/2018).
 *
 * Cada afirmação aqui corresponde a algo que o código faz — quando o código
 * mudar (um provedor novo, uma tabela nova na exportação, um prazo novo), este
 * texto precisa mudar junto. As fontes principais: backend/app/models.py,
 * routers/profile.py (exportação e exclusão), routers/social.py (o cartão),
 * routers/varredura.py (a triagem sem autor), config.py (os provedores).
 *
 * O texto sai do dicionário de idiomas; os nomes dos fornecedores, os endereços
 * e as siglas legais continuam no código, porque não se traduzem.
 */

import type { Traduzir } from "@/lib/i18n";
import { EmailContato, Fichas, Forte, LinkDoc, Lista, Nota, P, Subtitulo, type DocumentoLegal } from "./LegalLayout";

export const CAMINHO_PRIVACIDADE = "/privacidade";

export function privacidade(t: Traduzir): DocumentoLegal {
  /** As fichas de fornecedores: o nome é do fornecedor, o resto é texto. */
  const ficha = (nome: string, indice: number) => ({
    nome,
    papel: t(`legal.privacidade.compartilhamento.fichas.${indice}.papel`),
    detalhe: t(`legal.privacidade.compartilhamento.fichas.${indice}.detalhe`),
  });

  const direito = (indice: number) => ({
    nome: t(`legal.privacidade.direitos.fichas.${indice}.nome`),
    papel: t(`legal.privacidade.direitos.fichas.${indice}.papel`),
    detalhe: t(`legal.privacidade.direitos.fichas.${indice}.detalhe`),
  });

  return {
    path: CAMINHO_PRIVACIDADE,
    aba: t("legal.privacidade.aba"),
    kicker: t("legal.privacidade.kicker"),
    titulo: t("legal.privacidade.titulo"),
    introducao: t("legal.privacidade.introducao"),
    resumo: [
      t("legal.privacidade.resumo.0"),
      t("legal.privacidade.resumo.1"),
      t("legal.privacidade.resumo.2"),
      t("legal.privacidade.resumo.3"),
      t("legal.privacidade.resumo.4"),
      t("legal.privacidade.resumo.5"),
    ],
    secoes: [
      {
        id: "controlador",
        titulo: t("legal.privacidade.controlador.titulo"),
        corpo: (
          <>
            <P>
              {t("legal.privacidade.controlador.p1a")} <Forte>pathr.notter.com.br</Forte>
              {t("legal.privacidade.controlador.p1b")} <Forte>api.pathr.notter.com.br</Forte>
              {t("legal.privacidade.controlador.p1c")} <Forte>Rodrigo Carvalho</Forte>
              {t("legal.privacidade.controlador.p1d")}
            </P>
            <P>
              {t("legal.privacidade.controlador.p2")} <EmailContato />.
            </P>
            <P>{t("legal.privacidade.controlador.p3")}</P>
          </>
        ),
      },
      {
        id: "dados-coletados",
        titulo: t("legal.privacidade.dadosColetados.titulo"),
        corpo: (
          <>
            <Subtitulo>{t("legal.privacidade.dadosColetados.contaTitulo")}</Subtitulo>
            <Lista
              itens={[
                t("legal.privacidade.dadosColetados.conta.0"),
                t("legal.privacidade.dadosColetados.conta.1"),
                t("legal.privacidade.dadosColetados.conta.2"),
                t("legal.privacidade.dadosColetados.conta.3"),
                t("legal.privacidade.dadosColetados.conta.4"),
              ]}
            />
            <Subtitulo>{t("legal.privacidade.dadosColetados.perfilTitulo")}</Subtitulo>
            <Lista
              itens={[
                t("legal.privacidade.dadosColetados.perfil.0"),
                t("legal.privacidade.dadosColetados.perfil.1"),
                t("legal.privacidade.dadosColetados.perfil.2"),
                t("legal.privacidade.dadosColetados.perfil.3"),
              ]}
            />
            <Subtitulo>{t("legal.privacidade.dadosColetados.curriculoTitulo")}</Subtitulo>
            <Lista
              itens={[
                t("legal.privacidade.dadosColetados.curriculo.0"),
                t("legal.privacidade.dadosColetados.curriculo.1"),
              ]}
            />
            <Nota>{t("legal.privacidade.dadosColetados.notaCurriculo")}</Nota>
            <Subtitulo>{t("legal.privacidade.dadosColetados.estudoTitulo")}</Subtitulo>
            <Lista
              itens={[
                t("legal.privacidade.dadosColetados.estudo.0"),
                t("legal.privacidade.dadosColetados.estudo.1"),
                t("legal.privacidade.dadosColetados.estudo.2"),
                t("legal.privacidade.dadosColetados.estudo.3"),
                t("legal.privacidade.dadosColetados.estudo.4"),
              ]}
            />
            <Subtitulo>{t("legal.privacidade.dadosColetados.pessoasTitulo")}</Subtitulo>
            <Lista
              itens={[
                t("legal.privacidade.dadosColetados.pessoas.0"),
                t("legal.privacidade.dadosColetados.pessoas.1"),
              ]}
            />
            <Subtitulo>{t("legal.privacidade.dadosColetados.tecnicosTitulo")}</Subtitulo>
            <Lista
              itens={[
                t("legal.privacidade.dadosColetados.tecnicos.0"),
                t("legal.privacidade.dadosColetados.tecnicos.1"),
                t("legal.privacidade.dadosColetados.tecnicos.2"),
                t("legal.privacidade.dadosColetados.tecnicos.3"),
              ]}
            />
            <Subtitulo>{t("legal.privacidade.dadosColetados.naoColetamosTitulo")}</Subtitulo>
            <Lista
              itens={[
                t("legal.privacidade.dadosColetados.naoColetamos.0"),
                t("legal.privacidade.dadosColetados.naoColetamos.1"),
                t("legal.privacidade.dadosColetados.naoColetamos.2"),
              ]}
            />
          </>
        ),
      },
      {
        id: "finalidades",
        titulo: t("legal.privacidade.finalidades.titulo"),
        corpo: (
          <>
            <Lista
              itens={[0, 1, 2, 3, 4, 5, 6].map((indice) => (
                <>
                  <Forte>{t(`legal.privacidade.finalidades.itens.${indice}.forte`)}</Forte>
                  {t(`legal.privacidade.finalidades.itens.${indice}.resto`)}
                </>
              ))}
            />
            <Nota>{t("legal.privacidade.finalidades.nota")}</Nota>
          </>
        ),
      },
      {
        id: "inteligencia-artificial",
        titulo: t("legal.privacidade.ia.titulo"),
        corpo: (
          <>
            <P>{t("legal.privacidade.ia.p1")}</P>
            <Lista
              itens={[
                t("legal.privacidade.ia.itens.0"),
                t("legal.privacidade.ia.itens.1"),
                t("legal.privacidade.ia.itens.2"),
              ]}
            />
            <P>
              {t("legal.privacidade.ia.p2a")} <Forte>Google Gemini, Groq, Cerebras, Mistral AI e OpenRouter</Forte>
              {t("legal.privacidade.ia.p2b")}
            </P>
            <P>{t("legal.privacidade.ia.p3")}</P>
          </>
        ),
      },
      {
        id: "compartilhamento",
        titulo: t("legal.privacidade.compartilhamento.titulo"),
        corpo: (
          <>
            <P>{t("legal.privacidade.compartilhamento.p1")}</P>
            <Fichas
              itens={[
                ficha("Supabase", 0),
                ficha("Fly.io", 1),
                ficha("Cloudflare Pages", 2),
                ficha("Brevo", 3),
                ficha("Google Gemini, Groq, Cerebras, Mistral AI, OpenRouter", 4),
                ficha("DeepL", 5),
                ficha("Tavily, Brave Search e YouTube Data API", 6),
                ficha("Adzuna, Gupy e Remotive", 7),
                ficha("YouTube (Google)", 8),
                ficha("Google Fonts", 9),
                ficha("Notion", 10),
                ficha("Anthropic (Claude)", 11),
              ]}
            />
            <P>{t("legal.privacidade.compartilhamento.p2")}</P>
            <Lista
              itens={[
                t("legal.privacidade.compartilhamento.itens.0"),
                t("legal.privacidade.compartilhamento.itens.1"),
                t("legal.privacidade.compartilhamento.itens.2"),
              ]}
            />
          </>
        ),
      },
      {
        id: "outras-pessoas",
        titulo: t("legal.privacidade.outrasPessoas.titulo"),
        corpo: (
          <>
            <P>
              {t("legal.privacidade.outrasPessoas.p1a")} <Forte>{t("legal.privacidade.outrasPessoas.p1forte")}</Forte>
              {t("legal.privacidade.outrasPessoas.p1b")}
            </P>
            <P>
              {t("legal.privacidade.outrasPessoas.p2a")} <Forte>{t("legal.privacidade.outrasPessoas.p2forte")}</Forte>{" "}
              {t("legal.privacidade.outrasPessoas.p2b")}
            </P>
            <Lista
              itens={[
                <>
                  <Forte>{t("legal.privacidade.outrasPessoas.sugestoesForte")}</Forte>
                  {t("legal.privacidade.outrasPessoas.sugestoesResto")}
                </>,
                <>
                  {t("legal.privacidade.outrasPessoas.arrobaA")}{" "}
                  <Forte>{t("legal.privacidade.outrasPessoas.arrobaForte")}</Forte>{" "}
                  {t("legal.privacidade.outrasPessoas.arrobaB")}
                </>,
                <>{t("legal.privacidade.outrasPessoas.convite")}</>,
              ]}
            />
          </>
        ),
      },
      {
        id: "relatos",
        titulo: t("legal.privacidade.relatos.titulo"),
        corpo: (
          <>
            <P>{t("legal.privacidade.relatos.p1")}</P>
            <P>
              {t("legal.privacidade.relatos.p2a")} <Forte>{t("legal.privacidade.relatos.p2forte")}</Forte>
              {t("legal.privacidade.relatos.p2b")}
            </P>
          </>
        ),
      },
      {
        id: "retencao",
        titulo: t("legal.privacidade.retencao.titulo"),
        corpo: (
          <>
            <Lista
              itens={[
                ...[0, 1, 2, 3, 4].map((indice) => (
                  <>
                    <Forte>{t(`legal.privacidade.retencao.itens.${indice}.forte`)}</Forte>
                    {t(`legal.privacidade.retencao.itens.${indice}.resto`)}
                  </>
                )),
                <>
                  <Forte>{t("legal.privacidade.retencao.registrosForte1")}</Forte>
                  {t("legal.privacidade.retencao.registrosMeio")}{" "}
                  <Forte>{t("legal.privacidade.retencao.registrosForte2")}</Forte>
                  {t("legal.privacidade.retencao.registrosResto")}
                </>,
                <>
                  <Forte>{t("legal.privacidade.retencao.itens.5.forte")}</Forte>
                  {t("legal.privacidade.retencao.itens.5.resto")}
                </>,
              ]}
            />
            <Nota>
              {t("legal.privacidade.retencao.nota")} <EmailContato />.
            </Nota>
          </>
        ),
      },
      {
        id: "direitos",
        titulo: t("legal.privacidade.direitos.titulo"),
        corpo: (
          <>
            <P>{t("legal.privacidade.direitos.p1")}</P>
            <Fichas itens={[0, 1, 2, 3, 4, 5].map(direito)} />
            <P>{t("legal.privacidade.direitos.p2")}</P>
          </>
        ),
      },
      {
        id: "idade",
        titulo: t("legal.privacidade.idade.titulo"),
        corpo: (
          <P>
            {t("legal.privacidade.idade.p1a")} <Forte>{t("legal.privacidade.idade.p1forte")}</Forte>{" "}
            {t("legal.privacidade.idade.p1b")}
          </P>
        ),
      },
      {
        id: "cookies",
        titulo: t("legal.privacidade.cookies.titulo"),
        corpo: (
          <>
            <Lista
              itens={[0, 1, 2].map((indice) => (
                <>
                  <Forte>{t(`legal.privacidade.cookies.itens.${indice}.forte`)}</Forte>
                  {t(`legal.privacidade.cookies.itens.${indice}.resto`)}
                </>
              ))}
            />
            <P>{t("legal.privacidade.cookies.p1")}</P>
          </>
        ),
      },
      {
        id: "transferencia",
        titulo: t("legal.privacidade.transferencia.titulo"),
        corpo: <P>{t("legal.privacidade.transferencia.p1")}</P>,
      },
      {
        id: "incidentes",
        titulo: t("legal.privacidade.incidentes.titulo"),
        corpo: (
          <P>
            {t("legal.privacidade.incidentes.p1a")}{" "}
            <LinkDoc href="/seguranca">{t("legal.privacidade.incidentes.p1link")}</LinkDoc>
            {t("legal.privacidade.incidentes.p1b")}
          </P>
        ),
      },
      {
        id: "mudancas",
        titulo: t("legal.privacidade.mudancas.titulo"),
        corpo: <P>{t("legal.privacidade.mudancas.p1")}</P>,
      },
    ],
  };
}
