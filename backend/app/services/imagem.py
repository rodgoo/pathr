"""A foto de perfil no tamanho em que ela aparece.

A foto chegava do jeito que saiu da câmera: 2 MB, 4000 px de lado. Ela é
mostrada no máximo a 240 px (o card de conquista), e cada tela a pedia inteira
— baixada do armazenamento e decifrada a cada vez. É isso que a fazia demorar
a aparecer, para a própria pessoa e para os amigos.

Agora ela é reduzida no envio para 512 px no lado maior (nítida em tela de
alta densidade até 256 px) e reencodada. Dois ganhos de brinde:

- **Sem EXIF**: foto de celular carrega a localização GPS de onde foi tirada,
  o modelo do aparelho e a data. Nada disso precisa ir para o perfil.
- **Orientação aplicada**: a rotação que o EXIF indicava vira os pixels, e a
  foto não aparece deitada depois que o EXIF sai.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps

LADO_MAXIMO = 512

_FORMATO = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def reduzir(dados: bytes, tipo: str) -> bytes:
    """A imagem com no máximo 512 px no lado maior, sem metadados, no mesmo
    formato. Se algo falhar ao ler, devolve os bytes como vieram: a
    conferência de tipo já aconteceu antes, e perder a foto seria pior."""
    formato = _FORMATO.get(tipo)
    if not formato:
        return dados
    try:
        with Image.open(io.BytesIO(dados)) as original:
            imagem = ImageOps.exif_transpose(original)
            imagem.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.Resampling.LANCZOS)
            if formato == "JPEG" and imagem.mode not in ("RGB", "L"):
                imagem = imagem.convert("RGB")
            saida = io.BytesIO()
            opcoes = {"JPEG": {"quality": 86, "optimize": True, "progressive": True},
                      "PNG": {"optimize": True},
                      "WEBP": {"quality": 86, "method": 5}}[formato]
            # Sem `exif=`: o arquivo novo sai sem os metadados do original.
            imagem.save(saida, formato, **opcoes)
            return saida.getvalue()
    except Exception:  # noqa: BLE001
        return dados
