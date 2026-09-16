/**
 * Segurança: o que protege a conta e os dados, dito sem exagero.
 *
 * Cada número daqui vem do código — services/limites.py (limites de uso),
 * config.py (sessão, bloqueio, tamanhos de upload), security.py (Argon2id,
 * regras de senha), seguranca_http.py e frontend/public/_headers (cabeçalhos).
 * Mudou lá, muda aqui. Nada de selo, certificação ou promessa que o código não
 * sustenta.
 *
 * O texto sai do dicionário de idiomas; os nomes técnicos (Argon2id, HttpOnly,
 * SameSite=Strict, Content-Security-Policy) continuam no código.
 */

import type { Traduzir } from "@/lib/i18n";
import { EmailContato, Fichas, Forte, LinkDoc, Lista, Nota, P, type DocumentoLegal } from "./LegalLayout";

export const CAMINHO_SEGURANCA = "/seguranca";

export function seguranca(t: Traduzir): DocumentoLegal {
  const limite = (indice: number) => ({
    nome: t(`legal.seguranca.limites.fichas.${indice}.nome`),
    papel: t(`legal.seguranca.limites.fichas.${indice}.papel`),
    detalhe: t(`legal.seguranca.limites.fichas.${indice}.detalhe`),
  });

  return {
    path: CAMINHO_SEGURANCA,
    aba: t("legal.seguranca.aba"),
    kicker: t("legal.seguranca.kicker"),
    titulo: t("legal.seguranca.titulo"),
    introducao: t("legal.seguranca.introducao"),
    resumo: [
      t("legal.seguranca.resumo.0"),
      t("legal.seguranca.resumo.1"),
      t("legal.seguranca.resumo.2"),
      t("legal.seguranca.resumo.3"),
      t("legal.seguranca.resumo.4"),
      t("legal.seguranca.resumo.5"),
      t("legal.seguranca.resumo.6"),
    ],
    secoes: [
      {
        id: "senhas",
        titulo: t("legal.seguranca.senhas.titulo"),
        corpo: (
          <Lista
            itens={[
              <>
                {t("legal.seguranca.senhas.hashA")} <Forte>Argon2id</Forte>
                {t("legal.seguranca.senhas.hashB")}
              </>,
              t("legal.seguranca.senhas.itens.0"),
              t("legal.seguranca.senhas.itens.1"),
              t("legal.seguranca.senhas.itens.2"),
              t("legal.seguranca.senhas.itens.3"),
              t("legal.seguranca.senhas.itens.4"),
            ]}
          />
        ),
      },
      {
        id: "fatores",
        titulo: t("legal.seguranca.fatores.titulo"),
        corpo: (
          <Lista
            itens={[
              <>
                <Forte>{t("legal.seguranca.fatores.passkeyForte")}</Forte>
                {t("legal.seguranca.fatores.passkeyResto")}
              </>,
              <>
                <Forte>{t("legal.seguranca.fatores.totpForte")}</Forte>
                {t("legal.seguranca.fatores.totpResto")}
              </>,
              t("legal.seguranca.fatores.desafio"),
            ]}
          />
        ),
      },
      {
        id: "sessao",
        titulo: t("legal.seguranca.sessao.titulo"),
        corpo: (
          <>
            <Lista
              itens={[
                <>
                  {t("legal.seguranca.sessao.cookiesA")} <Forte>HttpOnly</Forte>{" "}
                  {t("legal.seguranca.sessao.cookiesB")} <Forte>Secure</Forte>{" "}
                  {t("legal.seguranca.sessao.cookiesC")} <Forte>SameSite=Strict</Forte>{" "}
                  {t("legal.seguranca.sessao.cookiesD")}
                </>,
                t("legal.seguranca.sessao.itens.0"),
                t("legal.seguranca.sessao.itens.1"),
                t("legal.seguranca.sessao.itens.2"),
              ]}
            />
            <P>
              {t("legal.seguranca.sessao.p1a")} <Forte>{t("legal.seguranca.sessao.p1forte")}</Forte>{" "}
              {t("legal.seguranca.sessao.p1b")}
            </P>
          </>
        ),
      },
      {
        id: "dados",
        titulo: t("legal.seguranca.dados.titulo"),
        corpo: (
          <Lista
            itens={[
              t("legal.seguranca.dados.itens.0"),
              t("legal.seguranca.dados.itens.1"),
              t("legal.seguranca.dados.itens.2"),
              t("legal.seguranca.dados.itens.3"),
              t("legal.seguranca.dados.itens.4"),
              t("legal.seguranca.dados.itens.5"),
              t("legal.seguranca.dados.itens.6"),
            ]}
          />
        ),
      },
      {
        id: "navegador",
        titulo: t("legal.seguranca.navegador.titulo"),
        corpo: (
          <Lista
            itens={[
              <>
                {t("legal.seguranca.navegador.httpsA")} <Forte>HTTPS</Forte>
                {t("legal.seguranca.navegador.httpsB")}
              </>,
              <>
                <Forte>Content-Security-Policy</Forte> {t("legal.seguranca.navegador.csp")}
              </>,
              t("legal.seguranca.navegador.itens.0"),
              t("legal.seguranca.navegador.itens.1"),
              t("legal.seguranca.navegador.itens.2"),
              t("legal.seguranca.navegador.itens.3"),
            ]}
          />
        ),
      },
      {
        id: "arquivos",
        titulo: t("legal.seguranca.arquivos.titulo"),
        corpo: (
          <Lista
            itens={[
              t("legal.seguranca.arquivos.itens.0"),
              t("legal.seguranca.arquivos.itens.1"),
              t("legal.seguranca.arquivos.itens.2"),
              t("legal.seguranca.arquivos.itens.3"),
              t("legal.seguranca.arquivos.itens.4"),
            ]}
          />
        ),
      },
      {
        id: "limites",
        titulo: t("legal.seguranca.limites.titulo"),
        corpo: (
          <>
            <P>{t("legal.seguranca.limites.p1")}</P>
            <Fichas itens={[0, 1, 2, 3, 4, 5, 6].map(limite)} />
          </>
        ),
      },
      {
        id: "monitoramento",
        titulo: t("legal.seguranca.monitoramento.titulo"),
        corpo: (
          <Lista
            itens={[
              t("legal.seguranca.monitoramento.itens.0"),
              t("legal.seguranca.monitoramento.itens.1"),
              t("legal.seguranca.monitoramento.itens.2"),
            ]}
          />
        ),
      },
      {
        id: "sua-parte",
        titulo: t("legal.seguranca.suaParte.titulo"),
        corpo: (
          <>
            <Lista
              itens={[
                t("legal.seguranca.suaParte.itens.0"),
                t("legal.seguranca.suaParte.itens.1"),
                t("legal.seguranca.suaParte.itens.2"),
                t("legal.seguranca.suaParte.itens.3"),
                t("legal.seguranca.suaParte.itens.4"),
              ]}
            />
          </>
        ),
      },
      {
        id: "vulnerabilidades",
        titulo: t("legal.seguranca.vulnerabilidades.titulo"),
        corpo: (
          <>
            <P>
              {t("legal.seguranca.vulnerabilidades.p1a")} <EmailContato />{" "}
              {t("legal.seguranca.vulnerabilidades.p1b")}
            </P>
          </>
        ),
      },
      {
        id: "limitacoes",
        titulo: t("legal.seguranca.limitacoes.titulo"),
        corpo: (
          <Nota tom="atencao">
            {t("legal.seguranca.limitacoes.notaA")}{" "}
            <LinkDoc href="/privacidade">{t("legal.seguranca.limitacoes.notaLink")}</LinkDoc>
            {t("legal.seguranca.limitacoes.notaB")}
          </Nota>
        ),
      },
    ],
  };
}
