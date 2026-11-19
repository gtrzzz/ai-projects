"""Liberar espacio: borra el vídeo original y el preparado de un proyecto terminado; conserva los clips."""

from __future__ import annotations

from pathlib import Path

import clipper
from panel.proyecto import Proyecto, cargar, carpeta, guardar, necesita_render


def _pesados(raiz: Path, p: Proyecto) -> list[Path]:
    d = carpeta(raiz, p.id)
    return [f for f in d.iterdir() if f.is_file() and f.name.startswith(("fuente", "preparado"))] if d.is_dir() else []


def liberable(raiz: Path, p: Proyecto) -> int:
    return sum(f.stat().st_size for f in _pesados(raiz, p))


def liberar(raiz: Path, pid: str) -> int:
    p = cargar(raiz, pid)
    cta = clipper.cta_para(p.opciones.tipo)
    if any(necesita_render(p, m, cta) for m in p.momentos):
        raise ValueError("Quedan clips sin renderizar. Renderízalos o descártalos antes de liberar espacio.")
    total = 0
    for f in _pesados(raiz, p):
        total += f.stat().st_size
        f.unlink()
    p.estado, p.preparado = "liberado", None
    guardar(raiz, p)
    return total
