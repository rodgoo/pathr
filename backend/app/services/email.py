"""E-mail transacional via Brevo, na conta do próprio PathR.

## Por que isto é HTML escrito à mão, e por que ele é antiquado por dentro

Cliente de e-mail não é navegador. O Outlook desenha com o motor do Word, o
Gmail apaga `<style>`, e nenhum dos dois tem flexbox ou grid confiável. O que
funciona nos dois é o que funcionava em 2005: tabelas aninhadas e estilo
inline em cada elemento. O HTML aqui é atrasado de propósito — trocar isso por
um layout moderno quebraria a caixa de entrada de quem usa Outlook sem quebrar
nenhum teste.

## As três defesas que o desenho precisa ter

1. **Imagem desligada.** Boa parte dos clientes bloqueia imagem até a pessoa
   liberar o remetente. Então o logotipo NUNCA carrega sozinho a identidade:
   ao lado dele vem "PathR" como texto de verdade. Com a imagem bloqueada o
   topo continua lendo PathR, e não um retângulo vazio.
2. **SVG não existe.** Gmail e Outlook descartam SVG. O logotipo vai como PNG
   (frontend/public/logo-email.png, gerado do logo.svg em 128px para telas
   retina e exibido em 40px).
3. **Fundo escuro precisa ser pintado.** Cliente que ignora o CSS do corpo põe
   a mensagem sobre branco; se o texto claro não tiver fundo escuro pintado
   ATRÁS dele, some. Cada tabela pinta o próprio `bgcolor`.
4. **O app do Gmail no celular inverte as cores.** Em modo escuro ele "clareia"
   o que é escuro: o e-mail preto chegava BRANCO no celular e preto no
   computador. Duas travas, que só agem dentro do Gmail:
   - o fundo vai também como `background-image` (um degradê de uma cor só) —
     imagem de fundo o Gmail não inverte;
   - o texto vai dentro de `_nitido()`: duas camadas com `mix-blend-mode`
     (screen e difference) que desfazem a inversão pixel a pixel. O seletor
     `u + .body` só existe no HTML que o Gmail monta; nos outros clientes a
     regra não casa, e as camadas são invisíveis.

## O assunto carrega o conteúdo, não o nome do app

"Novidades do PathR" não diz nada e ensina a ignorar. "Seu plano de hoje: 3
itens, 45 min" é lido na lista da caixa de entrada sem abrir — e quem não tem
tempo hoje decide sem precisar abrir, que é um favor, não uma perda.

## Uma família, cinco temperaturas

Todos têm o mesmo cabeçalho, a mesma tipografia e o mesmo pé. O que muda é a
cor do fio sob a marca e o rótulo acima do título: roxo para a marca e para o
plano, âmbar para o que exige atenção (senha, sequência por um fio), verde
para o que já foi feito. A pessoa reconhece qual é antes de ler o título.

## Sem `brevo_api_key`

`_send` registra no log e devolve False em vez de levantar. Isso mantém o app
usável num clone novo (dá para cadastrar: o link aparece no log do servidor) e
garante que uma falha de e-mail nunca derrube o cadastro em si.
"""

import logging
from datetime import datetime
from html import escape
from typing import Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from app.config import settings

logger = logging.getLogger("pathr.email")

_BREVO_URL = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT = 10

# ---------------------------------------------------------------------------
# Paleta
#
# O e-mail é PRETO, e não o azul-noite do app. Na caixa de entrada ele divide a
# tela com o cliente de e-mail em modo escuro, que é preto ou quase: o azul do
# app lia ali como um cartão acinzentado e desbotado. Os acentos (roxo, verde,
# âmbar) continuam os do app — são eles que dizem que a mensagem é do PathR.
#
# Sem diferença de tom entre fundo e cartão, a estrutura passa a ser desenhada
# por LINHA: o cartão, o placar e o logotipo ganham um contorno fino. Os cinzas
# do texto são neutros, recalibrados para o preto puro — os de antes eram
# azulados para conversar com o fundo antigo, e sobre preto puxavam para o
# lilás. O mais fraco ainda passa de 6:1 de contraste, o bastante para os 12px
# do rodapé.
# ---------------------------------------------------------------------------
_FUNDO = "#000000"
_PAINEL = "#000000"
# Um degrau acima do preto, para o placar ser caixa e não buraco.
_SUPERFICIE = "#0e0e11"
_TINTA = "#f4f4f6"
_TINTA_SUAVE = "#c4c4cc"
_TINTA_FRACA = "#8d8d97"
_LINHA = "#26262c"

