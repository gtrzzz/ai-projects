import json

from panel.ajustes import AJUSTES_POR_DEFECTO, cargar_ajustes, guardar_ajustes


def test_ajustes_por_defecto(tmp_path):
    assert cargar_ajustes(tmp_path) == AJUSTES_POR_DEFECTO
    assert AJUSTES_POR_DEFECTO["zoom_factor_mediana"] == 1.6
    assert AJUSTES_POR_DEFECTO["franjas"]["tiktok"] == [["19:00", "22:00"]]


def test_ajustes_mezcla(tmp_path):
    (tmp_path / "ajustes.json").write_text(json.dumps({"tipo": "truco"}), encoding="utf-8")
    aj = cargar_ajustes(tmp_path)
    assert aj["tipo"] == "truco"
    assert aj["formato"] == "zoom"


def test_guardar_ajustes(tmp_path):
    aj = dict(AJUSTES_POR_DEFECTO, idioma="en")
    guardar_ajustes(tmp_path, aj)
    assert cargar_ajustes(tmp_path)["idioma"] == "en"


def test_por_defecto_no_se_modifica(tmp_path):
    aj = cargar_ajustes(tmp_path)
    aj["franjas"]["tiktok"].append(["01:00", "02:00"])
    assert AJUSTES_POR_DEFECTO["franjas"]["tiktok"] == [["19:00", "22:00"]]
