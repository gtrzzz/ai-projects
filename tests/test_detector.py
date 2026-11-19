import json

import numpy as np

from detector import Analisis, analisis_a_dict, analisis_de_dict, elegir_segmentos, zoom_automatico


def analisis_con_puntuacion(valores) -> Analisis:
    s = np.array(valores, dtype=float)
    return Analisis(len(s), s, {"sonido": s.copy(), "accion": s.copy(), "reaccion": np.zeros_like(s)})


def partida_con_picos() -> Analisis:
    """600 s: 3 bloques fuertes de 40 s (20 % del tiempo) y 5 picos suaves sueltos."""
    s = [0.1] * 600
    for ini in (20, 220, 420):
        s[ini:ini + 40] = [1.0] * 40
    for t in (120, 170, 320, 370, 520):
        s[t] = 0.3
    return analisis_con_puntuacion(s)


def test_exacto_llega_a_n():
    an = partida_con_picos()
    assert len(elegir_segmentos(an, max_clips=6)) < 6
    assert len(elegir_segmentos(an, max_clips=6, exacto=True)) == 6


def test_exacto_no_solapa():
    segs = elegir_segmentos(partida_con_picos(), max_clips=6, exacto=True)
    assert all(a.fin <= b.inicio for a, b in zip(segs, segs[1:]))


def test_zoom_solo_si_destaca():
    plano = analisis_con_puntuacion([0.3] * 100)
    assert zoom_automatico(plano, 10, 40) is None
    pico = analisis_con_puntuacion([0.2] * 100)
    pico.puntuacion[25] = 1.0
    assert zoom_automatico(pico, 10, 40) == 15.3


def test_zoom_no_en_bordes():
    a = analisis_con_puntuacion([0.2] * 100)
    a.puntuacion[10] = 1.0
    assert zoom_automatico(a, 10, 40) is None


def test_analisis_ida_y_vuelta():
    an = partida_con_picos()
    b = analisis_de_dict(json.loads(json.dumps(analisis_a_dict(an))))
    assert b.duracion == an.duracion
    assert np.allclose(b.puntuacion, an.puntuacion, atol=1e-4)
    assert set(b.componentes) == set(an.componentes)
