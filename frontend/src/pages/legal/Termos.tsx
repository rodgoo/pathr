/**
 * Termos de uso.
 *
 * O que o PathR oferece, o que se espera de quem usa e os limites do que o app
 * promete. A idade mínima (18) vem de backend/app/schemas/auth.py; o resto do
 * que é fato técnico está detalhado em Privacidade.tsx e Seguranca.tsx, e aqui
 * só é referido — duas descrições do mesmo fato divergiriam.
 *
 * O texto sai do dicionário de idiomas: o documento é montado por uma função
 * que recebe o `t` de quem desenha a página, e não por uma constante de módulo
 * — uma constante seria congelada no idioma do primeiro carregamento.
 */

import type { Traduzir } from "@/lib/i18n";
import { EmailContato, Forte, LinkDoc, Lista, Nota, P, type DocumentoLegal } from "./LegalLayout";

export const CAMINHO_TERMOS = "/termos";

export function termos(t: Traduzir): DocumentoLegal {
  return {
    path: CAMINHO_TERMOS,
    aba: t("legal.termos.aba"),
    kicker: t("legal.termos.kicker"),
    titulo: t("legal.termos.titulo"),
    introducao: t("legal.termos.introducao"),
    resumo: [
      t("legal.termos.resumo.0"),
      t("legal.termos.resumo.1"),
      t("legal.termos.resumo.2"),
      t("legal.termos.resumo.3"),
      t("legal.termos.resumo.4"),
      t("legal.termos.resumo.5"),
    ],
    secoes: [
      {
        id: "aceitacao",
        titulo: t("legal.termos.aceitacao.titulo"),
        corpo: (
          <>
            <P>
              {t("legal.termos.aceitacao.p1a")}{" "}
              <LinkDoc href="/privacidade">{t("legal.termos.aceitacao.p1link")}</LinkDoc>
              {t("legal.termos.aceitacao.p1b")}
            </P>
            <P>{t("legal.termos.aceitacao.p2")}</P>
          </>
        ),
      },
      {
        id: "servico",
        titulo: t("legal.termos.servico.titulo"),
        corpo: (
          <>
            <P>
              {t("legal.termos.servico.p1a")} <Forte>{t("legal.termos.servico.p1forte")}</Forte>{" "}
              {t("legal.termos.servico.p1b")}
            </P>
            <P>{t("legal.termos.servico.p2")}</P>
          </>
        ),
      },
      {
        id: "conta",
        titulo: t("legal.termos.conta.titulo"),
        corpo: (
          <Lista
            itens={[
              <>
                {t("legal.termos.conta.idadeA")} <Forte>{t("legal.termos.conta.idadeForte")}</Forte>
                {t("legal.termos.conta.idadeB")}
              </>,
              t("legal.termos.conta.itens.0"),
              t("legal.termos.conta.itens.1"),
              t("legal.termos.conta.itens.2"),
            ]}
          />
        ),
      },
      {
        id: "ia",
        titulo: t("legal.termos.ia.titulo"),
        corpo: (
          <>
            <P>{t("legal.termos.ia.p1")}</P>
            <Nota tom="atencao">
              {t("legal.termos.ia.notaA")} <Forte>{t("legal.termos.ia.notaForte")}</Forte>
              {t("legal.termos.ia.notaB")}
            </Nota>
            <Lista
              itens={[t("legal.termos.ia.itens.0"), t("legal.termos.ia.itens.1"), t("legal.termos.ia.itens.2")]}
            />
          </>
        ),
      },
      {
        id: "uso-aceitavel",
        titulo: t("legal.termos.usoAceitavel.titulo"),
        corpo: (
          <>
            <P>{t("legal.termos.usoAceitavel.intro")}</P>
            <Lista
              itens={[
                t("legal.termos.usoAceitavel.itensAntes.0"),
                t("legal.termos.usoAceitavel.itensAntes.1"),
                t("legal.termos.usoAceitavel.itensAntes.2"),
                t("legal.termos.usoAceitavel.itensAntes.3"),
                <>
                  {t("legal.termos.usoAceitavel.falhasA")}{" "}
                  <LinkDoc href="/seguranca">{t("legal.termos.usoAceitavel.falhasLink")}</LinkDoc>
                  {t("legal.termos.usoAceitavel.falhasB")}
                </>,
                t("legal.termos.usoAceitavel.itensDepois.0"),
                t("legal.termos.usoAceitavel.itensDepois.1"),
              ]}
            />
          </>
        ),
      },
      {
        id: "social",
        titulo: t("legal.termos.social.titulo"),
        corpo: (
          <>
            <P>
              {t("legal.termos.social.p1a")}{" "}
              <LinkDoc href="/privacidade">{t("legal.termos.social.p1link")}</LinkDoc>.
            </P>
            <Lista
              itens={[
                t("legal.termos.social.itens.0"),
                t("legal.termos.social.itens.1"),
                t("legal.termos.social.itens.2"),
              ]}
            />
          </>
        ),
      },
      {
        id: "seu-conteudo",
        titulo: t("legal.termos.seuConteudo.titulo"),
        corpo: (
          <>
            <P>
              {t("legal.termos.seuConteudo.p1a")} <Forte>{t("legal.termos.seuConteudo.p1forte")}</Forte>.
            </P>
            <P>
              {t("legal.termos.seuConteudo.p2a")}{" "}
              <LinkDoc href="/privacidade">{t("legal.termos.seuConteudo.p2link")}</LinkDoc>{" "}
              {t("legal.termos.seuConteudo.p2b")}
            </P>
            <P>{t("legal.termos.seuConteudo.p3")}</P>
          </>
        ),
      },
      {
        id: "propriedade",
        titulo: t("legal.termos.propriedade.titulo"),
        corpo: <P>{t("legal.termos.propriedade.p1")}</P>,
      },
      {
        id: "moderacao",
        titulo: t("legal.termos.moderacao.titulo"),
        corpo: (
          <>
            <P>{t("legal.termos.moderacao.p1")}</P>
            <P>{t("legal.termos.moderacao.p2")}</P>
          </>
        ),
      },
      {
        id: "responsabilidade",
        titulo: t("legal.termos.responsabilidade.titulo"),
        corpo: (
          <>
            <P>{t("legal.termos.responsabilidade.p1")}</P>
            <P>{t("legal.termos.responsabilidade.p2")}</P>
          </>
        ),
      },
      {
        id: "mudancas",
        titulo: t("legal.termos.mudancas.titulo"),
        corpo: <P>{t("legal.termos.mudancas.p1")}</P>,
      },
      {
        id: "lei",
        titulo: t("legal.termos.lei.titulo"),
        corpo: (
          <P>
            {t("legal.termos.lei.p1a")} <EmailContato /> {t("legal.termos.lei.p1b")}
          </P>
        ),
      },
    ],
  };
}
