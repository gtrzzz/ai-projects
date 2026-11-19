# Clipper: partidas de PS5 a TikTok, Reels y Shorts

Metes tus partidas o clips en `entrada`, haces doble clic en **`procesar.bat`** y en `salida` tienes
vídeos verticales 1080x1920 listos para subir:

- **Partidas largas** (más de 2,5 min): busca solo los **mejores momentos** y crea un clip por cada uno.
- **Clips cortos** (los del botón Crear de la PS5): los convierte enteros.

Cada vídeo sale editado con **Remotion**: gancho arriba, subtítulos palabra a palabra con la palabra activa
en amarillo, emojis automáticos según lo que dices (💰 🚔 🐊 💥…), zoom con sacudida en el momento clave,
barra de progreso y "Sígueme para más" al final.

## Panel visual (recomendado)

Doble clic en **`panel.bat`**: se abre el panel en tu navegador (deja abierta la ventana negra mientras lo usas).
Todo funciona en tu PC, sin internet salvo la fuente de los textos.

1. **Añadir vídeos.** Conecta el USB de la PS5 y pulsa **Importar** en el aviso que sale. También puedes
   arrastrar vídeos al panel (p. ej. de otros creadores) o meterlos en la carpeta `entrada`: se importan solos.
   Cada vídeo se transcribe y se analiza sin que tengas que hacer nada.
