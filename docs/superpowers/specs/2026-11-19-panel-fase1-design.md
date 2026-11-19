# Clipper — Fase 1: panel visual con revisión antes de renderizar

Fecha: 2026-11-19 · Estado: revisado, pendiente de aprobación

## 1. Intención

El usuario usa Clipper (este repo) para convertir vídeos en clips verticales para TikTok, Reels y Shorts.
Es para él solo, no es pública. Hoy todo va por `procesar.bat` y comandos. Quiere:

- **No tocar código ni comandos**: todo desde una interfaz visual.
- **Lo más automatizado posible.**
- **No esperar al render para descubrir que un clip está mal.** Lo que más falla es la elección de los
  momentos clave, y hoy solo lo ve al final, con todo ya renderizado.

Su día normal: juega en PS5 → copia los clips a un USB → los mete en `entrada` → espera → los ve → sube los
buenos a mano. Además de su gameplay de GTA VI, también hará clips de vídeos de otros creadores.

Esta es la **Fase 1** de cinco. Las siguientes (fuera de este documento) son:
2. estilos (fuentes propias, emojis de Apple, paletas, logo, marca de agua, animaciones, transiciones);
3. IA de visión local para elegir mejor los momentos;
4. voz en off local con idiomas, acentos y tonos;
5. cámara del streamer arriba y juego abajo.

La Fase 1 debe dejar **sitio** para todas ellas (campos y secciones previstos), pero no implementarlas.

## 2. Objetivos

1. Un **panel web local** que se abre con doble clic en `panel.bat` y sirve para todo el recorrido:
   importar → analizar → revisar y ajustar → renderizar → publicar.
2. **Vista previa instantánea y fiel**: cada momento se ve en el navegador con el diseño final (gancho,
   subtítulos, emojis, zoom, barra, CTA) **sin renderizar**, y lo que se ve es lo que sale.
3. **Editar sin volver a analizar**: transcripción y análisis se guardan; cambiar tiempos, título, zoom o
   número de clips es inmediato. Solo se vuelven a renderizar los clips que cambian.
4. **Importación automática desde el USB de la PS5**, más arrastrar y soltar cualquier vídeo (p. ej. de otros
   creadores).
5. **Opciones por vídeo** (todas opcionales, con valores por defecto en Ajustes):
   - cómo se eligen los momentos: *vídeo entero* · *automático (detector actual)* · *los marco yo*
     · *automático con IA* (visible pero desactivado: llega en la Fase 3);
   - número de clips: *automático* o *N exacto*;
   - voz en off: visible pero desactivada (llega en la Fase 4);
   - tipo (`plantillas.json`), formato vertical (`zoom`/`blur`/`recorte` + centro), opciones A/B si el tipo es
     `decide`.
6. **Arreglar el zoom "sin motivo"**: hoy se hace siempre en el pico del clip aunque sea flojo.
7. **Kit de publicación**: para cada clip renderizado, botones de copiar el texto de cada plataforma (lo que hoy
   va en `_publicar.txt`) y una hora sugerida para subirlo.
8. **Editar `plantillas.json` desde el panel** (ganchos, preguntas, hashtags, CTA) para no tocar archivos.

## 3. No objetivos (Fase 1)

- IA de visión, voz en off, correcciones escritas con IA local (Ollama queda preparado en el README, sin usar).
- Personalizar fuentes, emojis, colores, logo, marca de agua, animaciones o transiciones (Fase 2). El diseño
  visual de los clips sigue siendo el actual.
- Cámara del streamer (Fase 5).
- Subir a las plataformas automáticamente: sus APIs dejan los vídeos en privado sin auditoría. Se usa la
  programación gratuita de cada plataforma.
- Modo `comparar` en el panel: se queda en la línea de comandos.
- Acceso desde otros dispositivos, cuentas o varios usuarios.

## 4. Anti-objetivos (sería un fracaso aunque funcione)

- Que la vista previa no coincida con el vídeo renderizado.
- Que editar un título o mover un corte obligue a volver a transcribir o analizar.
- Perder trabajo al cerrar el navegador o el panel: todo se guarda en disco al momento.
- Que el panel se congele mientras transcribe o renderiza.
- Romper lo que ya funciona: `procesar.bat`, `instalar.bat` y los comandos de `clipper.py` siguen funcionando.

## 5. Restricciones

- **Uso real en Windows 11**, RTX 5070 (12 GB VRAM), 32 GB RAM. Se desarrolla en un Mac: la detección de USB,
  NVENC y CUDA no se pueden probar aquí; el usuario lo verifica en su PC y el plan debe incluir esa prueba.
