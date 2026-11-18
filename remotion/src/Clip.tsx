import React from "react";
import {
  AbsoluteFill,
  Easing,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Montserrat";
import { ClipProps, Palabra } from "./tipos";
import { emojiPara } from "./emojis";

const { fontFamily } = loadFont("normal", { weights: ["800", "900"], subsets: ["latin", "latin-ext"] });

const AMARILLO = "#FFE600";
const contorno = (px: number): React.CSSProperties => ({
  WebkitTextStroke: `${px}px #000`,
  paintOrder: "stroke fill",
  textShadow: "0 8px 0 rgba(0,0,0,0.55)",
});

// ------------------------------------------------------------------ vídeo con zoom en el momento clave

const VideoConZoom: React.FC<{ video: string; zoomEn: number | null }> = ({ video, zoomEn }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  let escala = 1;
  let sacudida = 0;
  if (zoomEn !== null) {
    const z = zoomEn * fps;
    escala = interpolate(frame, [z - 0.12 * fps, z, z + 1.1 * fps, z + 1.5 * fps], [1, 1.16, 1.16, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    });
    // pequeña sacudida de cámara justo en el impacto
    const t = frame - z;
    if (t >= 0 && t < 0.3 * fps) sacudida = Math.sin(t * 2.2) * 10 * (1 - t / (0.3 * fps));
  }
  return (
    <AbsoluteFill style={{ transform: `scale(${escala}) translate(${sacudida}px, ${sacudida * 0.6}px)` }}>
      <OffthreadVideo src={staticFile(video)} style={{ width: "100%", height: "100%" }} />
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ gancho superior

const Titulo: React.FC<{ texto: string; y: number }> = ({ texto, y }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entrada = spring({ frame, fps, config: { damping: 11, stiffness: 160 } });
  const balanceo = Math.sin(frame / (fps * 0.9)) * 1.2;
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: y,
        display: "flex",
        justifyContent: "center",
        transform: `translateY(-50%) scale(${entrada}) rotate(${-2 + balanceo}deg)`,
      }}
    >
      <div
        style={{
          maxWidth: 940,
          background: "#fff",
          color: "#111",
          fontFamily,
          fontWeight: 900,
          fontSize: 66,
          lineHeight: 1.12,
          textAlign: "center",
          textTransform: "uppercase",
          padding: "22px 36px",
          borderRadius: 28,
          boxShadow: "0 14px 0 rgba(0,0,0,0.45)",
        }}
      >
        {texto}
      </div>
    </div>
  );
};

// ------------------------------------------------------------------ subtítulos palabra a palabra

type Pagina = { i: number; f: number; palabras: Palabra[] };

function paginar(palabras: Palabra[], max = 3, hueco = 0.6): Pagina[] {
  const paginas: Pagina[] = [];
  let actual: Palabra[] = [];
  for (const p of palabras) {
    const ultima = actual[actual.length - 1];
    if (ultima && (actual.length >= max || p.i - ultima.f > hueco || /[.?!,]$/.test(ultima.t))) {
      paginas.push({ i: actual[0].i, f: ultima.f, palabras: actual });
      actual = [];
    }
    actual.push(p);
  }
  if (actual.length) paginas.push({ i: actual[0].i, f: actual[actual.length - 1].f, palabras: actual });
  // que cada página dure hasta la siguiente (sin parpadeos), con un mínimo
  return paginas.map((pg, k) => {
    const sig = paginas[k + 1];
    const fin = sig ? Math.min(Math.max(pg.f + 0.25, pg.i + 0.4), sig.i) : pg.f + 0.4;
    return { ...pg, f: fin };
  });
}

const Subtitulos: React.FC<{ palabras: Palabra[]; y: number }> = ({ palabras, y }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const paginas = React.useMemo(() => paginar(palabras), [palabras]);
  const pg = paginas.find((p) => t >= p.i && t < p.f);
  if (!pg) return null;

  const desde = frame - pg.i * fps;
  const pop = spring({ frame: desde, fps, config: { damping: 9, stiffness: 220 }, from: 0.7, to: 1 });
  const emoji = emojiPara(pg.palabras.map((p) => p.t).join(" "));
  const saltoEmoji = spring({ frame: desde - 3, fps, config: { damping: 7, stiffness: 180 } });

  return (
    <div style={{ position: "absolute", left: 40, right: 40, top: y, transform: "translateY(-50%)" }}>
      {emoji && (
        <div
          style={{
            textAlign: "center",
            fontSize: 110,
            marginBottom: 6,
            transform: `scale(${saltoEmoji}) rotate(${(1 - saltoEmoji) * -30}deg)`,
          }}
        >
          {emoji}
        </div>
      )}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: "0 34px",
          transform: `scale(${pop})`,
          fontFamily,
          fontWeight: 900,
          fontSize: 92,
          lineHeight: 1.15,
          textTransform: "uppercase",
          ...contorno(16),
        }}
      >
        {pg.palabras.map((p, k) => {
          const activa = t >= p.i && t < (pg.palabras[k + 1]?.i ?? pg.f);
          return (
            <span
              key={k}
              style={{
                color: activa ? AMARILLO : "#fff",
                display: "inline-block",
                transform: activa ? "scale(1.08) translateY(-4px)" : "none",
              }}
            >
              {p.t.replace(/[.,]$/, "")}
            </span>
          );
        })}
      </div>
    </div>
  );
};

