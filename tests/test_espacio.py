import pytest

from panel import espacio
from panel.proyecto import Momento, cargar, carpeta, guardar
from tests.test_trabajos import nuevo_proyecto


def preparar(tmp_path, *momentos):
    p = nuevo_proyecto(tmp_path, estado="listo")
    d = carpeta(tmp_path, p.id)
    (d / "fuente.mp4").write_bytes(b"x" * 100)
    (d / "preparado.mp4").write_bytes(b"x" * 50)
    (d / "transcripcion.json").write_text("[]", encoding="utf-8")
    p.preparado = "preparado.mp4"
    p.momentos = list(momentos)
    guardar(tmp_path, p)
    return p


def test_liberable(tmp_path):
    p = preparar(tmp_path)
    assert espacio.liberable(tmp_path, p) == 150


def test_liberar(tmp_path):
    salida = tmp_path / "clip.mp4"
    salida.write_bytes(b"mp4")
    p = preparar(tmp_path, Momento(id="a", inicio=0, fin=10, titulo="A", estado="descartado"))
    assert espacio.liberar(tmp_path, p.id) == 150
    d = carpeta(tmp_path, p.id)
    assert sorted(f.name for f in d.iterdir()) == ["proyecto.json", "transcripcion.json"]
    assert cargar(tmp_path, p.id).estado == "liberado"
    assert salida.exists()


def test_no_liberar_si_falta_render(tmp_path):
    p = preparar(tmp_path, Momento(id="a", inicio=0, fin=10, titulo="A", estado="aprobado"))
    with pytest.raises(ValueError, match="Quedan clips sin renderizar"):
        espacio.liberar(tmp_path, p.id)
    assert (carpeta(tmp_path, p.id) / "fuente.mp4").exists()
