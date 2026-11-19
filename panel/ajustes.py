"""Ajustes del panel: valores por defecto mezclados con lo que el usuario guarda en ajustes.json."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

ARCHIVO = "ajustes.json"

AJUSTES_POR_DEFECTO: dict = {
    "modo_momentos": "auto",
    "clips": None,
    "duracion_clip": 25,
    "duracion_max": 60,
    "umbral_largo": 150,
    "tipo": "momento",
    "formato": "zoom",
    "centro": 0.5,
    "idioma": "es",
    "modelo": "large-v3-turbo",
    "carpeta_salida": "salida",
    "importar_usb_auto": False,
    "revisar_antes": True,
    "zoom_percentil": 85,
    "zoom_factor_mediana": 1.6,
    "franjas": {
        "tiktok": [["19:00", "22:00"]],
        "reels": [["13:00", "15:00"]],
        "shorts": [["16:00", "19:00"]],
    },
}


def cargar_ajustes(raiz: Path) -> dict:
    aj = copy.deepcopy(AJUSTES_POR_DEFECTO)
    ruta = Path(raiz) / ARCHIVO
    if ruta.exists():
        aj.update(json.loads(ruta.read_text(encoding="utf-8")))
    return aj


def guardar_ajustes(raiz: Path, ajustes: dict) -> None:
    ruta = Path(raiz) / ARCHIVO
    tmp = ruta.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ajustes, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, ruta)
