import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from panel.proyecto import Momento, cargar, carpeta, guardar, id_para
from panel.servidor import crear_app
from panel.trabajos import Cola
from tests.test_trabajos import nuevo_proyecto

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def raiz(tmp_path):
    shutil.copy(RAIZ / "plantillas.json", tmp_path / "plantillas.json")
    return tmp_path


@pytest.fixture
def cola():
    return Cola({})


@pytest.fixture
def cliente(raiz, cola):
    return TestClient(crear_app(raiz, cola))


@pytest.fixture
def proyecto(raiz):
    p = nuevo_proyecto(raiz, estado="listo")
    (carpeta(raiz, p.id) / "fuente.mp4").write_bytes(bytes(range(256)) * 4)
    p.preparado = "fuente.mp4"
    p.momentos = [Momento(id="m1", inicio=10.0, fin=35.0, titulo="Hola")]
    guardar(raiz, p)
    return p


def test_estado_vacio(cliente):
    r = cliente.get("/api/estado")
    assert r.status_code == 200
    assert r.json()["proyectos"] == [] and r.json()["cola"] == []


def test_estado_con_proyecto(cliente, proyecto):
    (p,) = cliente.get("/api/estado").json()["proyectos"]
    assert p["id"] == proyecto.id and p["momentos"]["propuesto"] == 1 and p["liberable"] == 1024


