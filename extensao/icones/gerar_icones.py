"""Gera os ícones da PathR Extension a partir do ícone do app.

Rode à mão quando o ícone do app mudar:

    python extensao/icones/gerar_icones.py

O glifo é o MESMO de hoje — `frontend/public/icons/icon-512.png` entra aqui como
máscara de luminância, e não como desenho novo. Redesenhar o `{P}` daria um
segundo `{P}`, parecido e diferente, e é assim que uma marca começa a ter duas
versões que ninguém sabe qual é a certa.

O que muda é só o que está atrás e em volta: fundo em degradê violeta→quase
preto, um brilho do glifo, um anel e quatro cantoneiras. Em 16px nada disso
aparece direito, então o anel e as cantoneiras ficam finos e o glifo grande: o
que precisa ser reconhecível na barra do navegador é o `{P}`.
"""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

AQUI = Path(__file__).resolve().parent
GLIFO = AQUI.parents[1] / "frontend" / "public" / "icons" / "icon-512.png"

# Desenha-se grande e reduz-se no fim: é o antisserrilhado de pobre, e o único
# que funciona igual em todo lugar sem depender de renderizador de SVG.
LADO = 1024
TAMANHOS = (128, 48, 32, 16)

ACENTO = (145, 132, 217)  # ACC, o mesmo violeta do app
BRILHO = (181, 171, 252)  # ACC4
CENTRO = (26, 21, 51)
BORDA = (5, 5, 10)


def _fundo() -> Image.Image:
    """Degradê radial: claro no meio, quase preto na borda."""
    fundo = Image.new("RGB", (LADO, LADO), BORDA)
    pixels = fundo.load()
    meio = LADO / 2
    for y in range(LADO):
        for x in range(LADO):
            # Distância normalizada até o centro, cortada em 1.
            d = min(1.0, (((x - meio) ** 2 + (y - meio) ** 2) ** 0.5) / meio)
            t = d * d  # quadrática: o miolo fica mais tempo claro
            pixels[x, y] = tuple(
                int(CENTRO[i] + (BORDA[i] - CENTRO[i]) * t) for i in range(3)
            )
    return fundo


def _grade(base: Image.Image) -> None:
    """Linhas finas de grade, bem apagadas — a textura de painel."""
    camada = Image.new("RGB", base.size, (0, 0, 0))
    caneta = ImageDraw.Draw(camada)
    passo = LADO // 16
    for i in range(1, 16):
        caneta.line([(i * passo, 0), (i * passo, LADO)], fill=(30, 26, 58), width=2)
        caneta.line([(0, i * passo), (LADO, i * passo)], fill=(30, 26, 58), width=2)
    base.paste(ImageChops.add(base, camada), (0, 0))


def _moldura(base: Image.Image) -> None:
    """O anel e as quatro cantoneiras."""
    caneta = ImageDraw.Draw(base, "RGBA")
    margem = int(LADO * 0.085)
    caixa = (margem, margem, LADO - margem, LADO - margem)
    caneta.rounded_rectangle(caixa, radius=int(LADO * 0.16), outline=(*ACENTO, 120), width=5)

    # Cantoneiras: dois traços por canto, saindo de dentro do anel. É o que dá
    # o ar de visor — e some sozinho nos tamanhos pequenos, sem virar sujeira.
    braco = int(LADO * 0.10)
    folga = int(LADO * 0.055)
    a, b = folga, LADO - folga
    for x, dx in ((a, 1), (b, -1)):
        for y, dy in ((a, 1), (b, -1)):
            caneta.line([(x, y), (x + braco * dx, y)], fill=(*BRILHO, 220), width=9)
            caneta.line([(x, y), (x, y + braco * dy)], fill=(*BRILHO, 220), width=9)


def _mascara_do_glifo() -> Image.Image:
    """O `{P}` do ícone de hoje, em preto e branco, sem o fundo preto dele."""
    original = Image.open(GLIFO).convert("RGBA")
    luz = original.convert("L")

    # Fora do quadrado arredondado o PNG do app é BRANCO OPACO, não transparente
    # — e branco, numa máscara de luminância, é tinta. Sem este recorte o ícone
    # ganha quatro cunhas brancas nas quinas. O raio é o do desenho original
    # (80 de 440), na medida deste arquivo.
    recorte = Image.new("L", original.size, 0)
    ImageDraw.Draw(recorte).rounded_rectangle(
        (0, 0, original.width - 1, original.height - 1),
        radius=int(original.width * 80 / 440),
        fill=255,
    )
    luz = ImageChops.multiply(luz, recorte)

    lado = int(LADO * 0.58)
    return luz.resize((lado, lado), Image.LANCZOS)


def _monta() -> Image.Image:
    base = _fundo()
    _grade(base)
    _moldura(base)

    mascara = _mascara_do_glifo()
    canto = ((LADO - mascara.width) // 2, (LADO - mascara.height) // 2)

    # O brilho primeiro (máscara borrada, na cor do acento), o glifo por cima.
    halo = Image.new("L", (LADO, LADO), 0)
    halo.paste(mascara, canto)
    halo = halo.filter(ImageFilter.GaussianBlur(LADO * 0.022))
    base.paste(Image.new("RGB", (LADO, LADO), BRILHO), (0, 0), halo)
    # A tinta do glifo tem o tamanho da máscara: com um canto de 2 valores, o
    # Pillow exige que colagem e máscara tenham a mesma medida.
    base.paste(Image.new("RGB", mascara.size, (255, 255, 255)), canto, mascara)

    # Canto arredondado do ícone inteiro.
    recorte = Image.new("L", (LADO, LADO), 0)
    ImageDraw.Draw(recorte).rounded_rectangle(
        (0, 0, LADO - 1, LADO - 1), radius=int(LADO * 0.22), fill=255
    )
    icone = base.convert("RGBA")
    icone.putalpha(recorte)
    return icone


def main() -> None:
    icone = _monta()
    for tamanho in TAMANHOS:
        destino = AQUI / f"icone-{tamanho}.png"
        icone.resize((tamanho, tamanho), Image.LANCZOS).save(destino)
        print(f"gravado {destino.name}")
    icone.save(AQUI / "icone-512.png")
    print("gravado icone-512.png")


if __name__ == "__main__":
    main()
