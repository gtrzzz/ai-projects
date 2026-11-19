import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Página del panel. `npm run panel:build` la deja en panel-dist/, que sirve panel/servidor.py.
const servidor = "http://127.0.0.1:8765";

export default defineConfig({
  root: "panel",
  base: "/",
  plugins: [react()],
  build: { outDir: "../panel-dist", emptyOutDir: true, chunkSizeWarningLimit: 4000 },
  server: { port: 5173, proxy: { "/api": servidor, "/media": servidor } },
});
