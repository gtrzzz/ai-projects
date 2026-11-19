"""
clipper.py - Convierte capturas de PS5 en vídeos verticales listos para TikTok, Reels y Shorts.

Comandos:
  auto      <video>             Lo hace todo: si es una partida larga busca los mejores momentos y los
                                corta; si es un clip corto lo convierte entero. (Lo usa procesar.bat)
  lote      [carpeta]           Ejecuta `auto` con todos los vídeos nuevos de una carpeta (./entrada)
  vertical  <clip>              Un clip concreto -> vertical 9:16, con tus opciones
  comparar  <clipA> <clipB>     Pantalla partida arriba/abajo (p. ej. GTA V vs GTA VI)
  subs      <video>             Solo genera el .srt

Motores de edición (--motor):
  remotion  (por defecto) subtítulos palabra a palabra, emojis, zoom en el momento clave, encuestas...
  ffmpeg    más rápido y sencillo (textos fijos)

Ejecuta `python clipper.py <comando> -h` para ver todas las opciones.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")

RAIZ = Path(__file__).resolve().parent
SALIDA_POR_DEFECTO = RAIZ / "salida"
ENTRADA_POR_DEFECTO = RAIZ / "entrada"
PLANTILLAS = RAIZ / "plantillas.json"
REMOTION = RAIZ / "remotion"
REMOTION_TMP = REMOTION / "public" / "_tmp"
REGISTRO = "procesados.json"

W, H = 1080, 1920                 # formato vertical común a las tres plataformas
PANEL_H = 608                     # altura de un 16:9 escalado a 1080 de ancho
EXTENSIONES = {".mp4", ".webm", ".mov", ".mkv"}

TITULO_Y = 330                    # centro vertical del gancho superior
SUBS_Y = 1550                     # centro vertical de los subtítulos


# --------------------------------------------------------------------------- utilidades

def log(msg: str) -> None:
    print(f"[clipper] {msg}", flush=True)


def ejecutar(cmd: list[str], cwd: Path | None = None) -> None:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-4000:])
        raise SystemExit(f"{Path(cmd[0]).name} falló (código {r.returncode})")


def segundos(valor: str | None) -> float | None:
    """Acepta '75', '75.5', '1:15' o '0:01:15'."""
    if valor is None:
        return None
    total = 0.0
    for p in str(valor).split(":"):
        total = total * 60 + float(p)
    return total


def mmss(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


@dataclass
class InfoVideo:
    duracion: float
    ancho: int
    alto: int
    hdr: bool
    tiene_audio: bool
    fps: float = 60.0


def _fps_de(texto: str | None) -> float:
    """'60000/1001' -> 59.94. Sin dato válido, 60. Nunca más de 60."""
    try:
        num, _, den = str(texto).partition("/")
        valor = float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        valor = 0.0
    if valor <= 0:
        return 60.0
    return round(min(valor, 60.0), 3)


@functools.cache
def analizar_archivo(ruta: Path) -> InfoVideo:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(ruta)],
        capture_output=True, text=True, encoding="utf-8",
    )
    if r.returncode != 0:
        raise SystemExit(f"No se puede leer {ruta}")
    datos = json.loads(r.stdout)
    video = next(s for s in datos["streams"] if s["codec_type"] == "video")
    return InfoVideo(
        duracion=float(datos["format"].get("duration", 0)),
        ancho=int(video["width"]),
        alto=int(video["height"]),
        hdr=video.get("color_transfer") in ("smpte2084", "arib-std-b67"),
        tiene_audio=any(s["codec_type"] == "audio" for s in datos["streams"]),
        fps=_fps_de(video.get("avg_frame_rate") if video.get("avg_frame_rate") not in (None, "0/0")
                    else video.get("r_frame_rate")),
    )


@functools.cache
def hay_nvenc() -> bool:
    prueba = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.1",
         "-c:v", "h264_nvenc", "-f", "null", "-"],
        capture_output=True,
    )
    return prueba.returncode == 0


def codificador(intermedio: bool = False) -> list[str]:
    """NVENC (GPU) si funciona; si no, libx264. `intermedio`: más calidad porque luego se recodifica."""
    if hay_nvenc():
        cq = "15" if intermedio else "19"
        return ["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr",
                "-cq", cq, "-b:v", "14M", "-maxrate", "30M", "-bufsize", "40M",
                "-profile:v", "high", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "fast" if intermedio else "medium",
            "-crf", "14" if intermedio else "18", "-profile:v", "high", "-pix_fmt", "yuv420p"]


AUDIO_SALIDA = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
CONTENEDOR = ["-movflags", "+faststart"]


def filtro_hdr(info: InfoVideo) -> str:
    """Las capturas HDR de PS5 se ven lavadas en móvil: las pasamos a SDR."""
    if not info.hdr:
        return ""
    return ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
            "tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")


def recorte_tiempo(inicio: float | None, fin: float | None) -> list[str]:
    args = []
    if inicio:
        args += ["-ss", f"{inicio:.3f}"]
    if fin is not None:
        args += ["-t", f"{fin - (inicio or 0):.3f}"]
    return args


@functools.cache
def remotion_disponible() -> bool:
    return bool(shutil.which("node")) and (REMOTION / "node_modules" / "@remotion" / "renderer").is_dir()


def cargar_plantillas() -> dict:
    return json.loads(PLANTILLAS.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- transcripción

def _preparar_dlls_cuda() -> None:
    """En Windows, ctranslate2 necesita encontrar las DLL de cuBLAS/cuDNN instaladas por pip."""
    if os.name != "nt":
        return
    import site
    for base in site.getsitepackages():
        nvidia = Path(base) / "nvidia"
        if nvidia.is_dir():
            for bin_dir in nvidia.glob("*/bin"):
                os.add_dll_directory(str(bin_dir))
                os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]


@functools.cache
def _cargar_whisper(modelo: str, dispositivo: str):
    _preparar_dlls_cuda()
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("Falta faster-whisper. Ejecuta instalar.bat o usa --sin-subs.")
    return WhisperModel(modelo, device=dispositivo,
                        compute_type="float16" if dispositivo == "cuda" else "int8")


# Frases que Whisper "se inventa" con música o ruido (vienen de los subtítulos con los que se entrenó)
ALUCINACIONES = re.compile(
    r"amara\.org|subt[ií]tul|gracias por ver|suscr[ií]b|thanks for watching|like y comparte|www\.|\.com",
    re.IGNORECASE,
)


def transcribir(audio_de: Path, idioma: str, modelo: str, inicio: float | None = None,
                fin: float | None = None) -> list[tuple[float, float, str]]:
    """Palabras [(inicio, fin, texto)] con tiempos relativos al tramo indicado."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        ejecutar(["ffmpeg", "-y", "-v", "error", *recorte_tiempo(inicio, fin), "-i", str(audio_de),
                  "-vn", "-ac", "1", "-ar", "16000", str(wav)])
        lang = None if idioma == "auto" else idioma
        opciones = dict(language=lang, word_timestamps=True, vad_filter=True,
                        condition_on_previous_text=False)
        try:
            segmentos = list(_cargar_whisper(modelo, "cuda").transcribe(str(wav), **opciones)[0])
            log(f"Transcrito con GPU ({modelo})")
        except Exception as e:  # sin CUDA utilizable -> CPU
            log(f"GPU no disponible para Whisper ({type(e).__name__}); usando CPU con modelo 'small'")
            segmentos = list(_cargar_whisper("small", "cpu").transcribe(str(wav), **opciones)[0])

    palabras = []
    for s in segmentos:
        if s.no_speech_prob > 0.6 or s.avg_logprob < -1.0 or ALUCINACIONES.search(s.text):
            continue
        for w in (s.words or []):
            texto = w.word.strip()
            if texto:
                palabras.append((w.start, w.end, texto))
    return palabras


