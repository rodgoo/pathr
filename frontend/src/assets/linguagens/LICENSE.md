# Logos das linguagens

Os SVGs desta pasta vêm do [Devicon](https://github.com/devicons/devicon),
versão 2.17.0, sob licença MIT:

> The MIT License (MIT)
>
> Copyright (c) 2015 konpa
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in
> all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

## Por que copiados, e não o pacote

São 15 ícones de um conjunto fixo. O pacote `devicon` inteiro teria dezenas de
megabytes em `node_modules` para isso, e importar arquivo de dentro dele
depende de um caminho interno que muda entre versões.

## O que foi alterado

- `go.svg` é o `go-original-wordmark` e não o `go-original`: o original é o
  gopher desenhado, que a 18px vira uma mancha.
- `rust.svg` ganhou `fill="#e9e9ed"`. O original não declara cor e sai preto,
  invisível no fundo escuro do PathR.
- `bash.svg` teve o cinza-escuro `#293138` trocado por `#c9ccd6`. O original é
  o contorno de um terminal escuro, feito para fundo claro: no PathR sumia,
  sobrando só o cursor verde.
- SQL não tem ícone aqui: o Devicon só tem os de bancos específicos (MySQL,
  PostgreSQL…), e usar um deles para "SQL" diria uma coisa que não é. A tela
  usa o ícone genérico de banco de dados do próprio app.
