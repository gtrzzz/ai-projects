import re

from panel.ajustes import AJUSTES_POR_DEFECTO
from panel.proyecto import (Momento, Opciones, Proyecto, cargar, carpeta, guardar, huella, id_para, listar,
                            necesita_render)


def proyecto_ejemplo(pid="partida-abc123") -> Proyecto:
    return Proyecto(
        id=pid, nombre="partida.mp4", clave="partida.mp4|100", fuente="fuente.mp4", preparado=None,
        duracion=600.0, ancho=1920, alto=1080, fps=60.0, hdr=False, tiene_audio=True, estado="listo",
        progreso=1.0, error=None, opciones=Opciones.desde_ajustes(AJUSTES_POR_DEFECTO),
        momentos=[momento_ejemplo()], creado="2026-11-19T10:00:00",
    )


def momento_ejemplo(**cambios) -> Momento:
    datos = dict(id="m1", inicio=10.0, fin=35.0, titulo="Hola", zoom="auto", zoom_en=None, zoom_auto=5.3,
                 estado="propuesto", editado=False, salida=None, huella=None,
                 subido={"tiktok": False, "reels": False, "shorts": False}, puntuacion=0.8, motivos={})
    datos.update(cambios)
    return Momento(**datos)


def test_id_seguro():
    i = id_para("Grand Theft Auto VI_20261118 ñandú 🐊.mp4", "x|1")
    assert re.fullmatch(r"[a-z0-9-]{1,40}-[0-9a-f]{6}", i)
    assert i.startswith("grand-theft-auto-vi")


def test_id_distinto_por_clave():
    assert id_para("a.mp4", "a.mp4|1") != id_para("a.mp4", "a.mp4|2")


def test_guardar_y_cargar(tmp_path):
    p = proyecto_ejemplo()
    guardar(tmp_path, p)
    q = cargar(tmp_path, p.id)
    assert q == p
    assert [x.id for x in listar(tmp_path)] == [p.id]


def test_guardado_atomico(tmp_path):
    p = proyecto_ejemplo()
    guardar(tmp_path, p)
    guardar(tmp_path, p)
    assert sorted(f.name for f in carpeta(tmp_path, p.id).iterdir()) == ["proyecto.json"]


def test_huella_cambia_con_titulo():
    p = proyecto_ejemplo()
    base = huella(p, momento_ejemplo(), "Sígueme")
    assert huella(p, momento_ejemplo(titulo="Otro"), "Sígueme") != base
    assert huella(p, momento_ejemplo(estado="aprobado", subido={"tiktok": True}), "Sígueme") == base
    assert huella(p, momento_ejemplo(), "Otro CTA") != base


def test_necesita_render():
    p = proyecto_ejemplo()
    assert necesita_render(p, momento_ejemplo(estado="aprobado"), None)
    hecho = momento_ejemplo(estado="renderizado", salida="x.mp4")
    hecho.huella = huella(p, hecho, None)
    assert not necesita_render(p, hecho, None)
    hecho.titulo = "Cambiado"
    assert necesita_render(p, hecho, None)
    assert not necesita_render(p, momento_ejemplo(estado="descartado"), None)
    assert not necesita_render(p, momento_ejemplo(estado="propuesto"), None)