- Todo local y gratis. Ningún servicio externo. El servidor escucha solo en `127.0.0.1`.
- Interfaz en español.
- Construir sobre lo que hay: Python (`clipper.py`, `detector.py`, faster-whisper), Remotion 4.0.545
  (`remotion/src/Clip.tsx`), ffmpeg.
- Las capturas de PS5 son 1080p60 y pueden ser HDR (ya se convierte con `filtro_hdr`).

## 6. Enfoques considerados

| Enfoque | Ventaja | Problema |
|---|---|---|
| **A. Panel web local** (Python sirve una página React que reutiliza `Clip.tsx` con el Player de Remotion) — **elegido por el usuario** | Vista previa idéntica al render; reutiliza todo el código; se abre en el navegador | Hay que mover la composición vertical de ffmpeg a Remotion (ver 7.3) |
| B. App de escritorio (Electron/Tauri) | Ventana propia | Mucho más trabajo de empaquetado; nada que aporte para uso personal |
| C. Interfaz Python (Gradio/Streamlit) | Lo más rápido de hacer | No permite la vista previa en directo de Remotion: habría que renderizar para ver cada cambio, que es justo el problema |

## 7. Diseño

### 7.1 Piezas

- **Servidor** (`panel/servidor.py`): FastAPI + uvicorn. Sirve la página, una API JSON y el estado en directo
  (SSE o consultas periódicas, a elección del constructor). Reutiliza las funciones de `clipper.py` y
  `detector.py` importándolas; las que hoy mezclan lógica y argumentos `argparse` se separan lo justo.
- **Cola de trabajos**: un único hilo trabajador para lo pesado (copia, preparación, transcripción, análisis,
  render), uno detrás de otro, para no pelear por la gráfica. El estado de cada trabajo se ve en el panel.
- **Página** (`panel/web/`): React + Vite + `@remotion/player` (misma versión que Remotion). Importa el
  componente `Clip` de `remotion/src`, así preview y render usan el mismo código. Se compila en
  `instalar.bat`; el servidor sirve la versión compilada.
- **`panel.bat`**: arranca el servidor y abre `http://127.0.0.1:<puerto>` en el navegador por defecto.

### 7.2 Proyecto por vídeo (lo que hace posible editar sin rehacer)

Cada vídeo importado es un **proyecto** en `proyectos/<nombre>/` con:

- `proyecto.json`: origen, duración, HDR sí/no, opciones del vídeo (objetivo 5), estado y lista de **momentos**.
- `transcripcion.json`: las palabras con tiempos (lo que hoy devuelve `transcribir`).
- `analisis.json`: las curvas por segundo del detector (`puntuacion` y `componentes`) para dibujar la línea de
  tiempo y volver a elegir momentos sin recalcular.
- el vídeo preparado para vista previa y render (7.3).

Cada **momento**: `id`, `inicio`, `fin`, `titulo`, `zoom` (*auto* · *sin zoom* · *en el segundo X*),
`estado` (*propuesto* · *aprobado* · *descartado* · *renderizado*), `salida` (ruta del mp4) y una huella de los
datos con los que se renderizó. Si la huella cambia, el clip queda como "cambiado, hay que renderizar de nuevo".
Campos reservados para fases siguientes (`voz_en_off`, `estilo`, `camara`) pueden existir vacíos.

**Relación con `entrada` y `procesar.bat`** (decisión mía): el panel copia cada vídeo importado directamente a
`proyectos/<nombre>/`, nunca a `entrada`. La carpeta `entrada` es una fuente más, igual que el USB: si el usuario
suelta ahí un vídeo con el panel abierto, el panel lo detecta y lo importa. Al importar, el panel anota el vídeo
en `salida/procesados.json` con la misma clave que usa `lote` (`nombre|tamaño`), así `procesar.bat` no lo vuelve a
procesar. Lo que se procesó antes con `procesar.bat` no aparece en el panel. `lote` no cambia.

**Vídeos de cualquier origen** (decisión mía): los vídeos de otros creadores pueden venir en vertical, con otra
resolución o a 24/30 fps. La composición respeta los fps reales del vídeo (hoy fijos a 60) y añade un formato
*original* que no recorta un vídeo que ya es vertical; ese formato se propone solo si el vídeo es vertical.
Cada proyecto tiene además un campo **idioma** (`es` · `en` · `auto`, por defecto el de Ajustes). Cambiarlo
obliga a transcribir de nuevo, y el panel avisa antes.

