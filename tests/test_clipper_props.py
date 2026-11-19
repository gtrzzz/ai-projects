import re
from pathlib import Path

import clipper
from clipper import Trabajo, escribir_publicacion, props_remotion, textos_publicacion

RAIZ = Path(__file__).resolve().parent.parent


def claves_clipprops() -> set[str]:
    ts = (RAIZ / "remotion/src/tipos.ts").read_text(encoding="utf-8")
    bloque = ts[ts.index("export type ClipProps = {"):]
    bloque = bloque[: bloque.index("\n};")]
    return set(re.findall(r"^\s+(\w+):", bloque, re.M))


def trabajo(**cambios) -> Trabajo:
    datos = dict(base=Path("x.mp4"), salida=Path("salida/clip.mp4"), duracion=10.0, titulo="Hola", tipo="momento",
                 fuente=Path("remotion/public/_tmp/prueba.mp4"), inicio=5.0, fin=15.0, modo="zoom", fps=59.94,
                 fuente_ancho=1920, fuente_alto=1080)
    datos.update(cambios)
    return Trabajo(**datos)


def test_props_tienen_todas_las_claves():
    props = props_remotion(trabajo(), "Sígueme")
    assert set(props) == claves_clipprops()
    assert props["inicio"] == 5.0 and props["fin"] == 15.0 and props["duracion"] == 10.0
    assert props["fps"] == 59.94 and props["modo"] == "zoom"


def test_props_url():
    url = "http://127.0.0.1:8765/media/p/preparado.mp4"
    assert props_remotion(trabajo(video_url=url), None)["video"] == url
    assert props_remotion(trabajo(), None)["video"] == "_tmp/prueba.mp4"


def test_textos_publicacion_por_plataforma():
    t = trabajo(duracion=200.0, titulo="Esto es GTA 6 😳", palabras=[(0, 0.5, "madre"), (0.5, 1, "mía")])
    textos = textos_publicacion(t)
    assert set(textos) == {"tiktok", "reels", "shorts", "transcripcion", "aviso"}
    assert textos["tiktok"].startswith("Esto es GTA 6 😳 ")
    assert "#Shorts" in textos["shorts"]
    assert textos["aviso"]  # dura más de 3 min


def test_txt_igual_que_antes(tmp_path):
    t = Trabajo(base=Path("x.mp4"), salida=tmp_path / "clip.mp4", duracion=200.0, titulo="Esto es GTA 6 😳",
                tipo="momento", palabras=[(0, 0.5, "madre"), (0.5, 1, "mía")], origen="partida.mp4 1:00-4:20")
    escribir_publicacion(t)
    esperado = (RAIZ / "tests/datos/publicar_esperado.txt").read_text(encoding="utf-8")
    assert (tmp_path / "clip_publicar.txt").read_text(encoding="utf-8") == esperado
