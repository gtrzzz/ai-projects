import subprocess
from types import SimpleNamespace

import numpy as np

import clipper


class ModeloFalso:
    def __init__(self):
        self.audio = None

    def transcribe(self, audio, **opciones):
        self.audio = audio
        palabra = SimpleNamespace(word=" hola", start=0.1, end=0.4)
        seg = SimpleNamespace(text="hola", no_speech_prob=0.1, avg_logprob=-0.2, words=[palabra])
        return iter([seg]), None


def test_transcribir_pasa_audio_en_memoria(tmp_path, monkeypatch):
    """faster-whisper abre los archivos con PyAV y PyAV 19 rompió esa llamada: le pasamos el audio ya decodificado."""
    wav = tmp_path / "a.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=d=2", str(wav)], check=True)
    modelo = ModeloFalso()
    monkeypatch.setattr(clipper, "_cargar_whisper", lambda nombre, dispositivo: modelo)
    assert clipper.transcribir(wav, "es", "small") == [(0.1, 0.4, "hola")]
    assert isinstance(modelo.audio, np.ndarray) and modelo.audio.dtype == np.float32
    assert abs(len(modelo.audio) - 32000) < 400  # 2 s a 16 kHz
