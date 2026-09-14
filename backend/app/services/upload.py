"""Ler um arquivo enviado sem deixar o tamanho a cargo de quem mandou.

`await arquivo.read()` traz o arquivo INTEIRO para a memória antes de qualquer
checagem de tamanho — um envio de centenas de megas ocupava a memória da
máquina só para ouvir "arquivo grande demais" no fim, e alguns ao mesmo tempo
derrubavam o processo. Aqui a leitura é em blocos e para no primeiro byte
além do limite.
"""

from fastapi import HTTPException, UploadFile, status

_BLOCO = 64 * 1024


async def ler_com_limite(arquivo: UploadFile, limite_bytes: int, mensagem: str) -> bytes:
    partes: list[bytes] = []
    total = 0
    while True:
        bloco = await arquivo.read(_BLOCO)
        if not bloco:
            break
        total += len(bloco)
        if total > limite_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=mensagem)
        partes.append(bloco)
    return b"".join(partes)
