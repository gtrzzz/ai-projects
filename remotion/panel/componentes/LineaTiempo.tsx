import React, { useRef, useState } from "react";
import { Momento, tiempo } from "../api";

type Arrastre =
  | { tipo: "i" | "f"; mid: string; t: number }
  | { tipo: "nuevo"; desde: number; t: number }
  | { tipo: "zoom"; mid: string; t: number }
  | { tipo: "clic"; mid: string; t: number; x: number };

export const zoomDe = (m: Momento): number | null =>
  m.zoom === "no" ? null : m.zoom === "fijo" ? m.zoom_en : m.zoom_auto;

type Props = {
  duracion: number;
  curva: number[];
  palabras: [number, number, string][];
  momentos: Momento[];
  activo: string | null;
  vista: [number, number];
  bloqueado: boolean;
  alElegir: (mid: string, segundoEnClip: number) => void;
  alCambiar: (mid: string, cambios: Partial<Momento>) => void;
  alCrear: (inicio: number, fin: number) => void;
};

// Toda la partida: curva de puntuación, momentos (bordes arrastrables), marcador de zoom y lo que se dice
export const LineaTiempo: React.FC<Props> = (p) => {
  const caja = useRef<HTMLDivElement>(null);
  const [arr, setArr] = useState<Arrastre | null>(null);
  const [a, b] = p.vista;
  const ancho = b - a || 1;
  const pct = (t: number) => ((t - a) / ancho) * 100;
  const tDe = (clientX: number) => {
    const r = caja.current!.getBoundingClientRect();
    return Math.min(p.duracion, Math.max(0, a + ((clientX - r.left) / r.width) * ancho));
  };

  const empezar = (e: React.PointerEvent, nuevo: Arrastre) => {
    if (p.bloqueado) return;
    e.stopPropagation();
    caja.current?.setPointerCapture(e.pointerId);
    setArr(nuevo);
  };
  const mover = (e: React.PointerEvent) => arr && setArr({ ...arr, t: tDe(e.clientX) } as Arrastre);
  const soltar = (e: React.PointerEvent) => {
    if (!arr) return;
    const t = tDe(e.clientX);
    const m = "mid" in arr ? p.momentos.find((x) => x.id === arr.mid) : undefined;
    if (arr.tipo === "i" && m) p.alCambiar(m.id, { inicio: Math.min(t, m.fin - 1) });
    if (arr.tipo === "f" && m) p.alCambiar(m.id, { fin: Math.max(t, m.inicio + 1) });
    if (arr.tipo === "zoom" && m) p.alCambiar(m.id, { zoom: "fijo", zoom_en: Math.min(m.fin, Math.max(m.inicio, t)) - m.inicio });
    if (arr.tipo === "clic" && m) p.alElegir(m.id, t - m.inicio);
    if (arr.tipo === "nuevo") {
      const [i, f] = [Math.min(arr.desde, t), Math.max(arr.desde, t)];
      if (f - i >= 1) p.alCrear(i, f);
    }
    setArr(null);
  };

  // valores mostrados mientras se arrastra
  const mostrar = (m: Momento) => {
    if (arr && "mid" in arr && arr.mid === m.id) {
      if (arr.tipo === "i") return { ...m, inicio: Math.min(arr.t, m.fin - 1) };
      if (arr.tipo === "f") return { ...m, fin: Math.max(arr.t, m.inicio + 1) };
      if (arr.tipo === "zoom") return { ...m, zoom: "fijo" as const, zoom_en: arr.t - m.inicio };
    }
    return m;
  };

  const n = p.curva.length;
  const puntos = p.curva.map((v, i) => `${(((i - a) / ancho) * 1000).toFixed(1)},${(70 - v * 64).toFixed(1)}`).join(" ");
  const marcas = 6;
  return (
    <div
      ref={caja}
      className="linea"
      onPointerDown={(e) => empezar(e, { tipo: "nuevo", desde: tDe(e.clientX), t: tDe(e.clientX) })}
      onPointerMove={mover}
      onPointerUp={soltar}
      title="Arrastra en una zona vacía para crear un momento"
    >
      {n > 0 && (
        <svg viewBox="0 0 1000 70" preserveAspectRatio="none">
          <polyline points={puntos} fill="none" stroke="#ffe600" strokeWidth="1.5" vectorEffect="non-scaling-stroke" opacity="0.8" />
        </svg>
      )}
      {Array.from({ length: marcas + 1 }, (_, k) => a + (ancho * k) / marcas).map((t, k) => (
        <span key={k} className="reloj" style={{ left: `calc(${pct(t)}% + 3px)` }}>
          {tiempo(t).replace(/\.\d$/, "")}
        </span>
      ))}
      {p.palabras
        .filter(([i]) => i >= a && i <= b)
        .map(([i, , w], k) => (
          <span key={k} className="palabra" style={{ left: `${pct(i)}%` }} title={`${tiempo(i)}  «${w}»`} />
        ))}
      {p.momentos.map((m0) => {
        const m = mostrar(m0);
        if (m.fin < a || m.inicio > b) return null;
        const z = zoomDe(m);
        return (
          <React.Fragment key={m.id}>
            <div
              className={`bloque ${m.estado} ${m.id === p.activo ? "activo" : ""}`}
              style={{ left: `${pct(m.inicio)}%`, width: `${pct(m.fin) - pct(m.inicio)}%` }}
              onPointerDown={(e) => empezar(e, { tipo: "clic", mid: m.id, t: tDe(e.clientX), x: e.clientX })}
              title={`${m.titulo}\n${tiempo(m.inicio)} – ${tiempo(m.fin)}`}
            >
              <span className="asa i" onPointerDown={(e) => empezar(e, { tipo: "i", mid: m.id, t: m.inicio })} />
              {m.titulo}
              <span className="asa f" onPointerDown={(e) => empezar(e, { tipo: "f", mid: m.id, t: m.fin })} />
            </div>
            {m.id === p.activo && z !== null && (
              <span
                className="marca-zoom"
                style={{ left: `${pct(m.inicio + z)}%` }}
                title="Zoom: arrástralo para moverlo"
                onPointerDown={(e) => empezar(e, { tipo: "zoom", mid: m.id, t: m.inicio + z })}
              />
            )}
          </React.Fragment>
        );
      })}
      {arr?.tipo === "nuevo" && Math.abs(arr.t - arr.desde) > 0.2 && (
        <div
          className="seleccion"
          style={{ left: `${pct(Math.min(arr.desde, arr.t))}%`, width: `${Math.abs(pct(arr.t) - pct(arr.desde))}%` }}
        />
      )}
    </div>
  );
};
