"""Pruebas con ffmpeg de verdad (sin simulaciones) sobre vídeos sintéticos."""
import subprocess

import pytest

import clipper
import detector


def hacer_video(destino, segundos, con_audio=True):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=320x180:r=30:d={segundos}"]
    if con_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=d={segundos}", "-shortest", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(destino)]
    subprocess.run(cmd, check=True)
    return destino


@pytest.fixture(autouse=True)
def limpiar_cache():
    clipper.analizar_archivo.cache_clear()


def test_analizar_video_sin_audio(tmp_path):
    v = hacer_video(tmp_path / "mudo.mp4", 20, con_audio=False)
    assert not clipper.analizar_archivo(v).tiene_audio
    an = detector.analizar(v, [])
    assert an.duracion == 20 and len(an.puntuacion) == 20


def test_analizar_video_con_audio(tmp_path):
    v = hacer_video(tmp_path / "con.mp4", 12)
    assert detector.analizar(v, []).duracion == 12


def test_cortar_tramo(tmp_path):
    """Solo el tramo pedido, recodificado: Remotion no tiene que leer la grabación entera."""
    v = hacer_video(tmp_path / "largo.mp4", 20)
    dur = clipper.cortar_tramo(v, tmp_path / "tramo.mp4", 5.0, 12.0)
    assert dur == 7.0
    info = clipper.analizar_archivo(tmp_path / "tramo.mp4")
    assert abs(info.duracion - 7.0) < 0.2 and info.tiene_audio