def recortar_palabras(palabras, ini: float, fin: float):
    return [(a - ini, b - ini, t) for a, b, t in palabras if a >= ini - 0.05 and b <= fin + 0.05]


# --------------------------------------------------------------------------- textos (motor ffmpeg)

def agrupar(palabras, max_palabras: int = 3, max_hueco: float = 0.6):
    """Agrupa palabras en bloques cortos estilo TikTok."""
    bloques, actual = [], []
    for p in palabras:
        if actual and (len(actual) >= max_palabras or p[0] - actual[-1][1] > max_hueco
                       or re.search(r"[.?!,]$", actual[-1][2])):
            bloques.append(actual)
            actual = []
        actual.append(p)
    if actual:
        bloques.append(actual)
    resultado = []
    for i, b in enumerate(bloques):
        ini, fin = b[0][0], b[-1][1]
        if i + 1 < len(bloques):
            fin = min(max(fin, ini + 0.35), bloques[i + 1][0][0])
        resultado.append((ini, fin, " ".join(w[2] for w in b)))
    return resultado


def t_ass(t: float) -> str:
    t = max(t, 0)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def t_srt(t: float) -> str:
    t = max(t, 0)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"


def escribir_srt(bloques, destino: Path) -> None:
    lineas = []
    for i, (a, b, txt) in enumerate(bloques, 1):
        lineas += [str(i), f"{t_srt(a)} --> {t_srt(b)}", txt, ""]
    destino.write_text("\n".join(lineas), encoding="utf-8")


EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]+")


def escapar_ass(texto: str) -> str:
    # libass pinta los emojis en monocromo y quedan mal: fuera del vídeo (se mantienen en el texto de publicación)
    texto = re.sub(r"\s{2,}", " ", EMOJI.sub("", texto)).strip()
    return texto.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def escribir_ass(destino: Path, titulo: str | None, bloques, etiquetas=None,
                 subs_y: int = SUBS_Y, titulo_y: int = TITULO_Y) -> None:
    cabecera = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Titulo,Arial Black,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,7,3,5,70,70,0,1
