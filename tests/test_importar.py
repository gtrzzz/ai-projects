import io
import json

import pytest

import clipper
from panel import importar as imp
from panel.ajustes import AJUSTES_POR_DEFECTO
from panel.proyecto import cargar, carpeta, guardar, listar


@pytest.fixture(autouse=True)
def sin_ffprobe(monkeypatch):
    monkeypatch.setattr(clipper, "analizar_archivo",
                        lambda ruta: clipper.InfoVideo(duracion=600.0, ancho=1920, alto=1080, hdr=False,
                                                       tiene_audio=True, fps=60.0))


def video(ruta, contenido=b"0123456789"):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)
    return ruta


def test_busca_en_ps5_create(tmp_path):
    usb = tmp_path / "D"
    a = video(usb / "PS5/CREATE/Video Clips/Grand Theft Auto VI/a.mp4")
    video(usb / "PS5/CREATE/Screenshots/Grand Theft Auto VI/foto.jpg")
    video(usb / "otra/b.mp4")
    assert imp.buscar_ps5([usb]) == [a]


def test_buscar_entrada(tmp_path):
    a = video(tmp_path / "entrada/clip.MP4")
    video(tmp_path / "entrada/notas.txt")
    assert imp.buscar_entrada(tmp_path / "entrada") == [a]


def test_importar_copia_y_crea_proyecto(tmp_path):
    raiz = tmp_path / "app"
    origen = video(tmp_path / "usb/partida ñ.mp4")
    p = imp.importar(origen, raiz, AJUSTES_POR_DEFECTO)
    assert p.estado == "en_cola" and p.nombre == "partida ñ.mp4" and p.duracion == 600.0
    assert (carpeta(raiz, p.id) / p.fuente).read_bytes() == origen.read_bytes()
    assert cargar(raiz, p.id) == p


def test_no_reimporta(tmp_path):
    raiz = tmp_path / "app"
    origen = video(tmp_path / "usb/a.mp4")
    imp.importar(origen, raiz, AJUSTES_POR_DEFECTO)
    imp.importar(origen, raiz, AJUSTES_POR_DEFECTO)
    assert imp.pendientes([origen], raiz) == []
    assert len(listar(raiz)) == 1


def test_mismo_video_desde_otra_carpeta(tmp_path):
    raiz = tmp_path / "app"
    imp.importar(video(tmp_path / "usb/a.mp4"), raiz, AJUSTES_POR_DEFECTO)
    otro = video(tmp_path / "entrada/a.mp4")
    assert imp.pendientes([otro], raiz) == []


def test_registra_en_procesados(tmp_path):
    raiz = tmp_path / "app"
    imp.importar(video(tmp_path / "usb/a.mp4"), raiz, AJUSTES_POR_DEFECTO)
    registro = json.loads((raiz / "salida/procesados.json").read_text(encoding="utf-8"))
    assert registro == {"a.mp4|10": []}


def test_reimportar_liberado_reutiliza(tmp_path):
    raiz = tmp_path / "app"
    origen = video(tmp_path / "usb/a.mp4")
    p = imp.importar(origen, raiz, AJUSTES_POR_DEFECTO)
    (carpeta(raiz, p.id) / "transcripcion.json").write_text("[[0, 1, \"hola\"]]", encoding="utf-8")
    (carpeta(raiz, p.id) / p.fuente).unlink()
    p.estado = "liberado"
    guardar(raiz, p)
    assert imp.pendientes([origen], raiz) == []
    q = imp.importar(origen, raiz, AJUSTES_POR_DEFECTO)
    assert q.id == p.id and q.estado == "en_cola"
    assert (carpeta(raiz, q.id) / q.fuente).exists()
    assert (carpeta(raiz, q.id) / "transcripcion.json").read_text(encoding="utf-8") == "[[0, 1, \"hola\"]]"
    assert len(listar(raiz)) == 1


def test_importar_subida(tmp_path):
    raiz = tmp_path / "app"
    p = imp.importar_subida("clip 🐊.mp4", io.BytesIO(b"abc"), 3, raiz, AJUSTES_POR_DEFECTO)
    assert p.clave == "clip 🐊.mp4|3"
    assert (carpeta(raiz, p.id) / p.fuente).read_bytes() == b"abc"


def test_unidades_de_prueba(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPPER_UNIDADES", str(tmp_path))
    assert imp.unidades_windows() == [tmp_path]


def test_video_vertical_entero_por_defecto(tmp_path, monkeypatch):
    monkeypatch.setattr(clipper, "analizar_archivo",
                        lambda ruta: clipper.InfoVideo(duracion=30.0, ancho=1080, alto=1920, hdr=False,
                                                       tiene_audio=True, fps=30.0))
    p = imp.importar(video(tmp_path / "usb/v.mp4"), tmp_path / "app", AJUSTES_POR_DEFECTO)
    assert p.opciones.formato == "blur"
