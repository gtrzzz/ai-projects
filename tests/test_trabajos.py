import json

import numpy as np
import pytest

import clipper
import detector
from panel import trabajos as tr
from panel.ajustes import AJUSTES_POR_DEFECTO
from panel.proyecto import Momento, Opciones, Proyecto, cargar, carpeta, guardar
from tests.test_detector import analisis_con_puntuacion, partida_con_picos


def nuevo_proyecto(raiz, pid="p1", duracion=600.0, modo="auto", tiene_audio=True, estado="en_cola"):
    p = Proyecto(id=pid, nombre=f"{pid}.mp4", clave=f"{pid}.mp4|1", fuente="fuente.mp4", preparado=None,
                 duracion=duracion, ancho=1920, alto=1080, fps=60.0, hdr=False, tiene_audio=tiene_audio,
                 estado=estado, progreso=0.0, error=None,
                 opciones=Opciones.desde_ajustes(dict(AJUSTES_POR_DEFECTO, modo_momentos=modo)),
                 momentos=[], creado="2026-11-19T10:00:00")
    guardar(raiz, p)
    (carpeta(raiz, pid) / "fuente.mp4").write_bytes(b"x")
    return p


@pytest.fixture
def falsos(monkeypatch):
    llamadas = {"transcribir": 0}

    def transcribir(*a, **k):
        llamadas["transcribir"] += 1
        return [(25.0, 25.5, "madre"), (25.5, 26.0, "mía")]

    monkeypatch.setattr(clipper, "preparar_fuente", lambda entrada, destino: entrada)
    monkeypatch.setattr(clipper, "transcribir", transcribir)
    monkeypatch.setattr(detector, "analizar", lambda ruta, palabras=None, *a, **k: partida_con_picos())
    return llamadas


def test_entero_un_momento():
    proy = Proyecto(id="x", nombre="x.mp4", clave="x|1", fuente="f.mp4", preparado=None, duracion=600.0, ancho=1920,
                    alto=1080, fps=60, hdr=False, tiene_audio=True, estado="listo", progreso=1, error=None,
                    opciones=Opciones(modo_momentos="entero"), momentos=[], creado="")
    ms = tr.proponer(proy, partida_con_picos(), [], AJUSTES_POR_DEFECTO)
    assert [(m.inicio, m.fin) for m in ms] == [(0.0, 600.0)]
    assert ms[0].titulo and ms[0].estado == "propuesto"


def test_corto_en_auto_es_entero(tmp_path):
    p = nuevo_proyecto(tmp_path, duracion=90.0)
    ms = tr.proponer(p, analisis_con_puntuacion([0.1] * 90), [], AJUSTES_POR_DEFECTO)
    assert [(m.inicio, m.fin) for m in ms] == [(0.0, 90.0)]


def test_auto_propone_varios(tmp_path):
    p = nuevo_proyecto(tmp_path)
    ms = tr.proponer(p, partida_con_picos(), [], AJUSTES_POR_DEFECTO)
    assert len(ms) == 2 and all(m.estado == "propuesto" for m in ms)  # ~1 cada 4 min


def test_auto_exacto(tmp_path):
    p = nuevo_proyecto(tmp_path)
    p.opciones.clips, p.opciones.exacto = 6, True
    assert len(tr.proponer(p, partida_con_picos(), [], AJUSTES_POR_DEFECTO)) == 6


def test_manual_sin_momentos(tmp_path):
    p = nuevo_proyecto(tmp_path, modo="manual")
    assert tr.proponer(p, partida_con_picos(), [], AJUSTES_POR_DEFECTO) == []


def test_reproponer_conserva_aprobados(tmp_path):
    p = nuevo_proyecto(tmp_path)
    p.momentos = [Momento(id="ok", inicio=20.0, fin=60.0, titulo="Mío", estado="aprobado"),
                  Momento(id="viejo", inicio=300.0, fin=320.0, titulo="x")]
    ms = tr.proponer(p, partida_con_picos(), [], AJUSTES_POR_DEFECTO)
    ids = [m.id for m in ms]
    assert "ok" in ids and "viejo" not in ids
    otros = [m for m in ms if m.id != "ok"]
    assert all(m.fin <= 20.0 or m.inicio >= 60.0 for m in otros)