Style: Subs,Arial Black,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,8,3,5,60,60,0,1
Style: Etiqueta,Arial Black,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,0,0,3,14,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    eventos = []
    fin_total = "9:59:59.00"
    if titulo:
        eventos.append(f"Dialogue: 2,0:00:00.00,{fin_total},Titulo,,0,0,0,,"
                       f"{{\\pos({W // 2},{titulo_y})}}{escapar_ass(titulo.upper())}")
    for texto, y in etiquetas or []:
        eventos.append(f"Dialogue: 2,0:00:00.00,{fin_total},Etiqueta,,0,0,0,,"
                       f"{{\\pos(28,{y + 24})}}{escapar_ass(texto)}")
    for a, b, txt in bloques or []:
        pop = "{\\fscx75\\fscy75\\t(0,90,\\fscx100\\fscy100)}"
        eventos.append(f"Dialogue: 1,{t_ass(a)},{t_ass(b)},Subs,,0,0,0,,"
                       f"{{\\pos({W // 2},{subs_y})}}{pop}{escapar_ass(txt.upper())}")
    destino.write_text(cabecera + "\n".join(eventos) + "\n", encoding="utf-8-sig")


# --------------------------------------------------------------------------- trabajos y acabado final

@dataclass
class Trabajo:
    base: Path                      # vídeo vertical ya compuesto, sin textos
    salida: Path
    duracion: float
    titulo: str | None
    tipo: str
    palabras: list = field(default_factory=list)
    zoom_en: float | None = None
    etiquetas: list = field(default_factory=list)   # [(texto, y)]
    encuesta: tuple | None = None
    titulo_y: int = TITULO_Y
    subs_y: int = SUBS_Y
    origen: str = ""                # para el informe: "partida.mp4 12:30-12:58"
    motivos: dict = field(default_factory=dict)
    puntuacion: float | None = None
    # Remotion compone el vertical: fuente (sin componer), tramo y formato
    fuente: Path | None = None
    inicio: float = 0.0
    fin: float | None = None
    modo: str = "base"
    centro: float = 0.5
    fps: float = 60.0
    fuente_ancho: int = W
    fuente_alto: int = H
    video_url: str | None = None    # el panel sirve el vídeo por HTTP


def carpeta_base(motor: str) -> Path:
    if motor == "remotion":
        REMOTION_TMP.mkdir(parents=True, exist_ok=True)
        return REMOTION_TMP
    d = Path(tempfile.gettempdir()) / "clipper_bases"
    d.mkdir(exist_ok=True)
    return d


def nueva_base(motor: str) -> Path:
    return carpeta_base(motor) / f"{uuid.uuid4().hex[:12]}.mp4"


def finalizar(trabajos: list[Trabajo], motor: str) -> None:
    if not trabajos:
        return
    if motor == "remotion":
        _render_remotion(trabajos)
    else:
        for t in trabajos:
            _render_ffmpeg_textos(t)
    _fuente_en_tmp.cache_clear()
    for t in trabajos:
        t.base.unlink(missing_ok=True)
        if t.palabras:
            escribir_srt(agrupar(t.palabras), t.salida.with_suffix(".srt"))
        escribir_publicacion(t)
        log(f"Listo -> {t.salida}")


def _render_ffmpeg_textos(t: Trabajo) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        escribir_ass(tmp / "texto.ass", t.titulo, agrupar(t.palabras), t.etiquetas, t.subs_y, t.titulo_y)
        ejecutar(["ffmpeg", "-y", "-v", "error", "-i", str(t.base), "-vf", "ass=texto.ass",
                  "-map", "0:v", "-map", "0:a?", *codificador(), "-c:a", "copy", *CONTENEDOR, str(t.salida)],
                 cwd=tmp)


def props_remotion(t: Trabajo, cta: str | None) -> dict:
    """Las props de ClipProps (remotion/src/tipos.ts) para un trabajo."""
    fin = t.fin if t.fin is not None else t.inicio + t.duracion
    video = t.video_url or f"_tmp/{(t.fuente or t.base).name}"
    return {
        "video": video,
        "inicio": round(t.inicio, 3),
        "fin": round(fin, 3),
        "modo": t.modo,
        "centro": t.centro,
        "fuenteAncho": t.fuente_ancho,
        "fuenteAlto": t.fuente_alto,
        "duracion": round(fin - t.inicio, 3),
        "fps": t.fps,
        "titulo": t.titulo,
        "palabras": [{"i": round(a, 3), "f": round(b, 3), "t": w} for a, b, w in t.palabras],
        "zoomEn": t.zoom_en,
        "etiquetas": [{"texto": e, "y": y} for e, y in t.etiquetas],
        "encuesta": {"a": t.encuesta[0], "b": t.encuesta[1]} if t.encuesta else None,
        "cta": cta,
        "tituloY": t.titulo_y,
        "subsY": t.subs_y,
    }


PROGRESO_REMOTION = re.compile(r"\[remotion\] (\d+)/\d+ \S.* (\d+)%")


