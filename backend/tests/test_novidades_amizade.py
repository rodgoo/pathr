"""O pop-up de amizade e a foto de perfil no tamanho certo.

O que se segura: o convite aparece para quem recebeu e o aceite para quem
enviou, uma vez só (marcado como visto, some em todo aparelho); ninguém marca
como visto o aviso de outra pessoa; e a foto enviada vira 512 px sem os
metadados da câmera (que podem trazer a localização).
"""

import io

from PIL import Image

from app.services import imagem
from tests.test_amizade import ANA, BRUNO, CARLA, banco, como  # noqa: F401


def test_convite_vira_novidade_para_quem_recebeu_uma_vez(como):
    como(ANA).post("/social/amigos/brunolima")
    assert como(ANA).get("/social/novidades").json() == []

    novidades = como(BRUNO).get("/social/novidades").json()
    assert [(n["tipo"], n["pessoa"]["username"]) for n in novidades] == [("convite", "anasouza")]
    assert "stack" in novidades[0]["pessoa"] and novidades[0]["pessoa"]["name"] == "Ana Souza"

    visto = {"itens": [{"friendship_id": novidades[0]["friendship_id"], "tipo": "convite"}]}
    assert como(BRUNO).post("/social/novidades/vistas", json=visto).status_code == 204
    assert como(BRUNO).get("/social/novidades").json() == []
    # O convite continua lá para aceitar: visto não é respondido.
    assert len(como(BRUNO).get("/social/amigos").json()["recebidos"]) == 1


def test_aceite_vira_novidade_para_quem_enviou(como):
    como(ANA).post("/social/amigos/brunolima")
    convite = como(BRUNO).get("/social/novidades").json()[0]["friendship_id"]
    como(BRUNO).post(f"/social/convites/{convite}/aceitar")

    assert como(BRUNO).get("/social/novidades").json() == []
    novidades = como(ANA).get("/social/novidades").json()
    assert [(n["tipo"], n["pessoa"]["username"]) for n in novidades] == [("aceito", "brunolima")]


def test_so_a_ponta_certa_marca_como_visto(como):
    como(ANA).post("/social/amigos/brunolima")
    convite = como(BRUNO).get("/social/novidades").json()[0]["friendship_id"]
    # Quem enviou e uma terceira pessoa tentam esconder o aviso de Bruno.
    for quem in (ANA, CARLA):
        como(quem).post("/social/novidades/vistas", json={"itens": [{"friendship_id": convite, "tipo": "convite"}]})
    assert len(como(BRUNO).get("/social/novidades").json()) == 1


def test_foto_reduzida_a_512_e_sem_exif():
    original = Image.new("RGB", (3000, 2000), (120, 80, 200))
    exif = Image.Exif()
    exif[0x010F] = "Fabricante da camera"  # Make
    bruto = io.BytesIO()
    original.save(bruto, "JPEG", exif=exif.tobytes())
    reduzida = imagem.reduzir(bruto.getvalue(), "image/jpeg")

    with Image.open(io.BytesIO(reduzida)) as resultado:
        assert max(resultado.size) == 512 and resultado.format == "JPEG"
        assert not resultado.getexif()
    assert len(reduzida) < len(bruto.getvalue())
    # Algo que não é imagem volta como veio, em vez de perder o envio.
    assert imagem.reduzir(b"nao e imagem", "image/png") == b"nao e imagem"
