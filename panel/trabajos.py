"""Proceso de cada proyecto (preparar, transcribir, analizar, proponer) y la cola que lo ejecuta en orden."""

from __future__ import annotations

import json
import queue
import threading
import traceback
import uuid
from pathlib import Path
from typing import Callable

import clipper
import detector
from panel.proyecto import Momento, Proyecto, cargar, carpeta, guardar, listar

TRANSCRIPCION = "transcripcion.json"
ANALISIS = "analisis.json"
SIN_TERMINAR = ("importando", "en_cola", "preparando", "transcribiendo", "analizando")


def palabras_de(raiz: Path, pid: str) -> list[tuple[float, float, str]]:
    ruta = carpeta(raiz, pid) / TRANSCRIPCION
    if not ruta.exists():
        return []
    return [(float(a), float(b), str(t)) for a, b, t in json.loads(ruta.read_text(encoding="utf-8"))]


def analisis_de(raiz: Path, pid: str) -> detector.Analisis | None:
    ruta = carpeta(raiz, pid) / ANALISIS
    if not ruta.exists():
        return None
    return detector.analisis_de_dict(json.loads(ruta.read_text(encoding="utf-8")))


def _nuevo_id() -> str:
    return uuid.uuid4().hex[:8]


def _solapa(a: Momento, b: Momento) -> bool:
    return a.inicio < b.fin and b.inicio < a.fin


def proponer(p: Proyecto, an: detector.Analisis | None, palabras: list, ajustes: dict) -> list[Momento]:
    """Momentos propuestos según el modo; conserva los aprobados, renderizados y editados a mano."""
    o = p.opciones
    conservados = [m for m in p.momentos if m.estado in ("aprobado", "renderizado") or m.editado]
    zoom = lambda ini, fin: (detector.zoom_automatico(an, ini, fin, ajustes["zoom_percentil"],  # noqa: E731
                                                      ajustes["zoom_factor_mediana"]) if an else None)
    nuevos: list[Momento] = []
    entero = o.modo_momentos == "entero" or (o.modo_momentos == "auto" and p.duracion <= ajustes["umbral_largo"])
    if entero:
        nuevos = [Momento(id=_nuevo_id(), inicio=0.0, fin=round(p.duracion, 3),
                          titulo=clipper.gancho_automatico(o.tipo, p.nombre), zoom_auto=zoom(0.0, p.duracion))]
    elif o.modo_momentos == "auto" and an is not None:
        segs = detector.elegir_segmentos(an, palabras, max_clips=o.clips, dur_obj=o.duracion_clip,
                                         dur_max=o.duracion_max, exacto=o.exacto)
        for n, s in enumerate(segs, 1):
            fin = min(float(s.fin), round(p.duracion, 3))  # el análisis redondea a segundos enteros
            if fin - s.inicio < 1:
                continue
            nuevos.append(Momento(id=_nuevo_id(), inicio=float(s.inicio), fin=fin,
                                  titulo=clipper.gancho_automatico(o.tipo, f"{p.nombre}{n}"),
                                  zoom_auto=zoom(s.inicio, fin), puntuacion=s.puntuacion, motivos=s.motivos))
    nuevos = [m for m in nuevos if not any(_solapa(m, c) for c in conservados)]
    return sorted(conservados + nuevos, key=lambda m: m.inicio)


def _paso(raiz: Path, p: Proyecto, estado: str, progreso: float) -> None:
    p.estado, p.progreso = estado, progreso
    guardar(raiz, p)


def procesar(raiz: Path, pid: str, ajustes: dict, cola: "Cola | None" = None) -> None:
    p = cargar(raiz, pid)
    d = carpeta(raiz, pid)
    try:
        _paso(raiz, p, "preparando", 0.05)
        if not p.preparado or not (d / p.preparado).exists():
            p.preparado = clipper.preparar_fuente(d / p.fuente, d / "preparado.mp4").name

        _paso(raiz, p, "transcribiendo", 0.2)
        if not (d / TRANSCRIPCION).exists():
            palabras = []
            if p.tiene_audio:
                palabras = clipper.transcribir(d / p.fuente, p.opciones.idioma, ajustes["modelo"])
            (d / TRANSCRIPCION).write_text(json.dumps(palabras, ensure_ascii=False), encoding="utf-8")
        palabras = palabras_de(raiz, pid)

        _paso(raiz, p, "analizando", 0.6)
        if not (d / ANALISIS).exists():
            an = detector.analizar(d / p.preparado, palabras)
            (d / ANALISIS).write_text(json.dumps(detector.analisis_a_dict(an)), encoding="utf-8")

        p.momentos = proponer(p, analisis_de(raiz, pid), palabras, ajustes)
        if not ajustes.get("revisar_antes", True):
            for m in p.momentos:
                if m.estado == "propuesto":
                    m.estado = "aprobado"
        p.error = None
        _paso(raiz, p, "listo", 1.0)
        if not ajustes.get("revisar_antes", True) and cola is not None:
            cola.encolar("render", pid)
    except (Exception, SystemExit) as e:
        p.estado, p.error = "error", str(e) or type(e).__name__
        guardar(raiz, p)


class Cola:
    """Un único hilo para lo pesado (copiar, preparar, transcribir, analizar, renderizar), uno detrás de otro."""

    def __init__(self, manejadores: dict[str, Callable[..., None]]):
        self.manejadores = manejadores
        self._cola: queue.Queue = queue.Queue()
        self._pendientes: list[dict] = []
        self._actual: dict | None = None
        self._cerrojo = threading.Lock()
        self._hilo: threading.Thread | None = None

    def encolar(self, tipo: str, pid: str, **datos) -> None:
        trabajo = {"tipo": tipo, "pid": pid, "datos": datos}
        with self._cerrojo:
            if any(t["tipo"] == tipo and t["pid"] == pid and t["datos"] == datos for t in self._pendientes):
                return
            self._pendientes.append(trabajo)
        self._cola.put(trabajo)

    def estado(self) -> list[dict]:
        with self._cerrojo:
            lista = ([dict(self._actual, estado="en_curso")] if self._actual else []) + \
                    [dict(t, estado="en_cola") for t in self._pendientes]
        return [{"tipo": t["tipo"], "pid": t["pid"], "estado": t["estado"]} for t in lista]

    def _ejecutar_uno(self, trabajo: dict) -> None:
        with self._cerrojo:
            self._pendientes.remove(trabajo)
            self._actual = trabajo
        try:
            self.manejadores[trabajo["tipo"]](trabajo["pid"], **trabajo["datos"])
        except BaseException:  # un trabajo roto nunca para la cola
            traceback.print_exc()
        finally:
            with self._cerrojo:
                self._actual = None

    def ejecutar_pendientes(self) -> None:
        """Ejecuta lo que hay en la cola en este hilo (para pruebas)."""
        while not self._cola.empty():
            self._ejecutar_uno(self._cola.get())

    def iniciar(self) -> None:
        def bucle():
            while True:
                self._ejecutar_uno(self._cola.get())

        self._hilo = threading.Thread(target=bucle, daemon=True, name="cola-clipper")
        self._hilo.start()

    def reanudar(self, raiz: Path) -> None:
        """Al arrancar: vuelve a encolar lo que se quedó a medias al cerrar el panel."""
        for p in listar(raiz):
            if p.estado in SIN_TERMINAR:
                self.encolar("procesar", p.id)
            elif p.estado == "renderizando":
                p.estado = "listo"
                guardar(raiz, p)
                self.encolar("render", p.id)