def render_remotion(lista: list[tuple[dict, Path]], al_progresar=None) -> None:
    """Renderiza [(props, salida)] con render.mjs. `al_progresar(n, pct)` recibe el avance."""
    datos = {"trabajos": [{"props": pr, "salida": str(sal)} for pr, sal in lista], "concurrencia": None}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
        ruta_json = f.name
    log(f"Remotion: renderizando {len(lista)} vídeo(s)...")
    try:
        proc = subprocess.Popen(["node", str(REMOTION / "render.mjs"), ruta_json], cwd=REMOTION,
                                stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        for linea in proc.stdout:
            sys.stdout.write(linea)
            m = PROGRESO_REMOTION.search(linea)
            if m and al_progresar:
                al_progresar(int(m.group(1)), int(m.group(2)))
        if proc.wait() != 0:
            raise SystemExit("Remotion falló (mira el error de arriba). Puedes usar --motor ffmpeg.")
    finally:
        os.unlink(ruta_json)


def cta_para(tipo: str) -> str | None:
    return cargar_plantillas().get("cta") if tipo not in ("decide",) else None


def _render_remotion(trabajos: list[Trabajo]) -> None:
    render_remotion([(props_remotion(t, cta_para(t.tipo)), t.salida) for t in trabajos])


def textos_publicacion(t: Trabajo) -> dict[str, str]:
    """Texto para pegar en cada plataforma (lo mismo que va al _publicar.txt)."""
    p = cargar_plantillas()
    tp = p["tipos"].get(t.tipo, p["tipos"]["general"])
    gancho = t.titulo or tp["ganchos"][0]
    etiquetas = tp["hashtags"] + p["hashtags_base"]
    tags = lambda n: " ".join(etiquetas[:n])  # noqa: E731
    aviso = ""
    if t.duracion > 180:
        aviso = (f"!! Dura {t.duracion:.0f}s: Reels y Shorts admiten como máximo 3 min. "
                 "Recórtalo con --inicio/--fin para esas plataformas.")
    return {
        "tiktok": f"{gancho} {tp['pregunta']}\n{tags(5)}",
        "reels": f"{gancho}\n{tp['pregunta']} 👇\n.\n{tags(8)}",
        "shorts": (f"Título (máx. 100 caracteres):\n{gancho[:90]} #Shorts\nDescripción:\n{tp['pregunta']}\n"
                   f"{tp['descripcion_yt']}\n{tags(3)}"),
        "transcripcion": " ".join(w for _, _, w in t.palabras),
        "aviso": aviso,
    }


def escribir_publicacion(t: Trabajo) -> None:
    x = textos_publicacion(t)
    aviso = f"\n{x['aviso']}\n" if x["aviso"] else ""
    texto = f"""==================== {t.salida.stem} ====================
Duración: {t.duracion:.1f}s{aviso}
{('Origen: ' + t.origen) if t.origen else ''}

----- TIKTOK -----
{x['tiktok']}

----- INSTAGRAM REELS -----
{x['reels']}

----- YOUTUBE SHORTS -----
{x['shorts']}

----- TRANSCRIPCIÓN (para revisar / reutilizar) -----
{x['transcripcion'] or '(sin voz)'}
"""
    t.salida.with_name(t.salida.stem + "_publicar.txt").write_text(texto, encoding="utf-8")


def gancho_automatico(tipo: str, semilla: str) -> str:
    """Elige un gancho de plantillas.json (variado pero estable para el mismo clip)."""
    ganchos = cargar_plantillas()["tipos"].get(tipo, {}).get("ganchos") or ["Esto en GTA 6 es una locura"]
    return ganchos[int(hashlib.md5(semilla.encode()).hexdigest(), 16) % len(ganchos)]


# --------------------------------------------------------------------------- composición vertical (ffmpeg)

def filtro_vertical(modo: str, hdr: str, centro: float) -> str:
    if modo == "recorte":   # rellena toda la pantalla, se pierden los laterales
        return (f"[0:v]{hdr}scale=-2:{H}:flags=lanczos,"
                f"crop={W}:{H}:(iw-{W})*{centro}:0,setsar=1[base]")
    escala = 1.0 if modo == "blur" else 1.45   # zoom: el juego más grande, recorta algo de los lados
    ancho_fg = int(W * escala) // 2 * 2
    return (
        f"[0:v]{hdr}split=2[bg][fg];"
        f"[bg]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,"
        f"boxblur=12:3,eq=brightness=-0.12:saturation=1.2,scale={W}:{H}:flags=bicubic[bgb];"
        f"[fg]scale={ancho_fg}:-2:flags=lanczos,crop=min(iw\\,{W}):ih:(iw-min(iw\\,{W}))*{centro}:0[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1[base]"
    )


def crear_base_vertical(entrada: Path, destino: Path, modo: str, centro: float,
                        inicio: float | None, fin: float | None,
                        voz: Path | None = None, volumen_juego: float = 0.3) -> float:
    info = analizar_archivo(entrada)
    duracion = (fin if fin is not None else info.duracion) - (inicio or 0)
    filtro = filtro_vertical(modo, filtro_hdr(info), centro) + ";[base]null[v]"
    cmd = ["ffmpeg", "-y", "-v", "error", *recorte_tiempo(inicio, fin), "-i", str(entrada)]
    if voz:
        cmd += ["-i", str(voz)]
        if info.tiene_audio:
            filtro += (f";[0:a]volume={volumen_juego}[ja];[ja][1:a]amix=inputs=2:duration=first:normalize=0[a]")
        else:
            filtro += ";[1:a]anull[a]"
        audio = ["-map", "[a]"]
    else:
        audio = ["-map", "0:a?"]
    cmd += ["-filter_complex", filtro, "-map", "[v]", *audio, *codificador(intermedio=True),
            *AUDIO_SALIDA, *CONTENEDOR, "-t", f"{duracion:.3f}", str(destino)]
    ejecutar(cmd)
    return duracion


def crear_tramo_con_voz(entrada: Path, destino: Path, inicio: float | None, fin: float | None,
                        voz: Path, volumen_juego: float = 0.3) -> float:
    """Tramo del vídeo (en SDR, sin componer) con tu voz mezclada encima del juego."""
    info = analizar_archivo(entrada)
    duracion = (fin if fin is not None else info.duracion) - (inicio or 0)
    filtro = f"[0:v]{filtro_hdr(info)}null[v]"
    if info.tiene_audio:
        filtro += f";[0:a]volume={volumen_juego}[ja];[ja][1:a]amix=inputs=2:duration=first:normalize=0[a]"
    else:
        filtro += ";[1:a]anull[a]"
    ejecutar(["ffmpeg", "-y", "-v", "error", *recorte_tiempo(inicio, fin), "-i", str(entrada), "-i", str(voz),
              "-filter_complex", filtro, "-map", "[v]", "-map", "[a]", *codificador(intermedio=True),
              *AUDIO_SALIDA, *CONTENEDOR, "-t", f"{duracion:.3f}", str(destino)])
    return duracion


def preparar_fuente(entrada: Path, destino: Path) -> Path:
    """Vídeo listo para Remotion: si es HDR lo pasa a SDR (con keyframes cada segundo para saltar rápido).
    Si no es HDR devuelve `entrada` tal cual."""
    info = analizar_archivo(entrada)
    if not info.hdr:
        return entrada
    filtro = filtro_hdr(info).rstrip(",")
    ejecutar(["ffmpeg", "-y", "-v", "error", "-i", str(entrada), "-vf", filtro, "-map", "0:v", "-map", "0:a?",
              *codificador(intermedio=True), "-g", str(round(info.fps)), *AUDIO_SALIDA, *CONTENEDOR,
              str(destino)])
    return destino


@functools.cache
def _fuente_en_tmp(entrada: Path) -> Path:
    """La fuente (preparada) dentro de remotion/public/_tmp, una vez por vídeo."""
    destino = nueva_base("remotion")
    if preparar_fuente(entrada, destino) == entrada:
        try:
            os.link(entrada, destino)
        except OSError:
            shutil.copy2(entrada, destino)
    return destino


def zoom_en_pico(entrada: Path, inicio: float | None, fin: float | None, palabras, duracion: float):
    """Zoom automático solo si el momento más intenso del clip destaca de verdad."""
    try:
        import detector
        an = detector.analizar(entrada, palabras, inicio, fin)
        return detector.zoom_automatico(an, 0, duracion)
    except Exception as e:
        log(f"(sin zoom automático: {e})")
        return None


# --------------------------------------------------------------------------- comandos

def salida_para(entrada: Path, sufijo: str, carpeta: Path | None) -> Path:
    carpeta = Path(carpeta or SALIDA_POR_DEFECTO)
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / f"{entrada.stem}_{sufijo}.mp4"


def motor_de(a) -> str:
    if a.motor == "remotion" and not remotion_disponible():
        log("Remotion no está instalado: uso el motor ffmpeg (ejecuta instalar.bat)")
        return "ffmpeg"
    return a.motor


def trabajo_vertical(a, entrada: Path, salida: Path, inicio=None, fin=None, motor="remotion",
                     palabras=None, titulo=None) -> Trabajo:
    """Prepara un clip (o un tramo de una partida) para el acabado final."""
    info = analizar_archivo(entrada)
    voz = Path(a.voz).resolve() if getattr(a, "voz", None) else None
    log(f"{entrada.name} [{mmss(inicio or 0)}-{mmss(fin if fin is not None else info.duracion)}]"
        f"{' HDR' if info.hdr else ''} -> {a.modo}")
    if palabras is None:
        palabras = []
        if not a.sin_subs and (info.tiene_audio or voz):
            palabras = transcribir(voz or entrada, a.idioma, a.modelo,
                                   None if voz else inicio, None if voz else fin)
    encuesta = (a.opcion_a, a.opcion_b) if getattr(a, "opcion_a", None) and getattr(a, "opcion_b", None) else None
    comun = dict(salida=salida, titulo=titulo or a.titulo, tipo=a.tipo, palabras=palabras, encuesta=encuesta,
                 origen=f"{entrada.name} {mmss(inicio or 0)}-{mmss(fin if fin is not None else info.duracion)}")
    if motor != "remotion":
        base = nueva_base(motor)
        duracion = crear_base_vertical(entrada, base, a.modo, a.centro, inicio, fin, voz,
                                       getattr(a, "volumen_juego", 0.3))
        return Trabajo(base=base, duracion=duracion, **comun)

    # Remotion compone el vertical: solo hace falta la fuente (en SDR) y el tramo
    dims = dict(modo=a.modo, centro=a.centro, fps=info.fps, fuente_ancho=info.ancho, fuente_alto=info.alto)
    if voz:  # ffmpeg corta el tramo y mezcla tu voz; sin componer en vertical
        base = nueva_base(motor)
        duracion = crear_tramo_con_voz(entrada, base, inicio, fin, voz, getattr(a, "volumen_juego", 0.3))
        t = Trabajo(base=base, fuente=base, inicio=0.0, fin=duracion, duracion=duracion, **dims, **comun)
    else:
        fuente = _fuente_en_tmp(entrada)
        ini = inicio or 0.0
        duracion = (fin if fin is not None else info.duracion) - ini
        t = Trabajo(base=fuente, fuente=fuente, inicio=ini, fin=ini + duracion, duracion=duracion, **dims, **comun)
    t.zoom_en = zoom_en_pico(entrada, inicio, fin, palabras, duracion)
    return t


def cmd_vertical(a) -> None:
    entrada = Path(a.clip).resolve()
    motor = motor_de(a)
    salida = Path(a.salida).resolve() if a.salida else salida_para(entrada, "vertical", a.carpeta)
    t = trabajo_vertical(a, entrada, salida, segundos(a.inicio), segundos(a.fin), motor)
    finalizar([t], motor)


def cmd_comparar(a) -> None:
    ra, rb = Path(a.clip_a).resolve(), Path(a.clip_b).resolve()
    ia, ib = analizar_archivo(ra), analizar_archivo(rb)
    motor = motor_de(a)
    sa, sb = segundos(a.inicio_a) or 0, segundos(a.inicio_b) or 0
    duracion = min(ia.duracion - sa, ib.duracion - sb)
    if a.duracion:
        duracion = min(duracion, segundos(a.duracion))
    salida = Path(a.salida).resolve() if a.salida else salida_para(rb, "comparativa", a.carpeta)
    log(f"Comparativa {ra.name} vs {rb.name}, {duracion:.1f}s, audio: {a.audio}")

    # gancho arriba, panel A, panel B, subtítulos abajo
    y_a = 380
    y_b = y_a + PANEL_H + 12
    subs_y = y_b + PANEL_H + (H - (y_b + PANEL_H)) // 2 - 40

    palabras = []
    if not a.sin_subs:
        fuente, ini = (ra, sa) if a.audio == "a" else (rb, sb)
        if analizar_archivo(fuente).tiene_audio:
            palabras = transcribir(fuente, a.idioma, a.modelo, ini, ini + duracion)

    base = nueva_base(motor)
    panel = f"scale={W}:{PANEL_H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{PANEL_H},setsar=1"
    filtro = (
        f"color=c=0x0d0d0d:s={W}x{H}:r=60:d={duracion:.3f}[fondo];"
        f"[0:v]{filtro_hdr(ia)}{panel}[pa];"
        f"[1:v]{filtro_hdr(ib)}{panel}[pb];"
        f"[fondo][pa]overlay=0:{y_a}:shortest=1[t1];"
        f"[t1][pb]overlay=0:{y_b}:shortest=1[v]"
    )
    if a.audio == "mezcla" and ia.tiene_audio and ib.tiene_audio:
        filtro += ";[0:a][1:a]amix=inputs=2:duration=shortest:normalize=0[a]"
        mapa = ["-map", "[a]"]
    else:
        mapa = ["-map", "0:a?" if a.audio == "a" else "1:a?"]
    ejecutar(["ffmpeg", "-y", "-v", "error",
              "-ss", f"{sa:.3f}", "-t", f"{duracion:.3f}", "-i", str(ra),
              "-ss", f"{sb:.3f}", "-t", f"{duracion:.3f}", "-i", str(rb),
              "-filter_complex", filtro, "-map", "[v]", *mapa,
              *codificador(intermedio=True), *AUDIO_SALIDA, *CONTENEDOR, "-t", f"{duracion:.3f}", str(base)])

    t = Trabajo(base=base, salida=salida, duracion=duracion, titulo=a.titulo, tipo="comparativa",
                palabras=palabras, etiquetas=[(a.etiqueta_a, y_a), (a.etiqueta_b, y_b)],
                titulo_y=190, subs_y=subs_y, origen=f"{ra.name} vs {rb.name}",
                fuente=base, inicio=0.0, fin=duracion, modo="base")
    finalizar([t], motor)


def procesar_auto(a, entrada: Path, motor: str) -> list[Trabajo]:
    """Partida larga -> mejores momentos. Clip corto -> entero."""
    import detector
    info = analizar_archivo(entrada)
    if info.duracion <= a.umbral_largo:
        salida = salida_para(entrada, "vertical", a.carpeta)
        titulo = a.titulo or gancho_automatico(a.tipo, entrada.name)
        return [trabajo_vertical(a, entrada, salida, motor=motor, titulo=titulo)]

    log(f"{entrada.name}: partida de {mmss(info.duracion)} -> buscando los mejores momentos")
    palabras = []
    if not a.sin_subs and info.tiene_audio:
        palabras = transcribir(entrada, a.idioma, a.modelo)
    log("Analizando sonido, acción y reacciones...")
    an = detector.analizar(entrada, palabras)
    segs = detector.elegir_segmentos(an, palabras, max_clips=a.max_clips,
                                     dur_obj=a.duracion_clip, dur_max=a.duracion_max)
    log(f"{len(segs)} momento(s) elegidos")

    carpeta = Path(a.carpeta or SALIDA_POR_DEFECTO) / entrada.stem
    carpeta.mkdir(parents=True, exist_ok=True)
    trabajos = []
    for n, s in enumerate(segs, 1):
        salida = carpeta / f"{entrada.stem}_momento{n:02d}.mp4"
        titulo = a.titulo or gancho_automatico(a.tipo, f"{entrada.name}{n}")
        trozo = recortar_palabras(palabras, s.inicio, s.fin)
        t = trabajo_vertical(a, entrada, salida, s.inicio, s.fin, motor, palabras=trozo, titulo=titulo)
        if motor == "remotion":
            t.zoom_en = detector.zoom_automatico(an, s.inicio, s.fin)
        t.motivos, t.puntuacion = s.motivos, s.puntuacion
        trabajos.append(t)
    return trabajos


def escribir_informe(trabajos: list[Trabajo], carpeta: Path) -> None:
    """Página para ver de un vistazo los momentos elegidos y por qué."""
    filas = []
    for t in sorted(trabajos, key=lambda x: -(x.puntuacion or 0)):
        barras = "".join(
            f'<div class="m"><span>{k}</span><i style="width:{v * 100:.0f}%"></i></div>'
            for k, v in t.motivos.items()
        )
        filas.append(f"""<article>
<video src="{html.escape(t.salida.name)}" controls preload="metadata"></video>
<div><h2>{html.escape(t.salida.stem)}</h2>
<p class="o">{html.escape(t.origen)} · {t.duracion:.0f}s · puntuación {t.puntuacion or 0:.2f}</p>
{barras}
<p>{html.escape(' '.join(w for _, _, w in t.palabras)) or '<em>(sin voz)</em>'}</p></div></article>""")
    carpeta.joinpath("informe.html").write_text(f"""<!doctype html><meta charset="utf-8">
<title>Mejores momentos</title>
<style>body{{font:15px system-ui;background:#111;color:#eee;max-width:1100px;margin:auto;padding:16px}}
article{{display:flex;gap:20px;margin:18px 0;background:#1c1c1c;padding:14px;border-radius:12px;flex-wrap:wrap}}
video{{width:240px;border-radius:8px}}h2{{margin:0 0 4px;font-size:18px}}.o{{color:#999;margin:0 0 10px}}
.m{{display:flex;align-items:center;gap:8px;margin:4px 0}}.m span{{width:70px;color:#bbb}}
.m i{{display:block;height:10px;background:#ffe600;border-radius:5px}}</style>
<h1>Mejores momentos ({len(trabajos)})</h1>{''.join(filas)}""", encoding="utf-8")


def cmd_auto(a) -> None:
    motor = motor_de(a)
    entrada = Path(a.video).resolve()
    trabajos = procesar_auto(a, entrada, motor)
    finalizar(trabajos, motor)
    if len(trabajos) > 1 or analizar_archivo(entrada).duracion > a.umbral_largo:
        escribir_informe(trabajos, trabajos[0].salida.parent)
        log(f"Informe -> {trabajos[0].salida.parent / 'informe.html'}")


def cmd_lote(a) -> None:
    carpeta = Path(a.carpeta_entrada or ENTRADA_POR_DEFECTO).resolve()
    destino = Path(a.carpeta or SALIDA_POR_DEFECTO)
    destino.mkdir(parents=True, exist_ok=True)
    registro_ruta = destino / REGISTRO
    registro = json.loads(registro_ruta.read_text(encoding="utf-8")) if registro_ruta.exists() else {}
    clave = lambda p: f"{p.name}|{p.stat().st_size}"  # noqa: E731

    videos = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in EXTENSIONES)
    pendientes = [v for v in videos if clave(v) not in registro]
    if not pendientes:
        log(f"No hay vídeos nuevos en {carpeta}")
        return
    log(f"{len(pendientes)} vídeo(s) nuevos en {carpeta}")
    motor = motor_de(a)
    for i, v in enumerate(pendientes, 1):
        log(f"=== [{i}/{len(pendientes)}] {v.name}")
        trabajos = procesar_auto(a, v.resolve(), motor)
        finalizar(trabajos, motor)
        if analizar_archivo(v.resolve()).duracion > a.umbral_largo:
            escribir_informe(trabajos, trabajos[0].salida.parent)
        registro[clave(v)] = [str(t.salida) for t in trabajos]
        registro_ruta.write_text(json.dumps(registro, indent=1, ensure_ascii=False), encoding="utf-8")