_ROXO = "#9184d9"  # ACC
_ROXO_CLARO = "#b5abfc"  # ACC4
_VERDE = "#63b48f"
_AMBAR = "#cfa25e"

# Pilha de fontes do sistema. Webfont em e-mail não carrega de forma confiável,
# e a falha aparece como serifada gigante — pior que não ter fonte própria.
_FONTE = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def _mascarar(email: str) -> str:
    """"ana@exemplo.com" vira "a***@exemplo.com": dá para achar o caso no log
    sem o log virar uma lista de e-mails de quem usa o app."""
    usuario, _, dominio = (email or "").partition("@")
    return f"{usuario[:1]}***@{dominio}" if dominio else "***"


def _send(
    to_email: str,
    to_name: str,
    subject: str,
    html: str,
    reply_to: Optional[dict[str, str]] = None,
    anexos: Optional[list[dict[str, str]]] = None,
) -> bool:
    """Manda o e-mail. `reply_to` e `anexos` existem por causa da candidatura.

    Quem envia é sempre o domínio do PathR (é dele o DKIM/SPF que faz o e-mail
    chegar). Numa candidatura, porém, quem precisa receber a resposta é a
    pessoa — daí o `Reply-To` com o e-mail dela, e o currículo em anexo.
    """
    if not settings.brevo_api_key or not settings.brevo_from_email:
        logger.warning(
            "BREVO_API_KEY ausente — e-mail %r para %s não foi enviado. Conteúdo: %s",
            subject,
            to_email,
            html,
        )
        return False
    try:
        response = httpx.post(
            _BREVO_URL,
            headers={"api-key": settings.brevo_api_key, "content-type": "application/json"},
            json={
                "sender": {"email": settings.brevo_from_email, "name": settings.brevo_sender_name},
                "to": [{"email": to_email, "name": to_name or to_email}],
                "subject": subject,
                "htmlContent": html,
                **({"replyTo": reply_to} if reply_to else {}),
                **({"attachment": anexos} if anexos else {}),
            },
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        logger.error("Falha de rede ao enviar e-mail para %s: %s", _mascarar(to_email), type(exc).__name__)
        return False
    if response.status_code >= 400:
        logger.error("Brevo recusou o e-mail para %s: HTTP %s", _mascarar(to_email), response.status_code)
        return False
    return True


# ---------------------------------------------------------------------------
# Peças do desenho
# ---------------------------------------------------------------------------


def _preto(cor: str) -> str:
    """Fundo pintado duas vezes: cor e imagem. O app do Gmail inverte a cor,
    mas não a imagem — e é a imagem que fica por cima."""
    return f"background-color:{cor};background-image:linear-gradient({cor},{cor})"


def _nitido(conteudo: str) -> str:
    """Texto que o modo escuro do Gmail não apaga. Ver a trava 4 no topo."""
    return f'<span class="gm-s"><span class="gm-d">{conteudo}</span></span>'


def _primeiro_nome(nome: str) -> str:
    """Só o primeiro nome, já escapado.

    "Bom dia, Ana Paula Ribeiro" soa com um formulário falando; "Bom dia, Ana"
    soa com alguém falando.
    """
    return escape((nome or "").strip().split(" ")[0])


def _numero(valor: float) -> str:
    """Decimal com vírgula. Ponto, em português, lê como separador de milhar."""
    return f"{valor:.1f}".replace(".", ",")


def _cabecalho(cor: str) -> str:
    """Logotipo + marca escrita + o fio da cor do assunto.

    A marca vem como TEXTO ao lado da imagem, não dentro dela: com imagem
    bloqueada — o padrão em boa parte dos clientes — um logotipo sozinho
    deixaria o topo vazio, e e-mail sem remetente visível é e-mail apagado.
    """
    logo = f"{settings.frontend_url}/logo-email.png"
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
  <tr>
    <td style="padding:0 0 22px 0">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="padding-right:12px" valign="middle">
            <!-- alt vazio de propósito: "PathR" está escrito na célula ao
                 lado. Com alt="PathR" o leitor de tela anunciaria a marca
                 duas vezes, e com a imagem bloqueada o texto alternativo
                 aparece na cor padrão do cliente — preto sobre este painel
                 escuro, ilegível e ao lado do nome repetido. -->
            <!-- O logotipo é um quadrado preto: sobre o fundo preto ele
                 sumiria e sobraria o símbolo solto. O contorno devolve a
                 forma do ladrilho; 38px + 1px de cada lado mantêm os 40. -->
            <img src="{logo}" width="38" height="38" alt=""
                 style="display:block;width:38px;height:38px;border:1px solid {_LINHA};
                        border-radius:10px" />
          </td>
          <td valign="middle">
            <span style="font-family:{_FONTE};font-size:19px;font-weight:600;
                         letter-spacing:-.01em;color:{_TINTA}">{_nitido("PathR")}</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td height="3" bgcolor="{cor}"
        style="font-size:0;line-height:0;height:3px;{_preto(cor)};
               border-radius:2px">&nbsp;</td>
  </tr>
</table>
""".strip()


def _titulo(rotulo: str, titulo: str, cor: str) -> str:
    return f"""
<div style="font-family:{_FONTE};font-size:11px;font-weight:600;letter-spacing:.14em;
            text-transform:uppercase;color:{cor};padding:26px 0 0">{_nitido(rotulo)}</div>
<h1 style="font-family:{_FONTE};font-size:26px;line-height:1.25;font-weight:600;
           letter-spacing:-.02em;color:{_TINTA};margin:10px 0 0">{_nitido(titulo)}</h1>
""".strip()


def _texto(corpo: str, topo: int = 14) -> str:
    return (
        f'<p style="font-family:{_FONTE};font-size:15px;line-height:1.65;color:{_TINTA_SUAVE};'
        f'margin:{topo}px 0 0">{_nitido(corpo)}</p>'
    )


def _botao(rotulo: str, url: str, cor: str) -> str:
    """Botão em tabela, e não `<a>` com padding: o Outlook ignora padding em
    link, e o botão viraria texto sublinhado no meio da mensagem."""
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:26px 0 0">
  <tr>
    <td align="center" bgcolor="{cor}" style="border-radius:8px;{_preto(cor)}">
      <a href="{url}"
         style="display:inline-block;padding:13px 26px;font-family:{_FONTE};font-size:15px;
                font-weight:600;color:{_FUNDO};text-decoration:none;border-radius:8px">{rotulo}</a>
    </td>
  </tr>
</table>
""".strip()


def _itens(titulos: list[str], cor: str) -> str:
    """A lista de pendências.

    Em tabela, com o marcador em célula própria: `<ul>` tem recuo diferente em
    cada cliente, e um item que quebra linha alinharia embaixo do marcador em
    vez de alinhar com o texto de cima.
    """
    linhas = "".join(
        f"""
  <tr>
    <td valign="top" width="18"
        style="font-family:{_FONTE};font-size:15px;line-height:1.6;color:{cor}">{_nitido("&bull;")}</td>
    <td style="font-family:{_FONTE};font-size:15px;line-height:1.6;color:{_TINTA};
               padding-bottom:6px">{_nitido(escape(titulo))}</td>
  </tr>"""
        for titulo in titulos[:6]
    )
    resto = len(titulos) - 6
    if resto > 0:
        linhas += f"""
  <tr>
    <td></td>
    <td style="font-family:{_FONTE};font-size:13px;line-height:1.6;color:{_TINTA_FRACA}">
      {_nitido(f"e mais {resto} {'item' if resto == 1 else 'itens'}")}
    </td>
  </tr>"""
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       style="margin:18px 0 0">{linhas}
</table>
""".strip()


def _placar(colunas: list[tuple[str, str, str]]) -> str:
    """Os números lado a lado: (valor, rótulo, cor).

    Número grande antes da prosa porque é o que a pessoa quer saber, e é o que
    ela lembra depois de fechar o e-mail.
    """
    largura = f"{100 // max(len(colunas), 1)}%"
    celulas = "".join(
        f"""
    <td width="{largura}" valign="top" style="padding:0 6px">
      <div style="font-family:{_FONTE};font-size:28px;font-weight:600;letter-spacing:-.02em;
                  color:{cor};line-height:1.1">{_nitido(valor)}</div>
      <div style="font-family:{_FONTE};font-size:12px;color:{_TINTA_FRACA};
                  padding-top:4px">{_nitido(rotulo)}</div>
    </td>"""
        for valor, rotulo, cor in colunas
    )
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       bgcolor="{_SUPERFICIE}"
       style="margin:22px 0 0;{_preto(_SUPERFICIE)};border:1px solid {_LINHA};
              border-radius:10px">
  <tr><td style="padding:18px 10px">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
      <tr>{celulas}
      </tr>
    </table>
  </td></tr>
</table>
""".strip()


def _rodape(mostrar_preferencias: bool, url_alternativa: str = "") -> str:
    """O pé da mensagem.

    A linha de preferências só aparece nos avisos do plano. Confirmação de
    e-mail e troca de senha não são preferência — oferecer "ajuste seus
    avisos" neles ensinaria a pessoa a desligar justamente o que ela precisa
    receber para conseguir entrar na conta.
    """
    partes = []
    if url_alternativa:
        partes.append(
            f"""
      <div style="font-family:{_FONTE};font-size:12px;line-height:1.6;color:{_TINTA_FRACA};
                  padding-bottom:14px">
        {_nitido("Se o botão não funcionar, copie este endereço no navegador:")}<br />
        <span style="color:{_TINTA_SUAVE};word-break:break-all">{_nitido(url_alternativa)}</span>
      </div>"""
        )
    if mostrar_preferencias:
        partes.append(
            f"""
      <div style="font-family:{_FONTE};font-size:12px;line-height:1.6;color:{_TINTA_FRACA};
                  padding-bottom:10px">
        {_nitido("Você escolhe quais avisos recebe em")}
        <a href="{settings.frontend_url}" style="color:{_ROXO};text-decoration:none">{_nitido("Configurações &rsaquo; Avisos e privacidade")}</a>.
      </div>"""
        )
    partes.append(
        f"""
      <div style="font-family:{_FONTE};font-size:12px;color:{_TINTA_FRACA}">
        {_nitido("PathR &middot; seu plano de estudos")}
      </div>"""
    )
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       style="margin:30px 0 0">
  <tr><td style="border-top:1px solid {_LINHA};padding-top:18px">{''.join(partes)}
  </td></tr>
</table>
""".strip()


def _pagina(preheader: str, miolo: str) -> str:
    """O invólucro: fundo, cartão centralizado, e a linha de pré-visualização.

    O `preheader` é o trecho que a caixa de entrada mostra ao lado do assunto.
    Sem ele o cliente puxa o primeiro texto visível — que aqui seria "PathR",
    repetindo o remetente e desperdiçando a única linha de contexto que a
    pessoa lê antes de decidir abrir. Os caracteres invisíveis no fim empurram
    para fora do trecho o que viria depois.
    """
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<meta name="color-scheme" content="dark" />
<meta name="supported-color-schemes" content="dark" />
<style>
  /* Só casa no HTML do Gmail (ele põe um <u> antes do corpo). Ver trava 4. */
  u + .body .gm-s {{ background:#000; mix-blend-mode:screen; }}
  u + .body .gm-d {{ background:#000; mix-blend-mode:difference; }}
</style>
</head>
<body class="body" style="margin:0;padding:0;{_preto(_FUNDO)}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;
            height:0;width:0">{escape(preheader)}{'&#847;&zwnj;&nbsp;' * 40}</div>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       bgcolor="{_FUNDO}" style="{_preto(_FUNDO)};margin:0;padding:0">
  <tr>
    <td align="center" style="padding:32px 16px">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
             bgcolor="{_PAINEL}" style="max-width:560px;{_preto(_PAINEL)};
             border:1px solid {_LINHA};border-radius:16px">
        <tr>
          <td bgcolor="{_PAINEL}"
              style="{_preto(_PAINEL)};border-radius:16px;padding:28px 28px 26px">
            {miolo}
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Conta: confirmação e senha
#
# Estes dois não têm preferência e não podem ser desligados — sem eles não se
# entra na conta. Roxo no primeiro, que é a cor da marca e o momento de
# boas-vindas; âmbar no segundo, porque âmbar é a cor de atenção no app
# inteiro e troca de senha é o e-mail que alguém precisa reconhecer como fora
# do comum se não foi ela quem pediu.
# ---------------------------------------------------------------------------


def send_verification_email(to_email: str, to_name: str, token: str) -> bool:
    url = f"{settings.frontend_url}/confirmar-email?token={quote(token, safe="")}"
    nome = _primeiro_nome(to_name)
    miolo = (
        _cabecalho(_ROXO)
        + _titulo("Boas-vindas", f"Que bom ter você aqui{', ' + nome if nome else ''}.", _ROXO)
        + _texto(
            "Falta um passo para o seu plano de estudos começar a ser montado: confirme que "
            "este e-mail é seu."
        )
        + _botao("Confirmar meu e-mail", url, _ROXO)
        + _texto(
            f'<span style="color:{_TINTA_FRACA}">O link vale por 3 dias. Depois disso é só '
            "pedir outro na tela de entrada.</span>",
            topo=20,
        )
        + _rodape(mostrar_preferencias=False, url_alternativa=url)
    )
    return _send(
        to_email,
        to_name,
        "Confirme seu e-mail e comece seu plano no PathR",
        _pagina("Um clique para confirmar seu e-mail e liberar seu plano de estudos.", miolo),
    )


def send_password_reset(to_email: str, to_name: str, token: str) -> bool:
    url = f"{settings.frontend_url}/nova-senha?token={quote(token, safe="")}"
    miolo = (
        _cabecalho(_AMBAR)
        + _titulo("Segurança", "Vamos criar uma senha nova.", _AMBAR)
        + _texto("Você pediu para redefinir a senha da sua conta no PathR.")
        + _botao("Criar senha nova", url, _AMBAR)
        + _texto(
            f'<span style="color:{_TINTA_FRACA}">O link vale por 1 hora e serve uma vez só. '
            "<b>Se não foi você que pediu</b>, ignore esta mensagem: nada muda e sua senha "
            "atual continua valendo.</span>",
            topo=20,
        )
        + _rodape(mostrar_preferencias=False, url_alternativa=url)
    )
    return _send(
        to_email,
        to_name,
        "Redefinir sua senha do PathR",
        _pagina("Link de senha nova, válido por 1 hora. Não pediu? Pode ignorar.", miolo),
    )


# ---------------------------------------------------------------------------
# Candidaturas
#
# Dois e-mails bem diferentes: um avisa a PESSOA das vagas do dia; o outro vai
# para a EMPRESA, com a carta e o currículo em anexo. Só o segundo leva
# `Reply-To` com o e-mail de quem se candidatou — a resposta da empresa tem que
# chegar nela, não no PathR.
# ---------------------------------------------------------------------------


def send_daily_jobs(to_email: str, to_name: str, vagas: list[dict[str, str]]) -> bool:
    """As vagas separadas hoje, para a pessoa decidir o que enviar."""
    if not vagas:
        return False
    nome = _primeiro_nome(to_name)
    quantas = len(vagas)
    coisa = "vaga" if quantas == 1 else "vagas"
    itens = [
        f"{v.get('titulo', '')} — {v.get('empresa', '')}".strip(" —")
        + (f" · {v['local']}" if v.get("local") else "")
        # Diz o que já saiu: quem ligou o envio automático precisa saber o que
        # foi enviado em nome dele hoje, sem ter que abrir o app para descobrir.
        + (" · currículo enviado" if v.get("enviada") else "")
        for v in vagas
    ]
    quantas_enviadas = sum(1 for v in vagas if v.get("enviada"))
    miolo = (
        _cabecalho(_VERDE)
        + _titulo("Vagas de hoje", f"{quantas} {coisa} para você{', ' + nome if nome else ''}.", _VERDE)
        + _texto(
            "Separadas pelo quanto combinam com o seu currículo e o seu objetivo. "
            "No app, cada uma já sai com uma carta de apresentação escrita para ela."
            + (
                f' Em <b style="color:{_TINTA}">{quantas_enviadas}</b> delas o seu currículo já foi enviado.'
                if quantas_enviadas
                else ""
            )
        )
        + _itens(itens, _VERDE)
        + _botao("Ver e enviar", f"{settings.frontend_url}", _VERDE)
        + _texto(
            f'<span style="color:{_TINTA_FRACA}">Você decide o que enviar: nada sai sem você '
            "confirmar.</span>",
            topo=20,
        )
        + _rodape(mostrar_preferencias=True)
    )
    return _send(
        to_email,
        to_name,
        f"{quantas} {coisa} para você hoje",
        _pagina(f"{quantas} {coisa} que combinam com o seu perfil, com carta pronta.", miolo),
    )


def send_application(
    to_email: str,
    subject: str,
    carta: str,
    candidato_nome: str,
    candidato_email: str,
    anexo_nome: str = "",
    anexo_base64: str = "",
) -> bool:
    """A candidatura em si: carta no corpo, currículo em anexo.

    Texto simples e sem marca do PathR no corpo: quem lê é um recrutador, e a
    carta é da pessoa. O rodapé diz só o nome e o e-mail dela.
    """
    paragrafos = "".join(
        f'<p style="font-family:{_FONTE};font-size:15px;line-height:1.7;color:#1a1a1a;margin:0 0 14px">'
        f"{escape(trecho)}</p>"
        for trecho in (carta or "").split("\n")
        if trecho.strip()
    )
    assinatura = (
        f'<p style="font-family:{_FONTE};font-size:15px;line-height:1.7;color:#1a1a1a;margin:22px 0 0">'
        f"{escape(candidato_nome)}<br>"
        f'<a href="mailto:{escape(candidato_email)}" style="color:#1a1a1a">{escape(candidato_email)}</a></p>'
    )
    html = (
        '<div style="background:#ffffff;padding:24px;max-width:620px">' + paragrafos + assinatura + "</div>"
    )
    anexos = (
        [{"name": anexo_nome, "content": anexo_base64}] if anexo_nome and anexo_base64 else None
    )
    return _send(
        to_email,
        "",
        subject,
        html,
        reply_to={"email": candidato_email, "name": candidato_nome or candidato_email},
        anexos=anexos,
    )


# ---------------------------------------------------------------------------
# Avisos do plano de estudo
#
# Os três saem do disparo horário (routers/jobs.py) e respeitam as preferências
# da aba "Avisos e privacidade". Cada um só é enviado quando tem o que dizer:
# um lembrete de uma lista vazia, ou um resumo de uma semana sem nada, treina a
# pessoa a ignorar o remetente.
# ---------------------------------------------------------------------------


def send_daily_plan(to_email: str, to_name: str, pendentes: list[str], minutos: int) -> bool:
    """O que falta hoje, com o tempo que isso leva."""
    quantos = len(pendentes)
    coisa = "item" if quantos == 1 else "itens"
    nome = _primeiro_nome(to_name)

    miolo = (
        _cabecalho(_ROXO)
        + _titulo("Plano de hoje", f"Bom dia{', ' + nome if nome else ''}.", _ROXO)
        + _texto(
            f'Faltam <b style="color:{_TINTA}">{quantos} {coisa}</b> na sua semana — cerca de '
            f'<b style="color:{_TINTA}">{minutos} minutos</b> no total.'
        )
        + _itens(pendentes, _ROXO)
        + _botao("Abrir meu plano", settings.frontend_url, _ROXO)
        + _texto(
            f'<span style="color:{_TINTA_FRACA}">Começar pelo primeiro já mantém sua sequência '
            "de pé.</span>",
            topo=20,
        )
        + _rodape(mostrar_preferencias=True)
    )
    return _send(
        to_email,
        to_name,
        f"Seu plano de hoje: {quantos} {coisa}, {minutos} min",
        _pagina(
            f"{quantos} {coisa} para hoje, cerca de {minutos} minutos. Comece pelo primeiro.",
            miolo,
        ),
    )


def send_weekly_summary(
    to_email: str, to_name: str, feitos: int, total: int, minutos: int, streak: int
) -> bool:
    """A semana que passou, em números que a pessoa reconhece."""
    horas = _numero(minutos / 60)
    completou = total > 0 and feitos >= total

    placar = [
        (f"{feitos}/{total}", "itens concluídos", _VERDE if completou else _ROXO_CLARO),
        (f"{horas} h", "de estudo", _ROXO_CLARO),
    ]
    if streak:
        placar.append((str(streak), "dias seguidos", _AMBAR))

    if completou:
        recado = "Semana fechada por inteiro. A próxima já está montada, um degrau acima."
    elif feitos:
        recado = (
            "A semana nova já está montada no seu nível de agora — o que ficou para trás foi "
            "reencaixado, não perdido."
        )
    else:
        recado = (
            "A semana passou sem nenhum item marcado. A nova foi remontada mais leve: dá para "
            "recomeçar sem dívida."
        )

    miolo = (
        _cabecalho(_VERDE)
        + _titulo("Resumo da semana", "Como foi a sua semana.", _VERDE)
        + _placar(placar)
        + _texto(recado, topo=20)
        + _botao("Ver a semana nova", settings.frontend_url, _VERDE)
        + _rodape(mostrar_preferencias=True)
    )
    return _send(
        to_email,
        to_name,
        f"Sua semana: {feitos} de {total} itens e {horas} h de estudo",
        _pagina(
            f"{feitos} de {total} itens concluídos e {horas} h estudadas. A semana nova já está "
            "montada.",
            miolo,
        ),
    )


def send_streak_at_risk(to_email: str, to_name: str, streak: int) -> bool:
    """O aviso da noite. Só vai para quem tem sequência viva e não estudou hoje."""
    # "1 dia seguidos" e "12 dia seguidos" são os dois jeitos de errar isto, e
    # o número vem de dado real — os dois acontecem em produção.
    dia = "dia" if streak == 1 else "dias"
    seguidos = "seguido" if streak == 1 else "seguidos"
    miolo = (
        _cabecalho(_AMBAR)
        + _titulo("Sua sequência", "Ainda dá tempo hoje.", _AMBAR)
        + _placar([(str(streak), f"{dia} {seguidos} até ontem", _AMBAR)])
        + _texto(
            f'Você ainda não marcou nada hoje. <b style="color:{_TINTA}">Quinze minutos</b> '
            "bastam para a sequência continuar de pé.",
            topo=20,
        )
        + _botao("Estudar agora", settings.frontend_url, _AMBAR)
        + _rodape(mostrar_preferencias=True)
    )
    return _send(
        to_email,
        to_name,
        f"{streak} {dia} {seguidos} — não pare hoje",
        _pagina(
            f"Sua sequência de {streak} {dia} continua se você estudar quinze minutos hoje.",
            miolo,
        ),
    )


# ---------------------------------------------------------------------------
# Moderação: o resumo da varredura diária
#
# Vai só para quem modera (settings.moderator_emails), pedido pela rotina em
# routers/varredura.py. Rosa quando há algo crítico ou alto — é o e-mail que
# precisa ser aberto primeiro —, roxo nos outros dias.
# ---------------------------------------------------------------------------

_ROSA = "#d9849f"


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def send_scan_summary(to_email: str, numeros: dict, destaques: list[str], notion_url: str | None) -> bool:
    sev = numeros["por_severidade"]
    urgente = sev["critico"] + sev["alto"] > 0
    cor = _ROSA if urgente else _ROXO

    linha_bugs = (
        f'<b style="color:{_TINTA}">{_plural(numeros["bugs"], "bug encontrado", "bugs encontrados")} hoje</b>'
        f' &mdash; {_plural(sev["critico"], "crítico", "críticos")}, {_plural(sev["alto"], "alto", "altos")}, '
        f'{_plural(sev["medio"], "médio", "médios")} e {_plural(sev["baixo"], "baixo", "baixos")}'
    )
    if numeros["vulnerabilidades"]:
        linha_bugs += f' ({_plural(numeros["vulnerabilidades"], "vulnerabilidade", "vulnerabilidades")})'

    erros_txt = _plural(numeros["erros"], "erro", "erros") + " no servidor"
    if numeros["erros"]:
        erros_txt += f' ({_plural(numeros["ocorrencias_de_erro"], "ocorrência", "ocorrências")})'

    relatos_txt = (
        f'Usuários relataram {_plural(numeros["relatos_bug"], "bug", "bugs")} no sistema e '
        f'{_plural(numeros["relatos_sugestao"], "sugestão", "sugestões")}.'
    )
    total_relatos = numeros["relatos_bug"] + numeros["relatos_sugestao"]

    miolo = (
        _cabecalho(cor)
        + _titulo("Varredura diária", "O que apareceu hoje no PathR.", cor)
        + _placar(
            [
                (str(numeros["bugs"]), "bugs", _ROSA if urgente else _ROXO_CLARO),
                (str(numeros["sugestoes"]), "sugestões", _ROXO_CLARO),
                (str(numeros["erros"]), "erros", _AMBAR if numeros["erros"] else _ROXO_CLARO),
                (str(total_relatos), "relatos", _VERDE),
            ]
        )
        + _texto(linha_bugs + ".", topo=20)
        + _texto(f'{_plural(numeros["sugestoes"], "sugestão", "sugestões")} de melhoria.', topo=6)
        + _texto(erros_txt + ".", topo=6)
        + _texto(relatos_txt, topo=6)
        + (_itens(destaques, cor) if destaques else "")
        + (_botao("Abrir no Notion", escape(notion_url), cor) if notion_url else "")
        + _rodape(mostrar_preferencias=False)
    )
    assunto = (
        f'PathR hoje: {_plural(numeros["bugs"], "bug", "bugs")} '
        f'({sev["critico"]} crít., {sev["alto"]} altos) · '
        f'{_plural(numeros["sugestoes"], "sugestão", "sugestões")} · '
        f'{_plural(numeros["erros"], "erro", "erros")} · {_plural(total_relatos, "relato", "relatos")}'
    )
    return _send(to_email, "Moderação PathR", assunto, _pagina(relatos_txt, miolo))


# ---------------------------------------------------------------------------
# Segurança: novo acesso
#
# Sai quando a conta entra de um navegador+sistema que não usava nos últimos
# 180 dias (routers/sessoes.py). Âmbar, como a troca de senha: é o e-mail que
# a pessoa precisa reconhecer como fora do comum se não foi ela. Não é
# preferência e não pode ser desligado — quem desliga isto é quem invade.
# ---------------------------------------------------------------------------

_FUSO_AVISO = ZoneInfo("America/Sao_Paulo")


def send_new_login(
    to_email: str,
    to_name: str,
    *,
    aparelho: str,
    ip: str | None,
    quando: datetime,
    metodo: str,
) -> bool:
    local = quando.astimezone(_FUSO_AVISO)
    momento = local.strftime("%d/%m/%Y às %H:%M") + " (horário de Brasília)"
    como = "com chave de acesso" if metodo == "passkey" else "com e-mail e senha"
    nome = _primeiro_nome(to_name)

    detalhes = (
        f'<b style="color:{_TINTA}">{escape(aparelho)}</b><br />'
        f"{escape(momento)}<br />"
        f"Entrada {como}"
        + (f"<br />Rede: {escape(ip)}" if ip else "")
    )
    miolo = (
        _cabecalho(_AMBAR)
        + _titulo("Segurança", f"Novo acesso à sua conta{', ' + escape(nome) if nome else ''}.", _AMBAR)
        + _texto("Sua conta do PathR acabou de ser aberta num aparelho que ela não usava:")
        + _texto(detalhes, topo=12)
        + _texto(
            "<b>Foi você?</b> Então está tudo certo, não precisa fazer nada.",
            topo=18,
        )
        + _texto(
            "<b>Não foi você?</b> Entre no PathR, abra <b>Configurações › Conta › Aparelhos conectados</b>, "
            "encerre esse aparelho e troque sua senha.",
            topo=8,
        )
        + _botao("Revisar aparelhos conectados", settings.frontend_url, _AMBAR)
        + _rodape(mostrar_preferencias=False)
    )
    return _send(
        to_email,
        to_name,
        f"Novo acesso à sua conta do PathR: {aparelho}",
        _pagina(f"{aparelho} · {momento}. Não foi você? Encerre a sessão.", miolo),
    )