2. **Revisar antes de renderizar.** Entra en el vídeo. Cada momento se ve ya con el diseño final (gancho,
   subtítulos, emojis, zoom) **sin esperar al render**. Puedes:
   - cambiar el título (🎲 para otro gancho), mover inicio y fin (±1 s o arrastrando los bordes en la línea de
     tiempo), quitar el zoom o moverlo arrastrando el ◆;
   - crear un momento nuevo arrastrando sobre una zona vacía de la línea de tiempo;
   - elegir cómo se buscan los momentos (automático, vídeo entero o los marco yo), el número de clips
     (con *exacto* llega a ese número aunque algunos sean flojos), el formato y el idioma de la voz;
   - aprobar con **A**, descartar con **D**, pasar de uno a otro con **J**/**K** y reproducir con **Espacio**.
3. **Renderizar aprobados.** Solo se renderiza lo aprobado, en segundo plano. Si luego cambias un clip ya
   renderizado, al volver a pulsar se rehace solo ese.
4. **Publicar.** Para cada clip: botones para copiar el texto de TikTok, Reels y Shorts, la mejor hora
   sugerida y casillas de *Subido*. Los mp4 están en `salida/<vídeo>/`.
5. **Liberar espacio.** Cuando tengas los clips, el botón 🧹 del vídeo borra el original y el preparado
   (los clips se quedan). Ese vídeo ya no se podrá editar salvo que lo vuelvas a importar.

En **⚙ Ajustes** cambias los valores por defecto, las horas sugeridas, el zoom automático y los textos
(ganchos, hashtags, "Sígueme…") sin tocar archivos.

`procesar.bat` y los comandos de abajo siguen funcionando igual que antes.

## 1. Instalación (una vez)

Doble clic en **`instalar.bat`**. Necesita Python 3.11+, Node.js 18+ y ffmpeg (ya los tienes).
La primera vez que se generen subtítulos se descarga el modelo de Whisper (~1,6 GB).
**Si ya lo tenías instalado, vuelve a ejecutar `instalar.bat`** para añadir el panel.

Opcional: para la IA local gratuita (correcciones escritas con tus palabras), sigue el apartado
**7. IA local**.

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

## 7. IA local (gratis, sin cuentas)

Esto deja el PC preparado para la función de **correcciones escritas**: verás un clip, escribirás algo como
*"empieza 3 segundos antes y quítale el zoom"* y la app lo convertirá en cambios concretos (inicio, fin, zoom,
título, estilo) y volverá a renderizar. **Esa función todavía no está hecha**: este apartado solo prepara la IA
para cuando esté.

Todo funciona en tu PC: sin pagar, sin cuentas y sin internet una vez descargado el modelo.
La IA **no ve el vídeo**: trabaja con lo que la app ya sabe del clip (tiempos, transcripción, puntuaciones).

### Por qué este montaje

Con una **RTX 5070 (12 GB de VRAM)** y 32 GB de RAM, lo que limita es la VRAM, porque varias cosas usan la gráfica:

| Qué | VRAM aproximada |
|---|---|
| Whisper `large-v3-turbo` (subtítulos) | 2-3 GB |
| IA `qwen3:8b` (correcciones) | 5-6 GB |
| Renderizado (NVENC + Chrome de Remotion) | <1 GB |

Cabe todo a la vez con margen. Se usa **Ollama** porque es gratis, se instala con un clic, usa la gráfica
NVIDIA sin configurar nada y deja un servicio en segundo plano al que la app puede llamar.

### 7.1 Driver de NVIDIA

1. Abre la **app de NVIDIA** → Controladores → instala el último (Game Ready o Studio, cualquiera vale).
   Las RTX 50 necesitan un driver reciente.
2. Comprueba en una terminal (tecla Windows → escribe `terminal` → Enter):

   ```bash
   nvidia-smi
   ```

   Debe salir **RTX 5070** y, arriba a la derecha, **CUDA Version 12.8** o mayor.

### 7.2 Instalar Ollama

1. Descarga **OllamaSetup.exe** de [ollama.com/download](https://ollama.com/download) e instálalo.
2. Se queda como icono de llama en la bandeja del sistema (junto al reloj) y arranca solo con Windows.
3. Comprueba en una terminal **nueva**:

   ```bash
   ollama --version
   ```

**Opcional: guardar los modelos en otro disco** (por defecto van a `C:\Users\<tú>\.ollama`):

1. Tecla Windows → escribe `variables de entorno` → **Editar las variables de entorno de tu cuenta**.
2. **Nueva…** → Nombre: `OLLAMA_MODELS` · Valor: por ejemplo `D:\ollama\modelos`.
3. Cierra Ollama (clic derecho en el icono → Quit) y vuelve a abrirlo.

### 7.3 Descargar el modelo

```bash
ollama pull qwen3:8b
```

Son unos 5 GB. Se elige **Qwen3 8B** porque entiende bien el español, sigue instrucciones con precisión y es rápido.
Además, Ollama puede obligarle a responder en un formato fijo, así la app recibe siempre cambios válidos.

| Modelo | Tamaño | Cuándo usarlo |
|---|---|---|
| `qwen3:8b` (recomendado) | ~5 GB | Lo normal: rápido y cabe junto a Whisper |
| `qwen3:14b` | ~9 GB | Si el 8b entiende mal tus correcciones. Más lento y justo de VRAM con Whisper activo |
| `qwen3:4b` | ~2,5 GB | Si quieres ir aún más rápido o el PC va justo |

Prueba que responde (escribe `/bye` para salir):

```bash
ollama run qwen3:8b "Responde solo con un número: ¿cuántos segundos son 1:15?"
```

### 7.4 Comprobar que la app podrá usarlo

La app hablará con Ollama en `http://localhost:11434`. Comprueba que el servicio está activo:

```bash
curl.exe http://localhost:11434/api/tags
```

Debe salir un texto que incluya `qwen3:8b`.

### 7.5 Que la IA no robe gráfica al renderizar

Ollama mantiene el modelo cargado en la VRAM 5 minutos después de usarlo. Para ver qué hay cargado y liberarlo:

```bash
ollama ps
```

```bash
ollama stop qwen3:8b
```

En `ollama ps`, la columna **PROCESSOR** debe decir **100% GPU**. Si dice CPU, va mucho más lento:
actualiza el driver (7.1) y Ollama, y reinicia el PC.

### Problemas típicos

- **`ollama` no se reconoce como comando**: cierra y abre la terminal; si sigue, reinicia el PC.
- **Responde muy lento**: mira `ollama ps` (debe ser GPU) y cierra juegos u otras apps que usen la gráfica.
- **Se queda sin VRAM con Whisper a la vez**: usa `qwen3:4b` o no transcribas mientras corriges.
