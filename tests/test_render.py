from pathlib import Path

import pytest

import clipper
from panel import render
from panel.ajustes import AJUSTES_POR_DEFECTO
from panel.proyecto import Momento, cargar, carpeta, guardar
from tests.test_trabajos import nuevo_proyecto

URL = "http://127.0.0.1:8765"


def con_momentos(tmp_path, *momentos):
    p = nuevo_proyecto(tmp_path, estado="listo")
    p.preparado = "fuente.mp4"
    p.momentos = list(momentos)
    guardar(tmp_path, p)
    return p


@pytest.mark.parametrize("zoom,esperado", [("auto", 4.2), ("no", None), ("fijo", 7.0)])
def test_trabajo_zoom_segun_eleccion(tmp_path, zoom, esperado):
    m = Momento(id="m", inicio=10, fin=30, titulo="T", zoom=zoom, zoom_en=7.0, zoom_auto=4.2)
    p = con_momentos(tmp_path, m)
    assert render.trabajo_de(p, m, [], URL).zoom_en == esperado


def test_trabajo_props(tmp_path):
    m = Momento(id="m", inicio=10, fin=30, titulo="T")
    p = con_momentos(tmp_path, m)
    t = render.trabajo_de(p, m, [(9.0, 9.5, "antes"), (12.0, 12.5, "hola")], URL)
    props = clipper.props_remotion(t, None)
    assert props["video"] == f"{URL}/media/p1/fuente.mp4"
    assert props["inicio"] == 10 and props["fin"] == 30 and props["modo"] == "zoom"
    assert props["palabras"] == [{"i": 2.0, "f": 2.5, "t": "hola"}]


def test_encuesta_solo_en_decide(tmp_path):
    m = Momento(id="m", inicio=0, fin=20, titulo="T")
    p = con_momentos(tmp_path, m)
    p.opciones.opcion_a, p.opciones.opcion_b = "Robar", "Huir"
    assert render.trabajo_de(p, m, [], URL).encuesta is None
    p.opciones.tipo = "decide"
    assert render.trabajo_de(p, m, [], URL).encuesta == ("Robar", "Huir")


@pytest.fixture
def render_falso(monkeypatch):
    lotes = []

    def falso(lista, al_progresar=None):
        lotes.append(lista)
        for props, salida in lista:
            assert (clipper.REMOTION / "public" / props["video"]).exists()
            Path(salida).write_bytes(b"mp4")

    def cortar(entrada, destino, inicio, fin):
        Path(destino).write_bytes(b"tramo")
        return round(fin - inicio, 3)

    monkeypatch.setattr(clipper, "render_remotion", falso)
    monkeypatch.setattr(clipper, "cortar_tramo", cortar)
    return lotes


def test_renderiza_solo_lo_necesario(tmp_path, render_falso):
    nuevo = Momento(id="a", inicio=0, fin=20, titulo="A", estado="aprobado")
    hecho = Momento(id="b", inicio=100, fin=120, titulo="B", estado="aprobado")
    p = con_momentos(tmp_path, nuevo, hecho)
    render.renderizar(tmp_path, p.id, AJUSTES_POR_DEFECTO, URL)
    render.renderizar(tmp_path, p.id, AJUSTES_POR_DEFECTO, URL)
    assert [len(l) for l in render_falso] == [2]
    q = cargar(tmp_path, p.id)
    q.momentos[0].titulo = "Cambiado"
    guardar(tmp_path, q)
    render.renderizar(tmp_path, p.id, AJUSTES_POR_DEFECTO, URL)
    assert [len(l) for l in render_falso] == [2, 1]


def test_tras_render_estado_y_archivos(tmp_path, render_falso):
    p = con_momentos(tmp_path, Momento(id="a", inicio=0, fin=20, titulo="A", estado="aprobado"),
                     Momento(id="d", inicio=50, fin=70, titulo="D", estado="descartado"))
    render.renderizar(tmp_path, p.id, AJUSTES_POR_DEFECTO, URL)
    q = cargar(tmp_path, p.id)
    a, d = q.momentos
    assert a.estado == "renderizado" and a.huella and q.estado == "listo"
    assert d.estado == "descartado" and d.salida is None
    salida = Path(a.salida)
    assert salida == tmp_path / "salida" / p.id / f"{p.id}_momento01.mp4"
    assert salida.with_name(salida.stem + "_publicar.txt").exists()


def test_fallo_de_render(tmp_path, monkeypatch):
    def roto(lista, al_progresar=None):
        raise SystemExit("Remotion falló")

    monkeypatch.setattr(clipper, "render_remotion", roto)
    monkeypatch.setattr(clipper, "cortar_tramo", lambda e, d, i, f: (Path(d).write_bytes(b"x"), f - i)[1])
    p = con_momentos(tmp_path, Momento(id="a", inicio=0, fin=20, titulo="A", estado="aprobado"))
    render.renderizar(tmp_path, p.id, AJUSTES_POR_DEFECTO, URL)
    q = cargar(tmp_path, p.id)
    assert q.estado == "listo" and "Remotion" in q.error and q.momentos[0].estado == "aprobado"


def test_render_usa_solo_el_tramo(tmp_path, render_falso):
    p = con_momentos(tmp_path, Momento(id="a", inicio=100, fin=120, titulo="A", estado="aprobado"))
    render.renderizar(tmp_path, p.id, AJUSTES_POR_DEFECTO, URL)
    ((props, _),) = render_falso[0]
    assert props["video"].startswith("_tmp/") and props["inicio"] == 0 and props["fin"] == 20
    assert not (clipper.REMOTION / "public" / props["video"]).exists()  # se borra al terminar