// ------------------------------------------------------------------ comparativas, encuesta, cierre

const Etiqueta: React.FC<{ texto: string; y: number; retraso: number }> = ({ texto, y, retraso }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const x = interpolate(spring({ frame: frame - retraso, fps, config: { damping: 14 } }), [0, 1], [-400, 0]);
  return (
    <div
      style={{
        position: "absolute",
        top: y + 22,
        left: 22 + x,
        background: AMARILLO,
        color: "#111",
        fontFamily,
        fontWeight: 900,
        fontSize: 50,
        padding: "8px 22px",
        borderRadius: 14,
        boxShadow: "0 8px 0 rgba(0,0,0,0.5)",
      }}
    >
      {texto}
    </div>
  );
};

const Encuesta: React.FC<{ a: string; b: string; y: number; desde: number }> = ({ a, b, y, desde }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const f = frame - desde;
  if (f < 0) return null;
  const tarjeta = (letra: string, texto: string, color: string, retraso: number) => {
    const s = spring({ frame: f - retraso, fps, config: { damping: 12 } });
    return (
      <div
        style={{
          flex: 1,
          background: color,
          borderRadius: 26,
          padding: "22px 18px",
          color: "#fff",
          fontFamily,
          fontWeight: 900,
          textAlign: "center",
          transform: `scale(${s})`,
          boxShadow: "0 12px 0 rgba(0,0,0,0.45)",
        }}
      >
        <div style={{ fontSize: 90, lineHeight: 1 }}>{letra}</div>
        <div style={{ fontSize: 40, lineHeight: 1.15, textTransform: "uppercase" }}>{texto}</div>
      </div>
    );
  };
  const pulso = 1 + Math.sin(f / 6) * 0.04;
  return (
    <div style={{ position: "absolute", left: 50, right: 50, top: y, transform: "translateY(-50%)" }}>
      <div
        style={{
          textAlign: "center",
          color: "#fff",
          fontFamily,
          fontWeight: 900,
          fontSize: 54,
          whiteSpace: "nowrap",
          marginBottom: 22,
          transform: `scale(${pulso})`,
          ...contorno(12),
        }}
      >
        ¿QUÉ HAGO? COMENTA A O B
      </div>
      <div style={{ display: "flex", gap: 30 }}>
        {tarjeta("A", a, "#1f6bff", 0)}
        {tarjeta("B", b, "#ff2d55", 5)}
      </div>
    </div>
  );
};

const Cierre: React.FC<{ texto: string; desde: number }> = ({ texto, desde }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const f = frame - desde;
  if (f < 0) return null;
  const s = spring({ frame: f, fps, config: { damping: 10 } });
  return (
    <div
      style={{
        position: "absolute",
        bottom: 130,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        transform: `translateY(${(1 - s) * 200}px)`,
      }}
    >
      <div
        style={{
          background: "#ff2d55",
          color: "#fff",
          fontFamily,
          fontWeight: 900,
          fontSize: 50,
          padding: "18px 40px",
          borderRadius: 999,
          textTransform: "uppercase",
          boxShadow: "0 10px 0 rgba(0,0,0,0.45)",
        }}
      >
        {texto} 👉
      </div>
    </div>
  );
};

const Progreso: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        bottom: 0,
        height: 12,
        width: `${(frame / Math.max(1, durationInFrames - 1)) * 100}%`,
        background: AMARILLO,
      }}
    />
  );
};

// ------------------------------------------------------------------ composición

export const Clip: React.FC<ClipProps> = (p) => {
  const { fps } = useVideoConfig();
  const finEncuesta = p.encuesta ? Math.max(0, p.duracion - 5) * fps : Infinity;
  const finCta = p.cta && p.duracion > 8 && !p.encuesta ? (p.duracion - 1.8) * fps : Infinity;
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <VideoConZoom video={p.video} zoomEn={p.zoomEn} />
      {p.etiquetas.map((e, k) => (
        <Etiqueta key={k} texto={e.texto} y={e.y} retraso={k * 6} />
      ))}
      {p.titulo && <Titulo texto={p.titulo} y={p.tituloY} />}
      {frame < Math.min(finEncuesta, finCta) && <Subtitulos palabras={p.palabras} y={p.subsY} />}
      {p.encuesta && <Encuesta a={p.encuesta.a} b={p.encuesta.b} y={p.subsY + 40} desde={finEncuesta} />}
      {p.cta && finCta !== Infinity && <Cierre texto={p.cta} desde={finCta} />}
      <Progreso />
    </AbsoluteFill>
  );
};
