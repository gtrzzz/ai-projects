"""Importar vídeos al panel: desde el USB de la PS5, la carpeta `entrada` o el navegador."""

from __future__ import annotations

import json
import os
import string
import time
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Callable

import clipper
from panel.proyecto import Opciones, Proyecto, carpeta, guardar, id_para, listar

EXTENSIONES = clipper.EXTENSIONES
BLOQUE = 8 * 1024 * 1024


def unidades_windows() -> list[Path]:
    """Unidades D:..Z: que existen. CLIPPER_UNIDADES (rutas separadas por os.pathsep) las sustituye en pruebas."""
    prueba = os.environ.get("CLIPPER_UNIDADES")
    if prueba:
        return [Path(r) for r in prueba.split(os.pathsep) if r]
    if os.name != "nt":
        return []
    return [Path(f"{letra}:\\") for letra in string.ascii_uppercase[3:] if Path(f"{letra}:\\").exists()]


def _videos_en(carpeta_base: Path) -> list[Path]:
    if not carpeta_base.is_dir():
        return []
    return sorted(p for p in carpeta_base.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONES)


def buscar_ps5(unidades: list[Path]) -> list[Path]:
    """Vídeos que la PS5 copia al USB (Galería multimedia → Copiar a USB): <unidad>/PS5/CREATE/..."""
    return [v for u in unidades for v in _videos_en(Path(u) / "PS5" / "CREATE")]


def buscar_entrada(carpeta_entrada: Path, quieto: float = 5.0) -> list[Path]:
    """Vídeos de `entrada` que llevan `quieto` segundos sin cambiar (los que aún se copian, no)."""
    if not carpeta_entrada.is_dir():
        return []
    limite = time.time() - quieto
    return sorted(p for p in carpeta_entrada.iterdir()
                  if p.is_file() and p.suffix.lower() in EXTENSIONES and p.stat().st_mtime < limite)


def clave_de(ruta: Path) -> str:
    """La misma clave que usa `clipper.py lote` en procesados.json."""
    return f"{ruta.name}|{ruta.stat().st_size}"


def _por_clave(raiz: Path) -> dict[str, Proyecto]:
    return {p.clave: p for p in listar(raiz)}


def pendientes(rutas: list[Path], raiz: Path) -> list[Path]:
    existentes = _por_clave(raiz)
    vistas: set[str] = set()
    fuera = []
    for r in rutas:
        c = clave_de(r)
        if c not in existentes and c not in vistas:
            vistas.add(c)
            fuera.append(r)
    return fuera


def _registrar(raiz: Path, ajustes: dict, clave: str) -> None:
    destino = Path(raiz) / ajustes.get("carpeta_salida", "salida")
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / clipper.REGISTRO
    registro = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    registro.setdefault(clave, [])
    ruta.write_text(json.dumps(registro, indent=1, ensure_ascii=False), encoding="utf-8")


def _copiar(flujo: BinaryIO, destino: Path, tamaño: int, al_progresar: Callable[[float], None] | None) -> None:
    hecho = 0
    tmp = destino.with_name(destino.name + ".parte")
    with open(tmp, "wb") as f:
        while bloque := flujo.read(BLOQUE):
            f.write(bloque)
            hecho += len(bloque)
            if al_progresar and tamaño:
                al_progresar(min(1.0, hecho / tamaño))
    os.replace(tmp, destino)


def _crear(raiz: Path, nombre: str, clave: str, flujo: BinaryIO, tamaño: int, ajustes: dict,
           al_progresar=None) -> Proyecto:
    raiz = Path(raiz)
    existente = _por_clave(raiz).get(clave)
    sin_video = existente is not None and not (carpeta(raiz, existente.id) / existente.fuente).exists()
    if existente and not (existente.estado in ("liberado", "error") and sin_video):
        return existente
    ext = Path(nombre).suffix.lower()
    pid = existente.id if existente else id_para(nombre, clave)
    d = carpeta(raiz, pid)
    d.mkdir(parents=True, exist_ok=True)
    fuente = f"fuente{ext}"
    _copiar(flujo, d / fuente, tamaño, al_progresar)
    try:
        info = clipper.analizar_archivo(d / fuente)
    except (Exception, SystemExit):
        # vídeo dañado: no se guarda la copia (ocupa GB) y queda en error para no copiarlo en bucle
        (d / fuente).unlink(missing_ok=True)
        info = None
    if info is None:
        p = existente or Proyecto(id=pid, nombre=nombre, clave=clave, fuente=fuente, preparado=None, duracion=0.0,
                                  ancho=0, alto=0, fps=60.0, hdr=False, tiene_audio=False, estado="error",
                                  progreso=0.0, error=None, opciones=Opciones.desde_ajustes(ajustes), momentos=[],
                                  creado=datetime.now().isoformat(timespec="seconds"))
        p.estado = "error"
        p.error = "No se puede leer el vídeo (¿está dañado o sin terminar de copiar?). Arréglalo y vuelve a arrastrarlo."
        guardar(raiz, p)
        return p
    if existente:  # vuelve tras "Liberar espacio" o tras un error: conserva transcripción, análisis y momentos
        p = existente
        p.fuente, p.preparado, p.estado, p.progreso, p.error = fuente, None, "en_cola", 0.0, None
        p.duracion, p.ancho, p.alto, p.fps, p.hdr, p.tiene_audio = (info.duracion, info.ancho, info.alto, info.fps,
                                                                    info.hdr, info.tiene_audio)
    else:
        p = Proyecto(id=pid, nombre=nombre, clave=clave, fuente=fuente, preparado=None, duracion=info.duracion,
                     ancho=info.ancho, alto=info.alto, fps=info.fps, hdr=info.hdr, tiene_audio=info.tiene_audio,
                     estado="en_cola", progreso=0.0, error=None, opciones=Opciones.desde_ajustes(ajustes),
                     momentos=[], creado=datetime.now().isoformat(timespec="seconds"))
        if info.alto > info.ancho:  # vídeo vertical: por defecto entero, sin recortar
            p.opciones.formato = "blur"
    guardar(raiz, p)
    _registrar(raiz, ajustes, clave)
    return p


def importar(ruta: Path, raiz: Path, ajustes: dict, al_progresar=None) -> Proyecto:
    ruta = Path(ruta)
    with open(ruta, "rb") as f:
        return _crear(raiz, ruta.name, clave_de(ruta), f, ruta.stat().st_size, ajustes, al_progresar)


def importar_subida(nombre: str, flujo: BinaryIO, tamaño: int, raiz: Path, ajustes: dict) -> Proyecto:
    return _crear(raiz, Path(nombre).name, f"{Path(nombre).name}|{tamaño}", flujo, tamaño, ajustes)
