export type Palabra = { i: number; f: number; t: string }; // inicio, fin (s), texto

// Cómo se pasa el vídeo horizontal a vertical (igual que el antiguo filtro_vertical de clipper.py)
//   zoom:    juego grande en el centro, fondo difuminado
//   blur:    juego entero sin recortar (contain), fondo difuminado. Con vídeos verticales llena la pantalla
//   recorte: pantalla completa, se pierden los laterales
//   base:    el vídeo ya viene compuesto en vertical (comparativas, --voz): se pone tal cual
export type Modo = "zoom" | "blur" | "recorte" | "base";

export type ClipProps = {
  video: string; // URL http(s) o ruta dentro de public/, p. ej. "_tmp/clip.mp4"
  inicio: number; // segundo de la fuente donde empieza el clip
  fin: number; // segundo de la fuente donde acaba
  modo: Modo;
  centro: number; // 0 = izquierda, 1 = derecha (al recortar)
  fuenteAncho: number;
  fuenteAlto: number;
  duracion: number; // segundos (fin - inicio)
  fps: number;
  titulo: string | null; // gancho superior
  palabras: Palabra[]; // subtítulos palabra a palabra
  zoomEn: number | null; // segundo del momento clave (zoom automático)
  etiquetas: { texto: string; y: number }[]; // comparativas: "GTA V" / "GTA VI"
  encuesta: { a: string; b: string } | null; // serie "Tú decides"
  cta: string | null; // llamada final ("Sígueme para más")
  tituloY: number;
  subsY: number;
};

export const EJEMPLO: ClipProps = {
  video: "_tmp/prueba.mp4",
  inicio: 5,
  fin: 15,
  modo: "zoom",
  centro: 0.5,
  fuenteAncho: 1920,
  fuenteAlto: 1080,
  duracion: 10,
  fps: 60,
  titulo: "Cocodrilos en GTA 6 😳",
  palabras: [
    { i: 0.0, f: 0.3, t: "Mirad" },
    { i: 0.3, f: 0.5, t: "lo" },
    { i: 0.5, f: 0.64, t: "que" },
    { i: 0.64, f: 0.9, t: "pasa" },
    { i: 0.9, f: 1.0, t: "si" },
    { i: 1.0, f: 1.56, t: "conduces" },
    { i: 5.48, f: 5.8, t: "pero" },
    { i: 5.8, f: 5.95, t: "los" },
    { i: 5.95, f: 6.66, t: "cocodrilos" },
    { i: 6.66, f: 7.01, t: "sí." },
  ],
  zoomEn: 6,
  etiquetas: [],
  encuesta: null,
  cta: "Sígueme para más GTA 6",
  tituloY: 330,
  subsY: 1500,
};