### 7.3 Vista previa = render

Hoy ffmpeg crea un vídeo base ya vertical por cada clip y Remotion solo pone los textos encima. Para que la vista
previa sea instantánea, **la composición vertical (`zoom`/`blur`/`recorte` + centro) pasa a hacerse en
`Clip.tsx`**, sobre el vídeo original recortado con `startFrom`/`endAt`. Ya no hace falta un base por clip.

- Al importar, ffmpeg prepara **una vez por vídeo** una versión en SDR (tonemap si es HDR) con keyframes
  frecuentes para que el navegador salte rápido por la línea de tiempo. Se usa tanto para la vista previa como
  para el render. Si el vídeo no es HDR y ya sirve, se usa el original.
- `ClipProps` crece con: origen del vídeo, `inicio`, `fin`, `modo`, `centro`. `render.mjs` sigue renderizando en
  lote como ahora.
- El comando `vertical`/`auto` de `clipper.py` con motor Remotion usa el mismo camino nuevo. El motor `ffmpeg`
  y `--voz` siguen como están (la mezcla de voz se puede seguir haciendo con ffmpeg sobre el vídeo preparado).
- El aspecto del fondo difuminado y del recorte debe quedar igual que el actual, a ojo.
- **Velocidad de render** (decidido por el usuario): acepta que el render tarde más si el resultado es mejor,
  porque corre en segundo plano tras revisar. El constructor mide el tiempo con un clip de 25 s frente al actual
  (~45 s). Si pasa del doble, el render vuelve a usar ffmpeg para la composición vertical y se añade una
  comprobación de que la vista previa y el vídeo final coinciden.

### 7.2b Espacio en disco (decidido por el usuario)

Al importar se guardan el original y, si es HDR, la versión preparada: no se borra nada automáticamente.
En **Inicio** y en cada proyecto terminado hay un botón **Liberar espacio** que borra el original y la versión
preparada, y conserva los clips renderizados, sus `.txt`/`.srt`, la transcripción y el análisis. El panel enseña
cuánto espacio se libera y avisa antes de borrar de que ese proyecto ya no se podrá editar ni volver a renderizar.
Si después se vuelve a importar el mismo vídeo, se reutilizan transcripción y análisis.

### 7.4 Cambios en la elección de momentos y el zoom

- **N exacto**: hoy `elegir_segmentos` deja de buscar cuando el pico cae por debajo del percentil 85, así que
  "máximo 10" puede dar 6. Con *N exacto* se relaja ese corte hasta llegar a N (o hasta que no quepan más sin
  solaparse; el panel avisa si da menos).
- **Volver a buscar momentos** (cambiar número o duración) usa `analisis.json`: es instantáneo. Los momentos
  que el usuario ya aprobó o editó a mano no se tocan.
- **Zoom**: solo se pone automático si el pico del clip destaca de verdad: por encima del percentil 85 de toda
  la partida **y** claramente por encima de la mediana del propio clip (umbrales a elegir por el constructor,
  ajustables en Ajustes). Si no, sin zoom. En cada momento el usuario puede quitarlo o colocarlo en otro
  segundo arrastrando un marcador.

### 7.5 Pantallas

**Inicio**
```
┌──────────────────────────────────────────────────────────────┐
│ CLIPPER                                         [⚙ Ajustes]  │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ 🔌 USB de PS5 detectado: 4 vídeos nuevos   [Importar]    │ │
│ └──────────────────────────────────────────────────────────┘ │
│ ┌ - - - - - - - - - - - - - - - - - - - - - - - - - - - - -┐ │
│   Arrastra aquí vídeos o [Elegir archivos]                   │
│ └ - - - - - - - - - - - - - - - - - - - - - - - - - - - - -┘ │
│ [miniatura] partida_1911.mp4  58:12  Analizando… 63 %        │
│ [miniatura] clip_choque.mp4    0:42  ✅ Listo para revisar   │
│ [miniatura] streamer_x.mp4    12:03  ⏳ En cola              │
│ [miniatura] partida_1811.mp4  41:30  📦 6 clips renderizados │
└──────────────────────────────────────────────────────────────┘
```
- **USB**: el servidor comprueba las unidades cada pocos segundos buscando la carpeta de capturas de la PS5
  (`PS5\CREATE\Video Clips\...`; el constructor debe confirmar la ruta real) y avisa de los vídeos que no están
  importados. Con el ajuste *importar automáticamente* activado, los copia sin preguntar.
