"""Textos para pegar en cada plataforma y la próxima franja horaria sugerida."""

from __future__ import annotations

from datetime import datetime, time, timedelta

import clipper
from panel.proyecto import Momento, Proyecto
from panel.render import trabajo_de


def textos(p: Proyecto, m: Momento, palabras, url_base: str = "") -> dict[str, str]:
    return clipper.textos_publicacion(trabajo_de(p, m, palabras, url_base))


def _hora(texto: str) -> time:
    h, mnt = texto.split(":")
    return time(int(h), int(mnt))


def proxima_franja(plataforma: str, ahora: datetime, franjas: dict) -> tuple[datetime, datetime]:
    """La franja en curso si estamos dentro; si no, la siguiente (hoy o mañana). Hora local del PC."""
    candidatas = []
    for dias in (0, 1):
        dia = (ahora + timedelta(days=dias)).date()
        for ini, fin in franjas.get(plataforma, []):
            a, b = datetime.combine(dia, _hora(ini)), datetime.combine(dia, _hora(fin))
            if b > ahora:
                candidatas.append((a, b))
    return min(candidatas)
