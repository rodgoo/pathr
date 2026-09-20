# Segurança

## Achou uma falha? Escreva antes de publicar

**privacidade@notter.com.br**

Escreva em vez de abrir uma issue. Issue é pública desde o primeiro segundo, e
entre a publicação e a correção existe uma janela em que qualquer pessoa pode
usar o que você descreveu contra quem está usando o app — inclusive gente que
confiou o próprio currículo a ele.

Não existe programa de recompensa. O que existe é resposta: retorno em até 72
horas, e aviso quando a correção subir. Se quiser crédito pelo achado, diga
como prefere ser citado.

### O que ajuda no relato

- o que dá para fazer com a falha, em uma frase;
- os passos para reproduzir (ou um `curl`, um trecho de código, um vídeo);
- em que ambiente você viu — `pathr.notter.com.br` ou uma instalação sua.

Não precisa de exploração elaborada. Um relato claro de algo pequeno vale mais
que um relatório longo sobre algo teórico.

### Por favor, não

- não teste a instalação de produção com carga (isso é indisponibilidade, não
  pesquisa) — suba a sua cópia, o [README](README.md) explica como;
- não acesse, baixe nem modifique dado de outra pessoa. Se uma falha der acesso
  a dado alheio, pare no momento em que isso ficar provado e conte;
- não use engenharia social com quem opera o app.

## O que consideramos falha

Vale relatar: entrar na conta de outra pessoa, ler dado de outra pessoa,
executar código no servidor, escapar da sandbox do Laboratório de código, fazer
o servidor pedir endereços internos (SSRF), injeção de SQL ou de filtro,
contornar os limites de uso e de cadastro, e XSS em qualquer tela.

Provavelmente não vale: falta de um cabeçalho que não muda o que dá para fazer,
versão de biblioteca sem exploração demonstrada, relatório cru de varredor
automático, e "falta rate limit" em endpoint que já tem teto (veja
`backend/app/services/limites.py` antes).

## Como o app trata dado sensível

Isto é público de propósito: quem for auditar precisa saber onde olhar.

- **Currículo, respostas de formulário e cartas** ficam cifrados no banco
  (`backend/app/services/cifra.py`), com chave que não mora no código.
- **Sessão** vive em cookie `HttpOnly` `SameSite=Strict`, nunca em
  `localStorage` — JavaScript nenhum a alcança.
- **Senha** é hash; **segundo fator** é cifrado em repouso.
- **O frontend nunca fala com o banco**: tudo passa pela API, o que permite
  manter o RLS negando por padrão.
- **Requisição de saída** com endereço vindo de busca de terceiros passa por
  `backend/app/services/saida.py`: resolve o nome uma vez, recusa faixa
  interna, conecta no IP validado e revalida cada redirecionamento.
- **Segredo não entra no repositório**: `backend/scripts/check_secrets.py`
  confere o que vai ser versionado, e o `gitleaks` (config em
  `.gitleaks.toml`) varre o histórico inteiro.

## Se você opera uma cópia

Três coisas que, esquecidas, deixam a instalação aberta:

1. `JWT_SECRET_KEY`, `MFA_ENCRYPTION_KEY` e `DATA_ENCRYPTION_KEY` precisam ser
   longas e sorteadas. O app **recusa subir** em produção sem elas — de
   propósito: com `JWT_SECRET_KEY` vazia, qualquer pessoa forjaria o cookie de
   qualquer conta.
2. `SUPER_ADMIN_EMAILS` e `MODERATOR_EMAILS` começam vazios. Declare os seus,
   ou ninguém administra a sua instalação.
3. Os buckets do Storage (currículos, avatares, fotos de relato) precisam ser
   **privados**. Nada ali deve ser servido direto pelo Supabase.
