"""Renderiza desde el panel los momentos aprobados (o cambiados) con el mismo Clip.tsx que la vista previa."""

from __future__ import annotations

import json
from pathlib import Path

import clipper
from panel.proyecto import Momento, Proyecto, cargar, guardar, huella, necesita_render
from panel.trabajos import palabras_de


def _zoom(m: Momento) -> float | None:
    if m.zoom == "no":
        return None
    if m.zoom == "fijo":
        return m.zoom_en
    return m.zoom_auto


def trabajo_de(p: Proyecto, m: Momento, palabras, url_base: str, salida: Path | None = None) -> clipper.Trabajo:
    o = p.opciones
    preparado = p.preparado or p.fuente
    encuesta = (o.opcion_a, o.opcion_b) if o.tipo == "decide" and o.opcion_a and o.opcion_b else None
    return clipper.Trabajo(
        base=Path(preparado), salida=salida or Path(f"{p.id}_{m.id}.mp4"), duracion=m.fin - m.inicio,
        titulo=m.titulo, tipo=o.tipo, palabras=clipper.recortar_palabras(palabras, m.inicio, m.fin),
        zoom_en=_zoom(m), encuesta=encuesta, origen=f"{p.nombre} {clipper.mmss(m.inicio)}-{clipper.mmss(m.fin)}",
        fuente=Path(preparado), inicio=m.inicio, fin=m.fin, modo=o.formato, centro=o.centro, fps=p.fps,
        fuente_ancho=p.ancho, fuente_alto=p.alto, video_url=f"{url_base}/media/{p.id}/{preparado}",
    )


def _salida_para(raiz: Path, p: Proyecto, ajustes: dict) -> Path:
    carpeta_salida = Path(raiz) / ajustes.get("carpeta_salida", "salida") / p.id
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    usadas = {m.salida for m in p.momentos if m.salida}
    n = 1
    while str(carpeta_salida / f"{p.id}_momento{n:02d}.mp4") in usadas:
        n += 1
    return carpeta_salida / f"{p.id}_momento{n:02d}.mp4"


def _actualizar_registro(raiz: Path, p: Proyecto, ajustes: dict) -> None:
    ruta = Path(raiz) / ajustes.get("carpeta_salida", "salida") / clipper.REGISTRO
    registro = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    registro[p.clave] = [m.salida for m in p.momentos if m.salida]
    ruta.write_text(json.dumps(registro, indent=1, ensure_ascii=False), encoding="utf-8")


def renderizar(raiz: Path, pid: str, ajustes: dict, url_base: str, al_progresar=None) -> None:
    p = cargar(raiz, pid)
    cta = clipper.cta_para(p.opciones.tipo)
    pendientes = [m for m in p.momentos if necesita_render(p, m, cta)]
    if not pendientes:
        return
    palabras = palabras_de(raiz, pid)
    trabajos = []
    for m in pendientes:
        if not m.salida:
            m.salida = str(_salida_para(raiz, p, ajustes))
        trabajos.append((m, trabajo_de(p, m, palabras, url_base, Path(m.salida))))
    p.estado, p.progreso, p.error = "renderizando", 0.0, None
    guardar(raiz, p)

    def progreso(n: int, pct: int) -> None:
        p.progreso = ((n - 1) + pct / 100) / len(trabajos)
        guardar(raiz, p)
        if al_progresar:
            al_progresar(p.progreso)

    try:
        clipper.render_remotion([(clipper.props_remotion(t, cta), t.salida) for _, t in trabajos], progreso)
        for m, t in trabajos:
            if t.palabras:
                clipper.escribir_srt(clipper.agrupar(t.palabras), t.salida.with_suffix(".srt"))
            clipper.escribir_publicacion(t)
            m.estado, m.huella = "renderizado", huella(p, m, cta)
    except (Exception, SystemExit) as e:
        p.error = f"El render falló: {e}"
    p.estado, p.progreso = "listo", 1.0
    guardar(raiz, p)
    _actualizar_registro(raiz, p, ajustes)
