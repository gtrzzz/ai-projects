"""Un proyecto por vídeo importado: opciones, momentos y estado, guardados en proyectos/<id>/proyecto.json."""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

ESTADOS_MOMENTO = ("propuesto", "aprobado", "descartado", "renderizado")


@dataclass
class Opciones:
    modo_momentos: str = "auto"         # entero | auto | manual | auto_ia (Fase 3)
    clips: int | None = None            # None = automático
    exacto: bool = False
    duracion_clip: float = 25
    duracion_max: float = 60
    tipo: str = "momento"
    formato: str = "zoom"               # zoom | blur (entero, sin recortar) | recorte
    centro: float = 0.5
    idioma: str = "es"
    opcion_a: str | None = None
    opcion_b: str | None = None
    voz_en_off: dict | None = None      # Fase 4
    estilo: dict | None = None          # Fase 2
    camara: dict | None = None          # Fase 5

    @classmethod
    def desde_ajustes(cls, aj: dict) -> "Opciones":
        nombres = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in aj.items() if k in nombres})


def _subido_vacio() -> dict:
    return {"tiktok": False, "reels": False, "shorts": False}


@dataclass
class Momento:
    id: str
    inicio: float
    fin: float
    titulo: str
    zoom: str = "auto"                  # auto | no | fijo
    zoom_en: float | None = None        # segundo relativo al inicio, si zoom == "fijo"
    zoom_auto: float | None = None      # calculado por el detector
    estado: str = "propuesto"
    editado: bool = False
    salida: str | None = None
    huella: str | None = None
    subido: dict = field(default_factory=_subido_vacio)
    puntuacion: float | None = None
    motivos: dict = field(default_factory=dict)


@dataclass
class Proyecto:
    id: str
    nombre: str
    clave: str
    fuente: str
    preparado: str | None
    duracion: float
    ancho: int
    alto: int
    fps: float
    hdr: bool
    tiene_audio: bool
    estado: str
    progreso: float
    error: str | None
    opciones: Opciones
    momentos: list[Momento]
    creado: str

    @classmethod
    def desde_dict(cls, d: dict) -> "Proyecto":
        d = dict(d)
        d["opciones"] = Opciones(**d["opciones"])
        d["momentos"] = [Momento(**m) for m in d["momentos"]]
        return cls(**d)


def id_para(nombre: str, clave: str) -> str:
    base = unicodedata.normalize("NFKD", Path(nombre).stem).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:40].strip("-") or "video"
    return f"{base}-{hashlib.sha1(clave.encode()).hexdigest()[:6]}"


def carpeta(raiz: Path, pid: str) -> Path:
    return Path(raiz) / "proyectos" / pid


def guardar(raiz: Path, p: Proyecto) -> None:
    d = carpeta(raiz, p.id)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "proyecto.json.tmp"
    tmp.write_text(json.dumps(asdict(p), indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, d / "proyecto.json")


def cargar(raiz: Path, pid: str) -> Proyecto:
    texto = (carpeta(raiz, pid) / "proyecto.json").read_text(encoding="utf-8")
    return Proyecto.desde_dict(json.loads(texto))


def listar(raiz: Path) -> list[Proyecto]:
    base = Path(raiz) / "proyectos"
    if not base.is_dir():
        return []
    return [cargar(raiz, d.name) for d in sorted(base.iterdir()) if (d / "proyecto.json").exists()]


def huella(p: Proyecto, m: Momento, cta: str | None) -> str:
    o = p.opciones
    datos = {"inicio": m.inicio, "fin": m.fin, "titulo": m.titulo, "zoom": m.zoom, "zoom_en": m.zoom_en,
             "formato": o.formato, "centro": o.centro, "tipo": o.tipo, "opcion_a": o.opcion_a,
             "opcion_b": o.opcion_b, "cta": cta}
    return hashlib.sha1(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def necesita_render(p: Proyecto, m: Momento, cta: str | None) -> bool:
    if m.estado == "aprobado":
        return True
    if m.estado == "renderizado":
        return not m.salida or m.huella != huella(p, m, cta)
    return False