def test_media_range(cliente, proyecto):
    r = cliente.get(f"/media/{proyecto.id}/fuente.mp4", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100


def test_media_no_sale_de_la_carpeta(cliente, proyecto):
    assert cliente.get(f"/media/{proyecto.id}/..%2F..%2Fplantillas.json").status_code == 404
    assert cliente.get("/media/..%2F/plantillas.json").status_code == 404


def test_media_nombre_con_tildes(cliente, raiz):
    pid = id_para("Ñandú 🐊.mp4", "Ñandú 🐊.mp4|4")
    p = nuevo_proyecto(raiz, pid=pid)
    assert cliente.get(f"/media/{p.id}/fuente.mp4").status_code == 200


def test_proyecto_detalle(cliente, proyecto):
    d = cliente.get(f"/api/proyectos/{proyecto.id}").json()
    assert d["proyecto"]["momentos"][0]["id"] == "m1" and d["palabras"] == [] and d["curva"] == []


def test_momento_invalido(cliente, proyecto):
    r = cliente.patch(f"/api/proyectos/{proyecto.id}/momentos/m1", json={"inicio": 30, "fin": 20})
    assert r.status_code == 422 and "fin" in r.json()["detail"]
    r = cliente.post(f"/api/proyectos/{proyecto.id}/momentos", json={"inicio": 590, "fin": 700})
    assert r.status_code == 422


def test_crear_momento(cliente, proyecto, raiz):
    r = cliente.post(f"/api/proyectos/{proyecto.id}/momentos", json={"inicio": 100, "fin": 120})
    assert r.status_code == 200
    m = [m for m in cargar(raiz, proyecto.id).momentos if m.inicio == 100][0]
    assert m.estado == "aprobado" and m.editado and m.titulo


def test_editar_titulo_marca_editado(cliente, proyecto, raiz):
    cliente.patch(f"/api/proyectos/{proyecto.id}/momentos/m1", json={"titulo": "Nuevo"})
    m = cargar(raiz, proyecto.id).momentos[0]
    assert m.titulo == "Nuevo" and m.editado


def test_aprobar_no_marca_editado(cliente, proyecto, raiz):
    cliente.patch(f"/api/proyectos/{proyecto.id}/momentos/m1", json={"estado": "aprobado"})
    m = cargar(raiz, proyecto.id).momentos[0]
    assert m.estado == "aprobado" and not m.editado


def test_subido_por_plataforma(cliente, proyecto, raiz):
    cliente.patch(f"/api/proyectos/{proyecto.id}/momentos/m1", json={"subido": {"tiktok": True}})
    assert cargar(raiz, proyecto.id).momentos[0].subido == {"tiktok": True, "reels": False, "shorts": False}


def test_ocupado_409(cliente, proyecto, raiz):
    p = cargar(raiz, proyecto.id)
    p.estado = "renderizando"
    guardar(raiz, p)
    assert cliente.patch(f"/api/proyectos/{proyecto.id}/momentos/m1", json={"titulo": "x"}).status_code == 409


def test_cambiar_idioma_reencola(cliente, proyecto, raiz, cola):
    (carpeta(raiz, proyecto.id) / "transcripcion.json").write_text("[]", encoding="utf-8")
    r = cliente.patch(f"/api/proyectos/{proyecto.id}/opciones", json={"idioma": "en"})
    assert r.status_code == 200
    assert not (carpeta(raiz, proyecto.id) / "transcripcion.json").exists()
    assert [(t["tipo"], t["pid"]) for t in cola.estado()] == [("procesar", proyecto.id)]


def test_props(cliente, proyecto):
    props = cliente.get(f"/api/proyectos/{proyecto.id}/props/m1").json()
    assert props["video"].endswith(f"/media/{proyecto.id}/fuente.mp4") and props["inicio"] == 10


def test_renderizar_encola(cliente, proyecto, cola):
    cliente.post(f"/api/proyectos/{proyecto.id}/renderizar")
    assert [(t["tipo"], t["pid"]) for t in cola.estado()] == [("render", proyecto.id)]


def test_liberar_409(cliente, proyecto, raiz):
    p = cargar(raiz, proyecto.id)
    p.momentos[0].estado = "aprobado"
    guardar(raiz, p)
    r = cliente.post(f"/api/proyectos/{proyecto.id}/liberar")
    assert r.status_code == 409 and "sin renderizar" in r.json()["detail"]


def test_importar_encola(cliente, cola, tmp_path):
    cliente.post("/api/importar", json={"rutas": [str(tmp_path / "a.mp4")]})
    assert [t["tipo"] for t in cola.estado()] == ["importar"]


def test_ajustes(cliente):
    aj = cliente.get("/api/ajustes").json()
    aj["tipo"] = "truco"
    assert cliente.put("/api/ajustes", json=aj).status_code == 200
    assert cliente.get("/api/ajustes").json()["tipo"] == "truco"


def test_plantillas_invalidas(cliente):
    assert cliente.put("/api/plantillas", json={"cta": "x"}).status_code == 422
    pl = cliente.get("/api/plantillas").json()
    assert cliente.put("/api/plantillas", json=pl).status_code == 200


def test_publicar_vacio(cliente, proyecto):
    d = cliente.get("/api/publicar").json()
    assert d["clips"] == [] and set(d["franjas"]) == {"tiktok", "reels", "shorts"}


def test_reintentar_tras_error(cliente, proyecto, raiz, cola):
    p = cargar(raiz, proyecto.id)
    p.estado, p.error = "error", "algo falló"
    guardar(raiz, p)
    assert cliente.post(f"/api/proyectos/{proyecto.id}/reintentar").status_code == 200
    q = cargar(raiz, proyecto.id)
    assert q.estado == "en_cola" and q.error is None
    assert [(t["tipo"], t["pid"]) for t in cola.estado()] == [("procesar", proyecto.id)]


def test_reintentar_sin_video_pide_reimportar(cliente, proyecto, raiz, cola):
    p = cargar(raiz, proyecto.id)
    p.estado = "error"
    guardar(raiz, p)
    (carpeta(raiz, p.id) / p.fuente).unlink()
    r = cliente.post(f"/api/proyectos/{proyecto.id}/reintentar")
    assert r.status_code == 409 and "arrastr" in r.json()["detail"]
    assert cola.estado() == []


def test_subir_video_ilegible_no_encola(cliente, cola, monkeypatch):
    import clipper

    def no_se_lee(ruta):
        raise SystemExit("No se puede leer")

    monkeypatch.setattr(clipper, "analizar_archivo", no_se_lee)
    r = cliente.post("/api/subir", files={"archivos": ("roto.mp4", b"basura", "video/mp4")})
    assert r.status_code == 200 and cola.estado() == []


def test_aprobar_no_revalida_tiempos(cliente, proyecto, raiz):
    """Aprobar o retitular no debe fallar por unos tiempos que el usuario no ha tocado."""
    p = cargar(raiz, proyecto.id)
    p.momentos[0].fin = p.duracion + 0.3
    guardar(raiz, p)
    assert cliente.patch(f"/api/proyectos/{proyecto.id}/momentos/m1", json={"estado": "aprobado"}).status_code == 200
