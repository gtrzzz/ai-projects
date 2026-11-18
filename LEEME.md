# Clipper: partidas de PS5 a TikTok, Reels y Shorts

Metes tus partidas o clips en `entrada`, haces doble clic en **`procesar.bat`** y en `salida` tienes
vídeos verticales 1080x1920 listos para subir:

- **Partidas largas** (más de 2,5 min): busca solo los **mejores momentos** y crea un clip por cada uno.
- **Clips cortos** (los del botón Crear de la PS5): los convierte enteros.

Cada vídeo sale editado con **Remotion**: gancho arriba, subtítulos palabra a palabra con la palabra activa
en amarillo, emojis automáticos según lo que dices (💰 🚔 🐊 💥…), zoom con sacudida en el momento clave,
barra de progreso y "Sígueme para más" al final.

## 1. Instalación (una vez)

Doble clic en **`instalar.bat`**. Necesita Python 3.11+, Node.js 18+ y ffmpeg (ya los tienes).
La primera vez que se generen subtítulos se descarga el modelo de Whisper (~1,6 GB).

## 2. Configurar la PS5

- **Ajustes → Capturas y emisiones → Capturas**: vídeo en **1080p** y **60 fps**.
- **Incluir el audio del micrófono: SÍ.** Tus reacciones son la mejor pista para el detector
  ("¡madre mía!", risas, gritos) y salen como subtítulos.
- Para grabar partidas largas: botón **Crear → Iniciar nueva grabación** (hasta 1 h). Para clips sueltos,
  **Crear → Guardar videoclip reciente** justo después de que pase algo bueno.
- El HDR no es problema: el script lo detecta y lo convierte para que no se vea lavado.

**Pasar los vídeos al PC:** app de PS en el móvil (Biblioteca de capturas) o USB en exFAT
(Galería multimedia → Copiar a USB). Mételos en `entrada`.

## 3. Cómo elige los mejores momentos

Mide tres señales en cada segundo de la partida:

| Señal | Qué detecta |
|---|---|
| **Sonido** | Picos de volumen respecto a lo normal de ese minuto: disparos, choques, explosiones, sirenas |
| **Acción** | Cuánto cambia la imagen: persecuciones y caos frente a ir andando, menús o pantallas de carga |
| **Reacción** | Tus exclamaciones, risas y gritos, transcritos con Whisper |

Cuando coinciden varias señales a la vez, el momento puntúa más. Corta cada momento sin partir frases,
con poco contexto antes (el primer segundo es lo que decide en TikTok) y más margen para el remate.
Por defecto saca ~1 clip cada 4 minutos de partida (máximo 15).

Junto a los clips se crea un **`informe.html`**: ábrelo para ver todos los momentos, su puntuación y por qué
se eligieron. Sube los que más te gusten.

Ajustes útiles (se pueden pasar a `procesar.bat`):

```bash
procesar.bat --max-clips 8 --duracion-clip 20
```

- `--max-clips N`: cuántos momentos como máximo por partida.
- `--duracion-clip S` / `--duracion-max S`: duración objetivo y máxima de cada momento (25 s / 60 s).
- `--umbral-largo S`: a partir de cuántos segundos un vídeo se trata como partida (150 s).
- `--tipo truco|momento|...`: cambia los ganchos y hashtags automáticos.
- `--motor ffmpeg`: edición sencilla y mucho más rápida (sin animaciones), por si vas con prisa.

## 4. Comandos manuales (para vídeos concretos)

Abre una terminal en esta carpeta.

**Un clip o un tramo concreto**, con tu propio gancho:

```bash
.venv\Scripts\python clipper.py vertical entrada\clip.mp4 --inicio 0:42 --fin 1:05 --titulo "Truco de dinero 💰" --tipo truco
```

**Comparativa GTA V vs GTA VI** (pantalla partida con etiquetas animadas):

```bash
.venv\Scripts\python clipper.py comparar entrada\gta5_playa.mp4 entrada\gta6_playa.mp4 --titulo "GTA 5 vs GTA 6: la playa" --inicio-a 3 --inicio-b 1.5
```

**Serie "Tú decides"** (encuesta A/B animada en los últimos 5 segundos):

```bash
.venv\Scripts\python clipper.py vertical entrada\parte1.mp4 --tipo decide --titulo "TÚ DECIDES: parte 1" --opcion-a "Robar el banco" --opcion-b "Huir a los Cayos"
```

**Tu voz encima** (grabada con el móvil). El juego baja al 30 % y los subtítulos salen de tu voz:

```bash
.venv\Scripts\python clipper.py vertical entrada\clip.mp4 --voz entrada\mi_voz.m4a --titulo "Nadie sabe esto"
```

**Una partida concreta en automático**, sin pasar por la carpeta `entrada`:

```bash
.venv\Scripts\python clipper.py auto D:\capturas\partida.mp4 --max-clips 5
```

### Formatos de vertical (`--modo`)

| Modo | Qué hace | Cuándo usarlo |
|---|---|---|
| `zoom` (por defecto) | Juego grande en el centro, fondo difuminado | Casi siempre |
| `blur` | Juego entero sin recortar | Cuando importa ver toda la pantalla (mapa, menús) |
| `recorte` | Pantalla completa, se pierden los laterales | Acción centrada en el personaje o el coche |

`--centro 0.3` mueve el recorte a la izquierda (0 = izquierda, 1 = derecha).

## 5. Personalizar

- **`plantillas.json`**: ganchos automáticos, preguntas, hashtags y el texto "Sígueme…".
- **`remotion/src/emojis.ts`**: qué palabras ponen qué emoji.
- **`remotion/src/Clip.tsx`**: el diseño (colores, tipografía, animaciones).
  Para verlo en directo mientras lo cambias: `cd remotion` y `npm run studio`.

## 6. Antes de subir

- **Revisa la transcripción** del `_publicar.txt`: Whisper falla a veces con nombres propios.
  Los diálogos del juego están en inglés: si quieres subtitularlos usa `--idioma auto`
  (Whisper no traduce al español).
- **Tiempos**: cada clip de 25 s tarda ~45 s en renderizarse con Remotion. Una partida de 1 h,
  con transcripción y unos 15 clips, tarda ~15 min.
- **Programar publicaciones**: TikTok (web → Programar), Instagram (Meta Business Suite) y
  YouTube Studio permiten programar gratis.
- **Reels y Shorts** admiten como máximo 3 minutos; el `.txt` te avisa si te pasas.
