// Llamadas al servidor del panel (panel/servidor.py). Todo es local: http://127.0.0.1:8765
import { useEffect, useRef, useState } from "react";
import type { ClipProps } from "../src/tipos";

export type EstadoMomento = "propuesto" | "aprobado" | "descartado" | "renderizado";
export type Plataforma = "tiktok" | "reels" | "shorts";
export const PLATAFORMAS: Plataforma[] = ["tiktok", "reels", "shorts"];

export type Momento = {
  id: string;
  inicio: number;
  fin: number;
  titulo: string;
  zoom: "auto" | "no" | "fijo";
  zoom_en: number | null;
  zoom_auto: number | null;
  estado: EstadoMomento;
  editado: boolean;
  salida: string | null;
  huella: string | null;
  subido: Record<Plataforma, boolean>;
  puntuacion: number | null;
  motivos: Record<string, number>;
};

export type Opciones = {
  modo_momentos: "entero" | "auto" | "manual" | "auto_ia";
  clips: number | null;
  exacto: boolean;
  duracion_clip: number;
  duracion_max: number;
  tipo: string;
  formato: "zoom" | "blur" | "recorte";
  centro: number;
  idioma: string;
  opcion_a: string | null;
  opcion_b: string | null;
};

export type Proyecto = {
  id: string;
  nombre: string;
  duracion: number;
  ancho: number;
  alto: number;
  fps: number;
  hdr: boolean;
  tiene_audio: boolean;
  estado: string;
  progreso: number;
  error: string | null;
  opciones: Opciones;
  momentos: Momento[];
  preparado: string | null;
  fuente: string;
};

export type Resumen = {
  id: string;
  nombre: string;
  duracion: number;
  estado: string;
  progreso: number;
  error: string | null;
  momentos: Record<EstadoMomento, number>;
  liberable: number;
  miniatura: string | null;
};

export type Estado = {
  proyectos: Resumen[];
  usb: { nuevos: string[] };
  entrada: { nuevos: string[] };
  cola: { tipo: string; pid: string; estado: string }[];
};

export type Detalle = { proyecto: Proyecto; palabras: [number, number, string][]; curva: number[]; liberable: number };

export type ClipPublicar = {
  pid: string;
  mid: string;
  nombre: string;
  titulo: string;
  duracion: number;
  video: string;
  textos: Record<Plataforma | "transcripcion" | "aviso", string>;
  subido: Record<Plataforma, boolean>;
};

export type Ajustes = Record<string, unknown> & { franjas: Record<Plataforma, [string, string][]> };
export type Plantillas = {
  hashtags_base: string[];
  cta: string;
  tipos: Record<string, { ganchos: string[]; pregunta: string; hashtags: string[]; descripcion_yt: string }>;
};

async function pedir<T>(metodo: string, ruta: string, cuerpo?: unknown): Promise<T> {
  const r = await fetch(ruta, {
    method: metodo,
    headers: cuerpo === undefined ? undefined : { "Content-Type": "application/json" },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });
  if (!r.ok) {
    let mensaje = `${r.status}`;
    try {
      mensaje = (await r.json()).detail ?? mensaje;
    } catch {
      /* sin cuerpo */
    }
    throw new Error(mensaje);
  }
  return r.json() as Promise<T>;
}

export const api = {
  estado: () => pedir<Estado>("GET", "/api/estado"),
  importar: (rutas: string[]) => pedir("POST", "/api/importar", { rutas }),
  proyecto: (id: string) => pedir<Detalle>("GET", `/api/proyectos/${id}`),
  opciones: (id: string, cambios: Partial<Opciones>) => pedir<Proyecto>("PATCH", `/api/proyectos/${id}/opciones`, cambios),
  proponer: (id: string) => pedir<Proyecto>("POST", `/api/proyectos/${id}/proponer`),
  crearMomento: (id: string, inicio: number, fin: number) =>
    pedir<Momento>("POST", `/api/proyectos/${id}/momentos`, { inicio, fin }),
  momento: (id: string, mid: string, cambios: Partial<Momento>) =>
    pedir<Momento>("PATCH", `/api/proyectos/${id}/momentos/${mid}`, cambios),
  props: (id: string, mid: string) => pedir<ClipProps>("GET", `/api/proyectos/${id}/props/${mid}`),
  renderizar: (id: string) => pedir("POST", `/api/proyectos/${id}/renderizar`),
  liberar: (id: string) => pedir<{ liberado: number }>("POST", `/api/proyectos/${id}/liberar`),
  publicar: () => pedir<{ clips: ClipPublicar[]; franjas: Record<Plataforma, [string, string]> }>("GET", "/api/publicar"),
  ajustes: () => pedir<Ajustes>("GET", "/api/ajustes"),
  guardarAjustes: (a: Ajustes) => pedir<Ajustes>("PUT", "/api/ajustes", a),
  plantillas: () => pedir<Plantillas>("GET", "/api/plantillas"),
  guardarPlantillas: (p: Plantillas) => pedir<Plantillas>("PUT", "/api/plantillas", p),
};

// Sube vídeos desde el navegador con progreso (0..1)
export function subir(archivos: File[], alProgresar: (p: number) => void): Promise<void> {
  return new Promise((ok, mal) => {
    const datos = new FormData();
    archivos.forEach((a) => datos.append("archivos", a));
    const x = new XMLHttpRequest();
    x.open("POST", "/api/subir");
    x.upload.onprogress = (e) => e.lengthComputable && alProgresar(e.loaded / e.total);
    x.onload = () => (x.status < 300 ? ok() : mal(new Error(x.responseText)));
    x.onerror = () => mal(new Error("No se pudo subir"));
    x.send(datos);
  });
}

// Consulta periódica (cada 1,5 s por defecto)
export function usarSondeo<T>(pedirDatos: () => Promise<T>, ms = 1500, deps: unknown[] = []) {
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const vivo = useRef(true);
  const recargar = async () => {
    try {
      const d = await pedirDatos();
      if (vivo.current) {
        setDatos(d);
        setError(null);
      }
    } catch (e) {
      if (vivo.current) setError((e as Error).message);
    }
  };
  useEffect(() => {
    vivo.current = true;
    recargar();
    const t = setInterval(recargar, ms);
    return () => {
      vivo.current = false;
      clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { datos, error, recargar, setDatos };
}

export const tiempo = (s: number) => {
  const t = Math.max(0, s);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const seg = (t % 60).toFixed(1).padStart(4, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${seg}` : `${m}:${seg}`;
};

export const tamaño = (bytes: number) =>
  bytes > 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(bytes / 1e6))} MB`;

export const ESTADOS: Record<string, string> = {
  importando: "Importando…",
  en_cola: "⏳ En cola",
  preparando: "Preparando vídeo…",
  transcribiendo: "Transcribiendo…",
  analizando: "Buscando momentos…",
  listo: "✅ Listo para revisar",
  renderizando: "🎬 Renderizando…",
  liberado: "🧹 Espacio liberado",
  error: "⚠️ Error",
};
