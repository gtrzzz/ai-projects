"""
detector.py - Encuentra los mejores momentos de una partida larga.

Señales que mide (por segundo):
  - sonido:   picos de volumen respecto al nivel normal de la partida (disparos, choques, explosiones)
  - accion:   cuánto cambia la imagen (persecuciones, caos) frente a ir andando o estar en un menú
  - reaccion: tus reacciones habladas (exclamaciones, risas, gritos) detectadas con Whisper

Combina las tres, busca los picos y corta segmentos sin partir frases a la mitad.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

AUDIO_SR = 8000         # suficiente para medir volumen
VIDEO_FPS = 4           # fotogramas por segundo para medir movimiento
VIDEO_W, VIDEO_H = 96, 54

PESOS = {"sonido": 0.40, "accion": 0.25, "reaccion": 0.35}

# Exclamaciones típicas en español (y algo de inglés). Se buscan en la transcripción de tu voz.
REACCIONES = [
    r"\bja(ja)+\b", r"\bje(je)+\b", r"\bjaj", r"\bhostia", r"\bostia", r"\bjoder", r"\bmadre m[ií]a",
    r"\bdios\b", r"\bno puede ser", r"\bincre[ií]ble", r"\bbrutal", r"\blocura", r"\bflip", r"\bwow\b",
    r"\bqu[eé] (es esto|ha pasado|haces|co[ñn]o)", r"\bcuidado", r"\bcorre\b", r"\bsocorro", r"\bmierda",
    r"\bno no no", r"\bvamos\b", r"\bnoo+\b", r"\bs[ií]+\b!", r"\btoma\b", r"\bqu[eé] fuerte",
    r"\bmira (esto|eso)", r"\bme cago", r"\bpero qu[eé]", r"\bwhat\b", r"\boh my god", r"\bbro\b",
]
REACCIONES_RE = re.compile("|".join(REACCIONES), re.IGNORECASE)


@dataclass
class Segmento:
    inicio: float
    fin: float
    pico: float                 # segundo (absoluto) de máxima intensidad
    puntuacion: float
    motivos: dict = field(default_factory=dict)

    @property
    def duracion(self) -> float:
        return self.fin - self.inicio


# --------------------------------------------------------------------------- extracción de señales

def _extraer(ruta: Path, inicio: float | None, fin: float | None) -> tuple[np.ndarray, np.ndarray]:
    """Una sola pasada de ffmpeg: audio mono a 8 kHz y vídeo gris en miniatura a 4 fps."""
    with tempfile.TemporaryDirectory() as tmp:
        a_raw, v_raw = Path(tmp) / "a.raw", Path(tmp) / "v.raw"
        rango = []
        if inicio:
            rango += ["-ss", f"{inicio:.3f}"]
        if fin is not None:
            rango += ["-t", f"{fin - (inicio or 0):.3f}"]

        def ejecutar(hw: list[str]) -> bool:
            cmd = ["ffmpeg", "-y", "-v", "error", *hw, *rango, "-i", str(ruta),
                   "-map", "0:v:0", "-vf", f"fps={VIDEO_FPS},scale={VIDEO_W}:{VIDEO_H},format=gray",
                   "-f", "rawvideo", str(v_raw),
                   "-map", "0:a:0?", "-ac", "1", "-ar", str(AUDIO_SR), "-f", "s16le", str(a_raw)]
            return subprocess.run(cmd, capture_output=True).returncode == 0

        # decodificar en la GPU es mucho más rápido con partidas de horas
        if not ejecutar(["-hwaccel", "cuda"]) and not ejecutar([]):
            raise SystemExit(f"No se pudo analizar {ruta}")

        audio = np.fromfile(a_raw, dtype=np.int16) if a_raw.exists() else np.zeros(0, np.int16)
        video = np.fromfile(v_raw, dtype=np.uint8)
    n = len(video) // (VIDEO_W * VIDEO_H)
    return audio, video[: n * VIDEO_W * VIDEO_H].reshape(n, VIDEO_H, VIDEO_W)


def _rango_percentil(x: np.ndarray) -> np.ndarray:
    """Normaliza a 0..1 según la posición dentro de la propia partida (robusto a volumen/brillo)."""
    if len(x) == 0 or np.allclose(x, x[0]):
        return np.zeros_like(x, dtype=float)
    orden = x.argsort().argsort()
    return orden / (len(x) - 1)


def _suavizar(x: np.ndarray, ventana: int) -> np.ndarray:
    if ventana <= 1 or len(x) == 0:
        return x
    k = np.ones(ventana) / ventana
    return np.convolve(x, k, mode="same")


def _desviacion_local(x: np.ndarray, ventana: int) -> np.ndarray:
    """Cuánto sobresale cada valor respecto a la mediana de los ~ventana segundos que lo rodean."""
    if len(x) == 0:
        return x
    mitad = ventana // 2
    rellenado = np.pad(x, mitad, mode="edge")
    vistas = np.lib.stride_tricks.sliding_window_view(rellenado, ventana)[: len(x)]
    return x - np.median(vistas, axis=1)


def señal_sonido(audio: np.ndarray, segundos: int) -> np.ndarray:
    if len(audio) == 0:
        return np.zeros(segundos)
    a = audio.astype(np.float32) / 32768
    # RMS en ventanas de 0,25 s y nos quedamos con el máximo de cada segundo (los golpes son cortos)
    paso = AUDIO_SR // 4
    n = len(a) // paso
    rms = np.sqrt(np.mean(a[: n * paso].reshape(n, paso) ** 2, axis=1) + 1e-10)
    db = 20 * np.log10(rms)
    db = db[: segundos * 4]
    db = np.pad(db, (0, max(0, segundos * 4 - len(db))), constant_values=db.min() if len(db) else -90)
    por_segundo = db.reshape(segundos, 4).max(axis=1)
    return _desviacion_local(por_segundo, 61)


def señal_accion(video: np.ndarray, segundos: int) -> np.ndarray:
    if len(video) < 2:
        return np.zeros(segundos)
    v = video.astype(np.int16)
    dif = np.abs(np.diff(v, axis=0)).mean(axis=(1, 2))
    dif = np.concatenate([[dif[0]], dif])
    # fundidos a negro y menús quietos -> poco; persecuciones -> mucho. Cortes de escena aislados se suavizan.
    dif = dif[: segundos * VIDEO_FPS]
    dif = np.pad(dif, (0, max(0, segundos * VIDEO_FPS - len(dif))))
    por_segundo = dif.reshape(segundos, VIDEO_FPS).mean(axis=1)
    brillo = video.mean(axis=(1, 2))[: segundos * VIDEO_FPS]
    brillo = np.pad(brillo, (0, max(0, segundos * VIDEO_FPS - len(brillo)))).reshape(segundos, VIDEO_FPS).mean(axis=1)
    por_segundo[brillo < 12] = 0  # pantallas negras / cargas
    return por_segundo


def señal_reaccion(palabras, segundos: int) -> np.ndarray:
    """palabras: [(inicio, fin, texto)] con tiempos relativos al tramo analizado."""
    r = np.zeros(segundos)
    if not palabras:
        return r
    # Une palabras cercanas en frases para buscar expresiones de varias palabras
    texto, tiempos = [], []
    for ini, fin, w in palabras:
        texto.append(w)
        tiempos.append(ini)
    frase = " ".join(texto)
    posiciones = np.cumsum([0] + [len(w) + 1 for w in texto[:-1]])
    for m in REACCIONES_RE.finditer(frase):
        idx = int(np.searchsorted(posiciones, m.start(), side="right") - 1)
        s = int(tiempos[idx])
        if 0 <= s < segundos:
            r[s] += 1.0
    for ini, fin, w in palabras:
        s = int(ini)
        if 0 <= s < segundos:
            r[s] += 0.05  # hablar ya es un poco de señal (estás comentando algo)
            if "!" in w or "?" in w:
                r[s] += 0.4
            if w.isupper() and len(w) > 2:  # Whisper a veces pone gritos en mayúsculas
                r[s] += 0.4
    return _suavizar(r, 3)


@dataclass
class Analisis:
    duracion: int
    puntuacion: np.ndarray
    componentes: dict


def analizar(ruta: Path, palabras=None, inicio: float | None = None, fin: float | None = None) -> Analisis:
    audio, video = _extraer(ruta, inicio, fin)
    segundos = max(1, int(round(len(video) / VIDEO_FPS)) if len(video) else len(audio) // AUDIO_SR)
    # Escalas absolutas (no percentiles): así una partida tranquila no convierte cualquier ruido en "pico"
    sonido = señal_sonido(audio, segundos)               # dB por encima del nivel normal de ese minuto
    accion = señal_accion(video, segundos)
    techo_accion = max(np.percentile(accion, 97), 1e-6)  # lo más movido de la partida = 1
    reac = señal_reaccion(palabras, segundos)
    comp = {
        "sonido": np.clip(sonido / 14.0, 0, 1),          # +14 dB o más = máximo
        "accion": np.clip(accion / techo_accion, 0, 1) ** 1.5,  # castiga el movimiento normal (ir andando)
        "reaccion": np.clip(reac / 1.2, 0, 1),           # una exclamación clara ~ 0.8-1
    }

    # Si no hay voz, se reparte su peso entre las otras dos señales
    pesos = dict(PESOS)
    if not (reac > 0).any():
        pesos = {"sonido": 0.6, "accion": 0.4, "reaccion": 0.0}
    total = sum(pesos[k] * comp[k] for k in comp)
    # potenciamos los momentos donde coinciden varias señales a la vez
    coincidencia = (comp["sonido"] > 0.8).astype(float) + (comp["accion"] > 0.8) + (comp["reaccion"] > 0.5)
    total = total * (1 + 0.15 * coincidencia)
    return Analisis(segundos, _suavizar(total, 5), comp)


# --------------------------------------------------------------------------- selección de segmentos

def _ajustar_a_frases(ini: float, fin: float, palabras, limite: float) -> tuple[float, float]:
    """Evita empezar o terminar con una palabra cortada."""
    for p_ini, p_fin, _ in palabras or []:
        if p_ini < ini < p_fin:
            ini = p_ini - 0.2
        if p_ini < fin < p_fin:
            fin = p_fin + 0.3
    return max(0.0, ini), min(limite, fin)


def elegir_segmentos(an: Analisis, palabras=None, max_clips: int | None = None,
                     dur_min: float = 15, dur_obj: float = 25, dur_max: float = 60,
                     separacion: float = 8) -> list[Segmento]:
    s = an.puntuacion
    n = an.duracion
    if max_clips is None:  # ~1 clip cada 4 min de partida, entre 1 y 15
        max_clips = int(np.clip(round(n / 240), 1, 15))
    if n <= dur_min:
        pico = float(np.argmax(s)) if len(s) else 0.0
        return [Segmento(0, float(n), pico, float(s.max()) if len(s) else 0, {})]

    umbral_base = np.percentile(s, 60)
    umbral_pico = np.percentile(s, 85)
    ocupado = np.zeros(n, dtype=bool)
    elegidos: list[Segmento] = []
    orden = np.argsort(s)[::-1]

    for pico in orden:
        if len(elegidos) >= max_clips or s[pico] < umbral_pico:
            break  # orden descendente: a partir de aquí ya nada destaca
        if ocupado[pico]:
            continue
        # hueco libre alrededor del pico (sin pisar momentos ya elegidos)
        libre_ini = pico
        while libre_ini > 0 and not ocupado[libre_ini - 1]:
            libre_ini -= 1
        libre_fin = pico
        while libre_fin < n and not ocupado[libre_fin]:
            libre_fin += 1
        if libre_fin - libre_ini < dur_min:
            ocupado[libre_ini:libre_fin] = True
            continue

        # poco contexto antes (en TikTok el primer segundo decide) y más margen para el remate
        ini = max(libre_ini, pico - dur_obj * 0.3)
        fin = min(libre_fin, pico + dur_obj * 0.7)
        # extender mientras el entorno siga siendo interesante
        while fin - ini < dur_max and fin < libre_fin - 1 and s[int(fin)] > umbral_base:
            fin += 1
        while fin - ini < dur_max and ini > libre_ini + 1 and s[int(ini)] > umbral_base:
            ini -= 1
        if fin - ini < dur_min:
            falta = dur_min - (fin - ini)
            ini = max(libre_ini, ini - falta / 2)
            fin = min(libre_fin, ini + dur_min)
        ini, fin = _ajustar_a_frases(ini, fin, palabras, n)
        ini, fin = max(ini, libre_ini), min(fin, libre_fin)

        ocupado[int(max(0, ini - separacion)):int(min(n, fin + separacion))] = True
        tramo = slice(int(ini), max(int(ini) + 1, int(fin)))
        motivos = {k: round(float(v[tramo].max()), 2) for k, v in an.componentes.items()}
        elegidos.append(Segmento(round(ini, 2), round(fin, 2), float(pico), round(float(s[pico]), 3), motivos))

    return sorted(elegidos, key=lambda x: x.inicio)


def pico_relativo(an: Analisis) -> float:
    """Segundo de máxima intensidad (para el zoom automático)."""
    return float(np.argmax(an.puntuacion)) if len(an.puntuacion) else 0.0