def cmd_subs(a) -> None:
    entrada = Path(a.video).resolve()
    palabras = transcribir(entrada, a.idioma, a.modelo, segundos(a.inicio), segundos(a.fin))
    destino = entrada.with_suffix(".srt")
    escribir_srt(agrupar(palabras), destino)
    log(f"Subtítulos -> {destino}")


# --------------------------------------------------------------------------- CLI

TIPOS = ["general", "momento", "truco", "comparativa", "decide", "historia"]


def opciones_comunes(p: argparse.ArgumentParser) -> None:
    p.add_argument("--titulo", help="Gancho que aparece arriba (si no, se elige uno de plantillas.json en auto/lote)")
    p.add_argument("--sin-subs", action="store_true", help="No generar subtítulos")
    p.add_argument("--idioma", default="es", help="Idioma de la voz: es, en o auto (por defecto es)")
    p.add_argument("--modelo", default="large-v3-turbo", help="Modelo de Whisper")
    p.add_argument("--carpeta", type=Path, help="Carpeta de salida (por defecto ./salida)")
    p.add_argument("--motor", choices=["remotion", "ffmpeg"], default="remotion",
                   help="remotion: animado (por defecto); ffmpeg: rápido y sencillo")


def opciones_vertical(p: argparse.ArgumentParser) -> None:
    p.add_argument("--modo", choices=["blur", "zoom", "recorte"], default="zoom",
                   help="blur: juego entero con fondo difuminado; zoom: juego más grande (por defecto); "
                        "recorte: pantalla completa, se pierden los laterales")
    p.add_argument("--centro", type=float, default=0.5,
                   help="En zoom/recorte, qué parte horizontal conservar: 0=izquierda, 0.5=centro, 1=derecha")
    p.add_argument("--voz", help="Audio con tu voz (m4a/mp3/wav) para mezclar encima del juego")
    p.add_argument("--volumen-juego", type=float, default=0.3, help="Volumen del juego al usar --voz (0-1)")
    p.add_argument("--tipo", default="momento", choices=TIPOS,
                   help="Ajusta ganchos, hashtags y la pregunta para comentarios")
    p.add_argument("--opcion-a", help="Serie 'Tú decides': texto de la opción A (muestra encuesta al final)")
    p.add_argument("--opcion-b", help="Serie 'Tú decides': texto de la opción B")
    opciones_comunes(p)