def test_procesar_completo(tmp_path, falsos):
    nuevo_proyecto(tmp_path)
    tr.procesar(tmp_path, "p1", AJUSTES_POR_DEFECTO)
    p = cargar(tmp_path, "p1")
    assert p.estado == "listo" and p.preparado == "fuente.mp4" and len(p.momentos) == 2
    assert tr.palabras_de(tmp_path, "p1") == [(25.0, 25.5, "madre"), (25.5, 26.0, "mía")]
    assert tr.analisis_de(tmp_path, "p1").duracion == 600


def test_no_repite_transcripcion(tmp_path, falsos):
    nuevo_proyecto(tmp_path)
    tr.procesar(tmp_path, "p1", AJUSTES_POR_DEFECTO)
    tr.procesar(tmp_path, "p1", AJUSTES_POR_DEFECTO)
    assert falsos["transcribir"] == 1


def test_video_sin_audio(tmp_path, falsos):
    nuevo_proyecto(tmp_path, tiene_audio=False)
    tr.procesar(tmp_path, "p1", AJUSTES_POR_DEFECTO)
    assert falsos["transcribir"] == 0
    assert tr.palabras_de(tmp_path, "p1") == []
    assert cargar(tmp_path, "p1").estado == "listo"


def test_error_queda_en_el_proyecto(tmp_path, falsos, monkeypatch):
    nuevo_proyecto(tmp_path)

    def roto(*a, **k):
        raise SystemExit("ffmpeg falló (código 1)")

    monkeypatch.setattr(clipper, "preparar_fuente", roto)
    tr.procesar(tmp_path, "p1", AJUSTES_POR_DEFECTO)
    p = cargar(tmp_path, "p1")
    assert p.estado == "error" and "ffmpeg" in p.error


def test_error_no_tumba_la_cola(tmp_path):
    hechos = []

    def procesar(pid):
        if pid == "p1":
            raise RuntimeError("roto")
        hechos.append(pid)

    cola = tr.Cola({"procesar": procesar})
    cola.encolar("procesar", "p1")
    cola.encolar("procesar", "p2")
    cola.ejecutar_pendientes()
    assert hechos == ["p2"]
    assert cola.estado() == []


def test_reanudar_tras_cierre(tmp_path):
    nuevo_proyecto(tmp_path, "p1", estado="transcribiendo")
    nuevo_proyecto(tmp_path, "p2", estado="listo")
    p3 = nuevo_proyecto(tmp_path, "p3", estado="renderizando")
    cola = tr.Cola({})
    cola.reanudar(tmp_path)
    assert [(t["tipo"], t["pid"]) for t in cola.estado()] == [("procesar", "p1"), ("render", "p3")]
    assert cargar(tmp_path, "p3").estado == "listo"


def test_sin_revision_encola_render(tmp_path, falsos):
    nuevo_proyecto(tmp_path)
    cola = tr.Cola({})
    tr.procesar(tmp_path, "p1", dict(AJUSTES_POR_DEFECTO, revisar_antes=False), cola)
    p = cargar(tmp_path, "p1")
    assert all(m.estado == "aprobado" for m in p.momentos)
    assert [(t["tipo"], t["pid"]) for t in cola.estado()] == [("render", "p1")]


def test_proponer_no_pasa_del_final(tmp_path):
    """El análisis redondea a segundos (201) aunque el vídeo dure 200,7 s: ningún momento acaba después."""
    p = nuevo_proyecto(tmp_path, duracion=200.7)
    p.opciones.modo_momentos = "auto"
    s = [0.1] * 201
    s[190:201] = [1.0] * 11
    ms = tr.proponer(p, analisis_con_puntuacion(s), [], AJUSTES_POR_DEFECTO)
    assert ms and all(m.fin <= 200.7 for m in ms)