- Al importar, el vídeo entra en la cola con las opciones por defecto y se analiza solo.

**Proyecto (revisión)**
```
┌────────────────────────────────────────────────────────────────────┐
│ ← partida_1911.mp4    Momentos: [Automático ▾]  Clips: [Auto ▾]    │
│                       Tipo: [momento ▾]  Formato: [zoom ▾]         │
│                       IA: [desactivada · Fase 3]  Voz: [· Fase 4]   │
│ ┌──────────┐  Momento 3 de 8                                       │
│ │          │  Título: [Esto solo pasa en GTA 6 💀   ] [🎲 otro]     │
│ │  vista   │  Inicio [12:31.0] [-1s][+1s]  Fin [12:55.5] [-1s][+1s]│
│ │  previa  │  Zoom: (•) auto  ( ) sin zoom  ( ) en el marcador     │
│ │   9:16   │  Lo que se dice: "madre mía, pero qué hace el camión…" │
│ │          │  [✓ Aprobar]  [✗ Descartar]                            │
│ └──────────┘                                                       │
│ ▁▂▅█▃▁▁▂▇█▅▂▁▁▁▃▆▂▁   ← puntuación de toda la partida              │
│ ░░[■1]░░░[■2]░░[■3]░░░░[■4]░░  ← momentos, arrastrar bordes        │
│ 12:20 "venga venga"  12:31 "madre mía"  ← transcripción            │
│ [+ Añadir momento: selecciona en la línea]   [Renderizar aprobados (5)] │
└────────────────────────────────────────────────────────────────────┘
```
- Con *vídeo entero* hay un solo momento con todo el vídeo. Con *los marco yo* no se proponen momentos: el
  usuario los crea en la línea de tiempo.
- Atajos de teclado para revisar rápido (aprobar, descartar, siguiente, reproducir) a elección del constructor.
- **Renderizar aprobados** manda a la cola solo los aprobados que faltan o han cambiado.

**Publicar**: lista de clips renderizados con su vídeo, botones *Copiar para TikTok / Reels / Shorts* (mismo
texto que hoy genera `escribir_publicacion`, que sigue creando también el `.txt` y el `.srt`), la hora sugerida
y una casilla *Subido*.

**Ajustes**: valores por defecto de las opciones de vídeo, carpeta de salida, importación automática del USB,
*revisar antes de renderizar* (si se desactiva, todo lo propuesto se renderiza directo), umbrales del zoom, horas
sugeridas por plataforma (editables) y editor de `plantillas.json` (ganchos, preguntas, hashtags, CTA).

### 7.6 Horas sugeridas (valores iniciales, editables)

Hora de España. Los estudios se contradicen, así que son solo un punto de partida:
TikTok 19:00–22:00 (mejor domingo por la tarde) · Reels 13:00–15:00 · Shorts 16:00–19:00 (mejor viernes).
El panel muestra la próxima franja de cada plataforma según el reloj, sin calendario ni reparto de franjas
entre clips. La casilla *Subido* va por plataforma (TikTok, Reels, Shorts). Aprender de las estadísticas del
usuario queda para más adelante.

## 8. Decidido por el usuario

- Enfoque A (panel web local).
- Todo gratis y local; nada de pago.
- IA y voz en off: opcionales por vídeo, nunca obligatorias. El detector actual se mantiene.
- Revisar antes de renderizar es el centro de esta fase.
- Las fases y su orden.
- El render puede tardar más si el resultado es mejor (7.3).
- Liberar espacio con un botón cuando los clips están hechos, nunca automático (7.2b).

## 9. Decisiones mías (revisables)

- FastAPI + React/Vite + `@remotion/player`.
- Mover la composición vertical a Remotion (7.3) para que la vista previa sea fiel.
- Un vídeo preparado por proyecto en vez de un base por clip.
- Carpeta `proyectos/` junto a `entrada`/`salida`.
- Detección de USB por sondeo de unidades.
- Las horas iniciales de 7.6.

## 10. Lo que queda al constructor

Librería de componentes y estilo visual del panel, SSE o consultas periódicas, puerto, umbrales concretos del
zoom y de *N exacto*, formato exacto del vídeo preparado, atajos de teclado y cómo se separa la lógica de
`argparse` en `clipper.py`. Debe añadir pruebas (pytest) para: elección con *N exacto*, regla del zoom, guardado y
carga de proyectos y detección de cambios por huella. El repo no tiene pruebas hoy.