def opciones_auto(p: argparse.ArgumentParser) -> None:
    p.add_argument("--umbral-largo", type=float, default=150,
                   help="A partir de cuántos segundos un vídeo se trata como partida y se buscan momentos (150)")
    p.add_argument("--max-clips", type=int, help="Máximo de momentos por partida (por defecto ~1 cada 4 min, hasta 15)")
    p.add_argument("--duracion-clip", type=float, default=25, help="Duración objetivo de cada momento (25 s)")
    p.add_argument("--duracion-max", type=float, default=60, help="Duración máxima de cada momento (60 s)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Capturas de PS5 -> vídeos verticales para TikTok, Reels y Shorts")
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("auto", help="Partida larga -> mejores momentos; clip corto -> vertical")
    p.add_argument("video")
    opciones_vertical(p)
    opciones_auto(p)
    p.set_defaults(func=cmd_auto)

    p = sub.add_parser("lote", help="`auto` con todos los vídeos nuevos de una carpeta")
    p.add_argument("carpeta_entrada", nargs="?", help="Por defecto ./entrada")
    opciones_vertical(p)
    opciones_auto(p)
    p.set_defaults(func=cmd_lote)

    p = sub.add_parser("vertical", help="Convierte un clip (o un tramo) a vertical 9:16")
    p.add_argument("clip")
    p.add_argument("-o", "--salida", help="Archivo de salida")
    p.add_argument("--inicio", help="Segundo de inicio (75 o 1:15)")
    p.add_argument("--fin", help="Segundo de fin (90 o 1:30)")
    opciones_vertical(p)
    p.set_defaults(func=cmd_vertical)

    p = sub.add_parser("comparar", help="Pantalla partida arriba/abajo")
    p.add_argument("clip_a", help="Clip de arriba (p. ej. GTA V)")
    p.add_argument("clip_b", help="Clip de abajo (p. ej. GTA VI)")
    p.add_argument("--etiqueta-a", default="GTA V")
    p.add_argument("--etiqueta-b", default="GTA VI")
    p.add_argument("--inicio-a", help="Segundo donde empieza la acción en el clip A")
    p.add_argument("--inicio-b", help="Segundo donde empieza la acción en el clip B")
    p.add_argument("--duracion", help="Duración máxima")
    p.add_argument("--audio", choices=["a", "b", "mezcla"], default="b", help="Qué audio usar (por defecto el de B)")
    p.add_argument("-o", "--salida", help="Archivo de salida")
    opciones_comunes(p)
    p.set_defaults(func=cmd_comparar)

    p = sub.add_parser("subs", help="Solo genera el .srt de un vídeo")
    p.add_argument("video")
    p.add_argument("--inicio")
    p.add_argument("--fin")
    p.add_argument("--idioma", default="es")
    p.add_argument("--modelo", default="large-v3-turbo")
    p.set_defaults(func=cmd_subs)

    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("No se encuentra ffmpeg en el PATH.")
    a.func(a)


if __name__ == "__main__":
    main()
