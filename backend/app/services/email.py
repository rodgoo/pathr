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
from html import escape
from urllib.parse import quote

import httpx

from app.config import settings

logger = logging.getLogger("pathr.email")

_BREVO_URL = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT = 10

# ---------------------------------------------------------------------------
# Paleta
#
# Repetida do frontend (src/lib/tokens.ts) de propósito: e-mail não importa CSS
# do app, e atravessar os dois projetos por cinco cores custaria mais que a
# duplicação. Os nomes são os mesmos dos tokens de lá, para quem mudar a marca
# achar os dois lugares.
# ---------------------------------------------------------------------------
_FUNDO = "#161826"  # BG
_PAINEL = "#1b1d2b"  # PANEL
_TINTA = "#e9e9ed"
_TINTA_SUAVE = "#b9b9c4"
_TINTA_FRACA = "#84848f"
_LINHA = "#2a2d3f"

_ROXO = "#9184d9"  # ACC
_ROXO_CLARO = "#b5abfc"  # ACC4
_VERDE = "#63b48f"
_AMBAR = "#cfa25e"

# Pilha de fontes do sistema. Webfont em e-mail não carrega de forma confiável,
# e a falha aparece como serifada gigante — pior que não ter fonte própria.
_FONTE = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def _send(to_email: str, to_name: str, subject: str, html: str) -> bool:
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
            },
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        logger.error("Falha de rede ao enviar e-mail para %s: %s", to_email, exc)
        return False
    if response.status_code >= 400:
        logger.error("Brevo recusou o e-mail para %s: HTTP %s", to_email, response.status_code)
        return False
    return True


# ---------------------------------------------------------------------------
# Peças do desenho
# ---------------------------------------------------------------------------


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
            <img src="{logo}" width="40" height="40" alt=""
                 style="display:block;width:40px;height:40px;border:0;border-radius:10px" />
          </td>
          <td valign="middle">
            <span style="font-family:{_FONTE};font-size:19px;font-weight:600;
                         letter-spacing:-.01em;color:{_TINTA}">PathR</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td height="3" bgcolor="{cor}"
        style="font-size:0;line-height:0;height:3px;background-color:{cor};
               border-radius:2px">&nbsp;</td>
  </tr>
</table>
""".strip()


def _titulo(rotulo: str, titulo: str, cor: str) -> str:
    return f"""
<div style="font-family:{_FONTE};font-size:11px;font-weight:600;letter-spacing:.14em;
            text-transform:uppercase;color:{cor};padding:26px 0 0">{rotulo}</div>
<h1 style="font-family:{_FONTE};font-size:26px;line-height:1.25;font-weight:600;
           letter-spacing:-.02em;color:{_TINTA};margin:10px 0 0">{titulo}</h1>
""".strip()


def _texto(corpo: str, topo: int = 14) -> str:
    return (
        f'<p style="font-family:{_FONTE};font-size:15px;line-height:1.65;color:{_TINTA_SUAVE};'
        f'margin:{topo}px 0 0">{corpo}</p>'
    )


def _botao(rotulo: str, url: str, cor: str) -> str:
    """Botão em tabela, e não `<a>` com padding: o Outlook ignora padding em
    link, e o botão viraria texto sublinhado no meio da mensagem."""
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:26px 0 0">
  <tr>
    <td align="center" bgcolor="{cor}" style="border-radius:8px">
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
        style="font-family:{_FONTE};font-size:15px;line-height:1.6;color:{cor}">&bull;</td>
    <td style="font-family:{_FONTE};font-size:15px;line-height:1.6;color:{_TINTA};
               padding-bottom:6px">{escape(titulo)}</td>
  </tr>"""
        for titulo in titulos[:6]
    )
    resto = len(titulos) - 6
    if resto > 0:
        linhas += f"""
  <tr>
    <td></td>
    <td style="font-family:{_FONTE};font-size:13px;line-height:1.6;color:{_TINTA_FRACA}">
      e mais {resto} {'item' if resto == 1 else 'itens'}
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
                  color:{cor};line-height:1.1">{valor}</div>
      <div style="font-family:{_FONTE};font-size:12px;color:{_TINTA_FRACA};
                  padding-top:4px">{rotulo}</div>
    </td>"""
        for valor, rotulo, cor in colunas
    )
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       bgcolor="{_FUNDO}" style="margin:22px 0 0;background-color:{_FUNDO};border-radius:10px">
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
        Se o botão não funcionar, copie este endereço no navegador:<br />
        <span style="color:{_TINTA_SUAVE};word-break:break-all">{url_alternativa}</span>
      </div>"""
        )
    if mostrar_preferencias:
        partes.append(
            f"""
      <div style="font-family:{_FONTE};font-size:12px;line-height:1.6;color:{_TINTA_FRACA};
                  padding-bottom:10px">
        Você escolhe quais avisos recebe em
        <a href="{settings.frontend_url}" style="color:{_ROXO};text-decoration:none">Configurações
        &rsaquo; Avisos e privacidade</a>.
      </div>"""
        )
    partes.append(
        f"""
      <div style="font-family:{_FONTE};font-size:12px;color:{_TINTA_FRACA}">
        PathR &middot; seu plano de estudos
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
</head>
<body style="margin:0;padding:0;background-color:{_FUNDO}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;
            height:0;width:0">{escape(preheader)}{'&#847;&zwnj;&nbsp;' * 40}</div>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       bgcolor="{_FUNDO}" style="background-color:{_FUNDO};margin:0;padding:0">
  <tr>
    <td align="center" style="padding:32px 16px">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
             bgcolor="{_PAINEL}" style="max-width:560px;background-color:{_PAINEL};
             border-radius:16px">
        <tr>
          <td bgcolor="{_PAINEL}"
              style="background-color:{_PAINEL};border-radius:16px;padding:28px 28px 26px">
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
