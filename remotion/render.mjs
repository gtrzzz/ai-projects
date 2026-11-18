// Renderiza en lote: node render.mjs trabajos.json
// trabajos.json = { "concurrencia": 6, "trabajos": [ { "props": {...}, "salida": "C:/.../clip.mp4" } ] }
// Empaqueta el proyecto una sola vez y reutiliza el navegador para todos los clips.
import { bundle } from "@remotion/bundler";
import { openBrowser, renderMedia, selectComposition } from "@remotion/renderer";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const aqui = path.dirname(fileURLToPath(import.meta.url));
const { trabajos, concurrencia } = JSON.parse(readFileSync(process.argv[2], "utf8"));

const serveUrl = await bundle({
  entryPoint: path.join(aqui, "src", "index.ts"),
  publicDir: path.join(aqui, "public"),
});
const navegador = await openBrowser("chrome", { chromiumOptions: { gl: "angle" } });

try {
  for (const [n, { props, salida }] of trabajos.entries()) {
    const composition = await selectComposition({ serveUrl, id: "Clip", inputProps: props, puppeteerInstance: navegador });
    let ultimo = -1;
    const t0 = Date.now();
    await renderMedia({
      composition,
      serveUrl,
      inputProps: props,
      puppeteerInstance: navegador,
      codec: "h264",
      crf: 18,
      x264Preset: "fast",
      pixelFormat: "yuv420p",
      audioCodec: "aac",
      audioBitrate: "192k",
      concurrency: concurrencia ?? null,
      outputLocation: salida,
      onProgress: ({ progress }) => {
        const pct = Math.floor(progress * 10) * 10;
        if (pct !== ultimo) {
          ultimo = pct;
          process.stdout.write(`[remotion] ${n + 1}/${trabajos.length} ${path.basename(salida)} ${pct}%\n`);
        }
      },
    });
    console.log(`[remotion] OK ${path.basename(salida)} en ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  }
} finally {
  await navegador.close({ silent: true });
}
