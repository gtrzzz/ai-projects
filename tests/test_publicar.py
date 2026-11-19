from datetime import datetime

from panel.ajustes import AJUSTES_POR_DEFECTO
from panel.publicar import proxima_franja

F = AJUSTES_POR_DEFECTO["franjas"]


def test_franja_dentro():
    assert proxima_franja("tiktok", datetime(2026, 11, 19, 20, 30), F) == (
        datetime(2026, 11, 19, 19, 0), datetime(2026, 11, 19, 22, 0))


def test_franja_mas_tarde_hoy():
    assert proxima_franja("shorts", datetime(2026, 11, 19, 9, 0), F)[0] == datetime(2026, 11, 19, 16, 0)


def test_franja_siguiente_dia():
    assert proxima_franja("tiktok", datetime(2026, 11, 19, 23, 0), F)[0] == datetime(2026, 11, 20, 19, 0)


def test_varias_franjas():
    franjas = {"tiktok": [["19:00", "22:00"], ["13:00", "14:00"]]}
    assert proxima_franja("tiktok", datetime(2026, 11, 19, 10, 0), franjas)[0] == datetime(2026, 11, 19, 13, 0)
