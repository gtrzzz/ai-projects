"""Servidor del panel: API JSON, vídeos (con Range) y la página compilada. Solo escucha en 127.0.0.1."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
import webbrowser
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import clipper
import detector
from panel import espacio, importar, publicar, render, trabajos
from panel.ajustes import cargar_ajustes, guardar_ajustes
from panel.proyecto import ESTADOS_MOMENTO, Momento, Opciones, cargar, carpeta, guardar, listar

HOST, PUERTO = "127.0.0.1", 8765
URL_BASE = f"http://{HOST}:{PUERTO}"
OCUPADO = trabajos.SIN_TERMINAR + ("renderizando",)
FORMATOS = ("zoom", "blur", "recorte")
MODOS = ("entero", "auto", "manual", "auto_ia")
ID_VALIDO = re.compile(r"^[a-z0-9-]+$")
DIST = clipper.REMOTION / "panel-dist"


def crear_app(raiz: Path, cola: trabajos.Cola | None = None, url_base: str = URL_BASE) -> FastAPI:
    raiz = Path(raiz)
    cerrojo = threading.RLock()  # una edición de proyecto cada vez
    if cola is None:
        cola = cola_por_defecto(raiz, url_base)
    app = FastAPI(title="Clipper")
    app.state.cola = cola

    def proyecto(pid: str):
        if not ID_VALIDO.match(pid) or not (carpeta(raiz, pid) / "proyecto.json").exists():
            raise HTTPException(404, "No existe ese proyecto")
        return cargar(raiz, pid)

    def editable(pid: str):
        p = proyecto(pid)
        if p.estado in OCUPADO:
            raise HTTPException(409, "El proyecto está ocupado (analizando o renderizando). Espera a que termine.")
        return p

    def momento(p, mid: str) -> Momento:
        for m in p.momentos:
            if m.id == mid:
                return m
        raise HTTPException(404, "No existe ese momento")

    def validar_tiempos(p, inicio: float, fin: float) -> None:
        if not (0 <= inicio < fin <= p.duracion + 0.01):
            raise HTTPException(422, f"El fin ({fin:.1f}) debe ir después del inicio ({inicio:.1f}) "
                                     f"y dentro del vídeo (0–{p.duracion:.1f} s).")
        if fin - inicio < 1:
            raise HTTPException(422, "El clip debe durar al menos 1 segundo (revisa inicio y fin).")

    def zoom_auto(pid: str, inicio: float, fin: float) -> float | None:
        an = trabajos.analisis_de(raiz, pid)
        aj = cargar_ajustes(raiz)
        return detector.zoom_automatico(an, inicio, fin, aj["zoom_percentil"], aj["zoom_factor_mediana"]) if an else None

    def resumen(p) -> dict:
        cuenta = {e: 0 for e in ESTADOS_MOMENTO}
        for m in p.momentos:
            cuenta[m.estado] = cuenta.get(m.estado, 0) + 1
        return {"id": p.id, "nombre": p.nombre, "duracion": p.duracion, "estado": p.estado,
                "progreso": p.progreso, "error": p.error, "momentos": cuenta, "creado": p.creado,
                "liberable": espacio.liberable(raiz, p), "miniatura": f"/media/{p.id}/{p.preparado or p.fuente}"
                if p.estado != "liberado" else None}

    # ------------------------------------------------------------------ estado e importación

    escaneo = {"t": 0.0, "usb": [], "entrada": []}

    def escanear() -> dict:
        if time.monotonic() - escaneo["t"] > 3:
            escaneo["usb"] = [str(r) for r in importar.pendientes(importar.buscar_ps5(importar.unidades_windows()), raiz)]
            escaneo["entrada"] = [str(r) for r in importar.pendientes(importar.buscar_entrada(raiz / "entrada"), raiz)]
            escaneo["t"] = time.monotonic()
        return escaneo

    app.state.escanear = escanear

    @app.get("/api/estado")
    def estado():
        e = escanear()
        proyectos = sorted(listar(raiz), key=lambda p: p.creado, reverse=True)
        return {"proyectos": [resumen(p) for p in proyectos], "usb": {"nuevos": e["usb"]},
                "entrada": {"nuevos": e["entrada"]}, "cola": cola.estado()}

    @app.post("/api/importar")
    def importar_rutas(datos: dict = Body(...)):
        for ruta in datos.get("rutas", []):
            cola.encolar("importar", str(ruta))
        escaneo["t"] = 0.0
        return {"ok": True}

    @app.post("/api/subir")
    def subir(archivos: list[UploadFile]):
        ids = []
        for a in archivos:
            if Path(a.filename or "").suffix.lower() not in importar.EXTENSIONES:
                raise HTTPException(422, f"{a.filename}: no es un vídeo (mp4, webm, mov o mkv).")
            p = importar.importar_subida(a.filename, a.file, a.size or 0, raiz, cargar_ajustes(raiz))
            if p.estado == "en_cola":
                cola.encolar("procesar", p.id)
            ids.append(p.id)
        return {"ids": ids}

    # ------------------------------------------------------------------ proyecto

    @app.get("/api/proyectos/{pid}")
    def detalle(pid: str):
        p = proyecto(pid)
        an = trabajos.analisis_de(raiz, pid)
        return {"proyecto": asdict(p), "palabras": trabajos.palabras_de(raiz, pid),
                "curva": [round(float(v), 3) for v in an.puntuacion] if an else [],
                "liberable": espacio.liberable(raiz, p)}

    @app.patch("/api/proyectos/{pid}/opciones")
    def opciones(pid: str, cambios: dict = Body(...)):
        with cerrojo:
            p = editable(pid)
            validos = {f.name for f in fields(Opciones)}
            if set(cambios) - validos:
                raise HTTPException(422, f"Opción desconocida: {', '.join(sorted(set(cambios) - validos))}")
            if cambios.get("formato", p.opciones.formato) not in FORMATOS:
                raise HTTPException(422, "Formato no válido")
            if cambios.get("modo_momentos", p.opciones.modo_momentos) not in MODOS:
                raise HTTPException(422, "Modo de momentos no válido")
            idioma_antes = p.opciones.idioma
            for k, v in cambios.items():
                setattr(p.opciones, k, v)
            guardar(raiz, p)
            if p.opciones.idioma != idioma_antes:  # otro idioma: hay que transcribir y analizar de nuevo
                for nombre in (trabajos.TRANSCRIPCION, trabajos.ANALISIS):
                    (carpeta(raiz, pid) / nombre).unlink(missing_ok=True)
                p.estado = "en_cola"
                guardar(raiz, p)
                cola.encolar("procesar", pid)
        return asdict(p)

    @app.post("/api/proyectos/{pid}/proponer")
    def proponer(pid: str):
        with cerrojo:
            p = editable(pid)
            p.momentos = trabajos.proponer(p, trabajos.analisis_de(raiz, pid), trabajos.palabras_de(raiz, pid),
                                           cargar_ajustes(raiz))
            guardar(raiz, p)
        return asdict(p)

    @app.post("/api/proyectos/{pid}/momentos")
    def crear_momento(pid: str, datos: dict = Body(...)):
        with cerrojo:
            p = editable(pid)
            inicio, fin = float(datos["inicio"]), float(datos["fin"])
            validar_tiempos(p, inicio, fin)
            m = Momento(id=uuid.uuid4().hex[:8], inicio=round(inicio, 2), fin=round(fin, 2),
                        titulo=clipper.gancho_automatico(p.opciones.tipo, f"{p.nombre}{inicio}"),
                        estado="aprobado", editado=True, zoom_auto=zoom_auto(pid, inicio, fin))
            p.momentos = sorted(p.momentos + [m], key=lambda x: x.inicio)
            guardar(raiz, p)
        return asdict(m)

    @app.patch("/api/proyectos/{pid}/momentos/{mid}")
    def editar_momento(pid: str, mid: str, cambios: dict = Body(...)):
        with cerrojo:
            p = editable(pid)
            m = momento(p, mid)
            permitidos = {"inicio", "fin", "titulo", "zoom", "zoom_en", "estado", "subido"}
            if set(cambios) - permitidos:
                raise HTTPException(422, f"No se puede cambiar: {', '.join(sorted(set(cambios) - permitidos))}")
            inicio, fin = float(cambios.get("inicio", m.inicio)), float(cambios.get("fin", m.fin))
            if "inicio" in cambios or "fin" in cambios:
                validar_tiempos(p, inicio, fin)
            if cambios.get("estado", m.estado) not in ESTADOS_MOMENTO:
                raise HTTPException(422, "Estado no válido")
            if cambios.get("zoom", m.zoom) not in ("auto", "no", "fijo"):
                raise HTTPException(422, "Zoom no válido")
            if (inicio, fin) != (m.inicio, m.fin):
                m.inicio, m.fin = round(inicio, 2), round(fin, 2)
                m.zoom_auto = zoom_auto(pid, m.inicio, m.fin)
                m.editado = True
            for k in ("titulo", "zoom", "zoom_en"):
                if k in cambios and cambios[k] != getattr(m, k):
                    setattr(m, k, cambios[k])
                    m.editado = True
            if "estado" in cambios:
                m.estado = cambios["estado"]
            if "subido" in cambios:
                m.subido = {**m.subido, **{k: bool(v) for k, v in cambios["subido"].items() if k in m.subido}}
            p.momentos.sort(key=lambda x: x.inicio)
            guardar(raiz, p)
        return asdict(m)

    @app.get("/api/proyectos/{pid}/props/{mid}")
    def props(pid: str, mid: str):
        p = proyecto(pid)
        m = momento(p, mid)
        t = render.trabajo_de(p, m, trabajos.palabras_de(raiz, pid), url_base)
        return clipper.props_remotion(t, clipper.cta_para(p.opciones.tipo))

    @app.post("/api/proyectos/{pid}/reintentar")
    def reintentar(pid: str):
        with cerrojo:
            p = editable(pid)
            if not (carpeta(raiz, pid) / p.fuente).exists():
                raise HTTPException(409, "Falta el vídeo de este proyecto: vuelve a arrastrarlo al panel.")
            p.estado, p.error, p.progreso = "en_cola", None, 0.0
            guardar(raiz, p)
        cola.encolar("procesar", pid)
        return {"ok": True}

    @app.post("/api/proyectos/{pid}/renderizar")
    def renderizar(pid: str):
        editable(pid)
        cola.encolar("render", pid)
        return {"ok": True}

    @app.post("/api/proyectos/{pid}/liberar")
    def liberar(pid: str):
        with cerrojo:
            editable(pid)
            try:
                return {"liberado": espacio.liberar(raiz, pid)}
            except ValueError as e:
                raise HTTPException(409, str(e))

    # ------------------------------------------------------------------ publicar

    @app.get("/api/publicar")
    def para_publicar():
        aj = cargar_ajustes(raiz)
        ahora = datetime.now()
        franjas = {k: [x.isoformat() for x in publicar.proxima_franja(k, ahora, aj["franjas"])]
                   for k in ("tiktok", "reels", "shorts")}
        clips = []
        for p in sorted(listar(raiz), key=lambda p: p.creado, reverse=True):
            palabras = None
            for m in p.momentos:
                if m.estado != "renderizado" or not m.salida or not Path(m.salida).exists():
                    continue
                palabras = palabras if palabras is not None else trabajos.palabras_de(raiz, p.id)
                clips.append({"pid": p.id, "mid": m.id, "nombre": p.nombre, "titulo": m.titulo,
                              "duracion": round(m.fin - m.inicio, 1), "video": f"/media/{p.id}/{Path(m.salida).name}",
                              "textos": publicar.textos(p, m, palabras), "subido": m.subido})
        return {"clips": clips, "franjas": franjas}

    # ------------------------------------------------------------------ ajustes y plantillas

    @app.get("/api/ajustes")
    def leer_ajustes():
        return cargar_ajustes(raiz)

    @app.put("/api/ajustes")
    def escribir_ajustes(datos: dict = Body(...)):
        guardar_ajustes(raiz, {**cargar_ajustes(raiz), **datos})
        return cargar_ajustes(raiz)

    @app.get("/api/plantillas")
    def leer_plantillas():
        return json.loads((raiz / "plantillas.json").read_text(encoding="utf-8"))

    @app.put("/api/plantillas")
    def escribir_plantillas(datos: dict = Body(...)):
        if not {"hashtags_base", "cta", "tipos"} <= set(datos) or not isinstance(datos["tipos"], dict):
            raise HTTPException(422, "Las plantillas deben tener hashtags_base, cta y tipos.")
        for nombre, t in datos["tipos"].items():
            if not {"ganchos", "pregunta", "hashtags", "descripcion_yt"} <= set(t) or not t["ganchos"]:
                raise HTTPException(422, f"Al tipo «{nombre}» le falta algún campo o no tiene ganchos.")
        ruta = raiz / "plantillas.json"
        tmp = ruta.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ruta)
        return datos

    # ------------------------------------------------------------------ ficheros

    @app.get("/media/{pid}/{archivo}")
    def media(pid: str, archivo: str):
        if not ID_VALIDO.match(pid) or Path(archivo).name != archivo or archivo.startswith("."):
            raise HTTPException(404)
        salida = raiz / cargar_ajustes(raiz).get("carpeta_salida", "salida") / pid
        for base in (carpeta(raiz, pid), salida):
            ruta = base / archivo
            if ruta.is_file():
                return FileResponse(ruta)
        raise HTTPException(404)

    if DIST.is_dir():
        app.mount("/", StaticFiles(directory=DIST, html=True), name="panel")
    else:
        @app.get("/", response_class=HTMLResponse)
        def sin_compilar():
            return "<h1>Clipper</h1><p>Falta compilar el panel: ejecuta instalar.bat.</p>"

    return app


def cola_por_defecto(raiz: Path, url_base: str) -> trabajos.Cola:
    cola: trabajos.Cola

    def hacer_importar(ruta: str) -> None:
        p = importar.importar(Path(ruta), raiz, cargar_ajustes(raiz))
        if p.estado == "en_cola":
            cola.encolar("procesar", p.id)

    cola = trabajos.Cola({
        "importar": hacer_importar,
        "procesar": lambda pid: trabajos.procesar(raiz, pid, cargar_ajustes(raiz), cola),
        "render": lambda pid: render.renderizar(raiz, pid, cargar_ajustes(raiz), url_base),
    })
    return cola


def vigilar(app: FastAPI, raiz: Path) -> None:
    """Cada 3 s: importa solo lo que aparece en `entrada`, y lo del USB si está activado en Ajustes."""
    while True:
        try:
            e = app.state.escanear()
            nuevos = list(e["entrada"])
            if cargar_ajustes(raiz).get("importar_usb_auto"):
                nuevos += e["usb"]
            for ruta in nuevos:
                app.state.cola.encolar("importar", ruta)
        except Exception as err:  # el vigilante no debe morir nunca
            clipper.log(f"(vigilante: {err})")
        time.sleep(3)


def main() -> None:
    import uvicorn

    raiz = clipper.RAIZ
    app = crear_app(raiz)
    app.state.cola.reanudar(raiz)
    app.state.cola.iniciar()
    threading.Thread(target=vigilar, args=(app, raiz), daemon=True, name="vigilante").start()
    if not os.environ.get("CLIPPER_SIN_NAVEGADOR"):
        threading.Timer(1.5, lambda: webbrowser.open(URL_BASE)).start()
    clipper.log(f"Panel en {URL_BASE} (cierra esta ventana para apagarlo)")
    uvicorn.run(app, host=HOST, port=PUERTO, log_level="warning")


if __name__ == "__main__":
    main()
