# PathR Extension

Preenche formulário de vaga com o que o PathR já sabe de você. Você confere e envia.

## Instalar (Chrome ou Edge)

1. abra `chrome://extensions` (ou `edge://extensions`);
2. ligue o **Modo do desenvolvedor**;
3. **Carregar sem compactação** e escolha esta pasta (`extensao/`).

O ícone aparece na barra. Fixe-o para não ter de procurar.

## Conectar

No PathR, em **Candidaturas**, crie uma chave da extensão. Ela aparece **uma
vez** — copie e cole na janelinha da extensão. Perdeu, crie outra e revogue a
antiga.

A chave não é sua sessão: com ela só dá para ler o banco de respostas, baixar o
currículo e devolver resposta nova. Revogar no app desliga na hora.

## Usar

Na página da vaga, clique no ícone → **Preencher esta página**. O painel mostra:

- **Preenchi** — cada campo e de onde veio o valor (do seu perfil, ou de algo
  que você já respondeu antes);
- **Não consegui preencher** — campo fora do comum, para preencher à mão;
- **Preciso da sua resposta** — o que o app não responde sozinho. O que você
  escrever ali vai para o banco e serve para as próximas vagas, **em qualquer
  site** — é assim que ela melhora.

O botão de enviar do site continua sendo do site.

## O que ela não faz

- **não aperta enviar** — conferir antes de mandar currículo para uma empresa é
  seu;
- **não entra em conta nenhuma** nem navega sozinha por site de emprego: ela só
  roda na aba que você abriu, quando você clica;
- **não marca caixa de aceite** (termos, consentimento de dados): concordar é
  ato seu, não do programa;
- **não responde pergunta sensível** (gênero, raça, deficiência, idade): é
  opcional por lei e a resposta é sua;
- **não responde pergunta aberta sobre a vaga** ("por que você quer trabalhar
  aqui?"): reaproveitar a resposta de outra empresa, o recrutador percebe.

## Até onde vai o "funciona em todos os sites"

Ela não depende de receita por site: lê o rótulo que **você** lê e o casa com a
pergunta canônica, como o servidor faz. Por isso funciona em site que ninguém
testou, entra em `<iframe>` (Greenhouse, Lever, Workday embutidos) e em campo
escondido dentro de shadow DOM.

Mas "100% em todos os sites" não existe, e é melhor saber onde ela falha:

- campo sem rótulo nenhum (`name="f_12"`, sem `aria-label`, sem texto ao lado):
  não há o que reconhecer — cai em "preciso da sua resposta";
- combobox desenhado do zero (uma lista de `<div>` que finge ser `<select>`):
  cada um reage a um gesto diferente; alguns aceitam, outros não;
- formulário dentro de `<canvas>` ou de iframe de outra origem sem permissão:
  invisível para qualquer extensão;
- upload que exige passar por um provedor (Google Drive, OneDrive): o anexo é
  seu, à mão.

Nesses casos ela diz o que não deu, em vez de preencher errado e fingir sucesso.

## Desenvolver

- `src/campos.js` — reconhecer e preencher campo. É o coração; as chaves
  canônicas são as mesmas de `backend/app/services/perguntas.py`, e mudar lá
  pede mudar aqui.
- `src/conteudo.js` — o painel e a ordem das coisas. Roda em todos os quadros;
  painel só no de cima.
- `src/fundo.js` — guarda a chave e é o único que fala com a API.
- `src/popup.*` — a janelinha do ícone.
- `icones/gerar_icones.py` — regera os ícones a partir do ícone do app.
