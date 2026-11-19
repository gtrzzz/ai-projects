import React, { useEffect, useMemo, useRef, useState } from "react";
import { api, ESTADOS, Momento, Opciones, Plantillas, tiempo, usarSondeo } from "../api";
import { LineaTiempo, zoomDe } from "../componentes/LineaTiempo";
import { Previa, PreviaRef } from "../componentes/Previa";
import { avisar } from "../main";

const OCUPADO = ["en_cola", "importando", "preparando", "transcribiendo", "analizando", "renderizando"];
const CAMBIAN_MOMENTOS: (keyof Opciones)[] = ["modo_momentos", "clips", "exacto", "duracion_clip", "duracion_max"];

const Opcion: React.FC<{ etiqueta: string; children: React.ReactNode; ayuda?: string }> = ({ etiqueta, children, ayuda }) => (
  <label title={ayuda}>
    {etiqueta}
    {children}
  </label>
);

export const ProyectoPantalla: React.FC<{ id: string }> = ({ id }) => {
  const { datos, error, recargar } = usarSondeo(() => api.proyecto(id), 1500, [id]);
  const [activo, setActivo] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [titulo, setTitulo] = useState("");
  const [vista, setVista] = useState<"todo" | "cerca">("todo");
  const [buscarDeNuevo, setBuscarDeNuevo] = useState(false);
  const [plantillas, setPlantillas] = useState<Plantillas | null>(null);
  const previa = useRef<PreviaRef>(null);
  const esperaTitulo = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    api.plantillas().then(setPlantillas).catch(() => undefined);
  }, []);

  const p = datos?.proyecto;
  const momentos = p?.momentos ?? [];
  const m = momentos.find((x) => x.id === activo) ?? null;
  const ocupado = !!p && OCUPADO.includes(p.estado);

  // primer momento por defecto, y el título del momento activo
  useEffect(() => {
    if (!activo && momentos.length) setActivo((momentos.find((x) => x.estado !== "descartado") ?? momentos[0]).id);
    if (activo && momentos.length && !momentos.some((x) => x.id === activo)) setActivo(momentos[0].id);
  }, [momentos, activo]);
  useEffect(() => {
    if (m) setTitulo(m.titulo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m?.id]);

  const guardarMomento = async (mid: string, cambios: Partial<Momento>) => {
    try {
      await api.momento(id, mid, cambios);
      await recargar();
      setVersion((v) => v + 1);
    } catch (e) {
      avisar((e as Error).message, true);
    }
  };

  const cambiarOpciones = async (cambios: Partial<Opciones>) => {
    try {
      await api.opciones(id, cambios);
      if (CAMBIAN_MOMENTOS.some((k) => k in cambios)) setBuscarDeNuevo(true);
      if ("idioma" in cambios) avisar("Se vuelve a transcribir con el idioma nuevo…");
      await recargar();
      setVersion((v) => v + 1);
    } catch (e) {
      avisar((e as Error).message, true);
    }
  };

  const volverABuscar = async () => {
    try {
      await api.proponer(id);
      setBuscarDeNuevo(false);
      await recargar();
      setVersion((v) => v + 1);
      avisar("Momentos actualizados (los aprobados y editados se conservan)");
    } catch (e) {
      avisar((e as Error).message, true);
    }
  };

  const otroGancho = () => {
    if (!p || !m || !plantillas) return;
    const lista = plantillas.tipos[p.opciones.tipo]?.ganchos ?? [];
    if (!lista.length) return;
    const siguiente = lista[(lista.indexOf(titulo) + 1) % lista.length];
    setTitulo(siguiente);
    guardarMomento(m.id, { titulo: siguiente });
  };

  const cambiarTitulo = (texto: string) => {
    setTitulo(texto);
    clearTimeout(esperaTitulo.current);
    if (m) esperaTitulo.current = setTimeout(() => guardarMomento(m.id, { titulo: texto }), 300);
  };

  const mover = (delta: number) => {
    const visibles = momentos;
    const i = visibles.findIndex((x) => x.id === activo);
    const s = visibles[i + delta];
    if (s) setActivo(s.id);
  };

  // atajos: A aprobar, D descartar, J/K anterior/siguiente, Espacio reproducir
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || !m || ocupado) return;
      const k = e.key.toLowerCase();
      if (k === "a") guardarMomento(m.id, { estado: "aprobado" }).then(() => mover(1));
      else if (k === "d") guardarMomento(m.id, { estado: "descartado" }).then(() => mover(1));
      else if (k === "j") mover(-1);
      else if (k === "k") mover(1);
      else if (k === " ") {
        e.preventDefault();
        previa.current?.alternar();
      } else return;
    };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  });

  const rango = useMemo<[number, number]>(() => {
    if (!p) return [0, 1];
    if (vista === "cerca" && m) {
      const margen = Math.max(30, (m.fin - m.inicio) * 1.5);
      return [Math.max(0, m.inicio - margen), Math.min(p.duracion, m.fin + margen)];
    }
    return [0, p.duracion];
  }, [p, m, vista]);

  if (error && !datos) return <div className="aviso mal">{error}</div>;
  if (!p || !datos) return <p className="suave">Cargando…</p>;

  const aprobados = momentos.filter((x) => x.estado === "aprobado").length;
  const renderizables = momentos.some((x) => x.estado === "aprobado" || x.estado === "renderizado");
  const o = p.opciones;
  const dicho = m ? datos.palabras.filter(([i, f]) => i >= m.inicio - 0.05 && f <= m.fin + 0.05).map((w) => w[2]).join(" ") : "";
  const vertical = p.alto > p.ancho;

  return (
    <>
      <div className="acciones" style={{ marginBottom: 12 }}>
        <a href="#/">← Vídeos</a>
        <h2 style={{ margin: "0 8px", fontSize: 20 }}>{p.nombre}</h2>
        <span className="suave">
          {tiempo(p.duracion)} · {ESTADOS[p.estado] ?? p.estado}
          {p.hdr ? " · HDR" : ""}
        </span>
      </div>
      {p.error && (
        <div className="aviso mal">
          <span style={{ flex: 1 }}>{p.error}</span>
          {p.estado === "error" && <button onClick={async () => { await api.reintentar(id); recargar(); }}>↻ Reintentar</button>}
        </div>
      )}
      {ocupado && (
        <div className="aviso">
          {ESTADOS[p.estado]} {Math.round(p.progreso * 100)} % — la edición se activa al terminar.
        </div>
      )}

      <div className="tarjeta rejilla-opciones">
        <Opcion etiqueta="Momentos">
          <select value={o.modo_momentos} disabled={ocupado} onChange={(e) => cambiarOpciones({ modo_momentos: e.target.value as Opciones["modo_momentos"] })}>
            <option value="auto">Automático</option>
            <option value="entero">Vídeo entero</option>
            <option value="manual">Los marco yo</option>
            <option value="auto_ia" disabled>Automático con IA (Fase 3)</option>
          </select>
        </Opcion>
        <Opcion etiqueta="Nº de clips" ayuda="Vacío = automático (~1 cada 4 min)">
          <input type="number" min={1} max={50} style={{ width: 80 }} placeholder="Auto" value={o.clips ?? ""} disabled={ocupado}
            onChange={(e) => cambiarOpciones({ clips: e.target.value ? Number(e.target.value) : null })} />
        </Opcion>
        <label className="casilla" style={{ display: "flex", gap: 6, alignItems: "center" }} title="Llega a ese número aunque algunos momentos sean flojos">
          <input type="checkbox" checked={o.exacto} disabled={ocupado || !o.clips} onChange={(e) => cambiarOpciones({ exacto: e.target.checked })} />
          exacto
        </label>
        <Opcion etiqueta="Duración (s)">
          <input type="number" min={8} max={180} style={{ width: 70 }} value={o.duracion_clip} disabled={ocupado}
            onChange={(e) => cambiarOpciones({ duracion_clip: Number(e.target.value) })} />
        </Opcion>
        <Opcion etiqueta="Tipo">
          <select value={o.tipo} disabled={ocupado} onChange={(e) => cambiarOpciones({ tipo: e.target.value })}>
            {Object.keys(plantillas?.tipos ?? { [o.tipo]: 1 }).map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </Opcion>
        <Opcion etiqueta="Formato">
          <select value={o.formato} disabled={ocupado} onChange={(e) => cambiarOpciones({ formato: e.target.value as Opciones["formato"] })}>
            <option value="zoom">Zoom (juego grande)</option>
            <option value="blur">Entero (sin recortar){vertical ? " ★" : ""}</option>
            <option value="recorte">Recorte (pantalla completa)</option>
          </select>
        </Opcion>
        {o.formato !== "blur" && (
          <Opcion etiqueta={`Centro ${o.centro.toFixed(2)}`} ayuda="0 = izquierda, 1 = derecha">
            <input type="range" min={0} max={1} step={0.05} value={o.centro} disabled={ocupado}
              onChange={(e) => cambiarOpciones({ centro: Number(e.target.value) })} />
          </Opcion>
        )}
        <Opcion etiqueta="Idioma de la voz" ayuda="Cambiarlo vuelve a transcribir el vídeo">
          <select value={o.idioma} disabled={ocupado}
            onChange={(e) => window.confirm("Cambiar el idioma vuelve a transcribir y analizar el vídeo. ¿Seguir?") && cambiarOpciones({ idioma: e.target.value })}>
            <option value="es">Español</option>
            <option value="en">Inglés</option>
            <option value="auto">Automático</option>
          </select>
        </Opcion>
        {o.tipo === "decide" && (
          <>
            <Opcion etiqueta="Opción A">
              <input value={o.opcion_a ?? ""} disabled={ocupado} onChange={(e) => cambiarOpciones({ opcion_a: e.target.value })} />
            </Opcion>
            <Opcion etiqueta="Opción B">
              <input value={o.opcion_b ?? ""} disabled={ocupado} onChange={(e) => cambiarOpciones({ opcion_b: e.target.value })} />
            </Opcion>
          </>
        )}
        <Opcion etiqueta="Voz en off">
          <select disabled>
            <option>Desactivada (Fase 4)</option>
          </select>
        </Opcion>
        <button className={buscarDeNuevo ? "principal" : ""} disabled={ocupado || o.modo_momentos === "manual"} onClick={volverABuscar}
          title="Usa el análisis guardado: es instantáneo. Lo aprobado y lo editado se conserva">
          🔄 Volver a buscar momentos
        </button>
      </div>

      <div className="revision">
        {m ? <Previa ref={previa} pid={id} mid={m.id} version={version} /> : <div className="previa" />}
        <div className="editor">
          {m ? (
            <>
              <div className="momentos-lista">
                {momentos.map((x, i) => (
                  <button key={x.id} className={`e-${x.estado} ${x.id === activo ? "activo" : ""}`} onClick={() => setActivo(x.id)}>
                    {i + 1}. {tiempo(x.inicio).replace(/\.\d$/, "")}
                  </button>
                ))}
              </div>
              <div className="campo">
                <span>Título (gancho de arriba)</span>
                <div className="acciones">
                  <input style={{ flex: 1, minWidth: 220 }} value={titulo} disabled={ocupado} onChange={(e) => cambiarTitulo(e.target.value)} />
                  <button disabled={ocupado} onClick={otroGancho} title="Siguiente gancho de plantillas.json">🎲 otro</button>
                </div>
              </div>
              <div className="campo">
                <span>Tramo · dura {(m.fin - m.inicio).toFixed(1)} s</span>
                <div className="tiempos">
                  Inicio <b>{tiempo(m.inicio)}</b>
                  <button disabled={ocupado} onClick={() => guardarMomento(m.id, { inicio: Math.max(0, m.inicio - 1) })}>−1 s</button>
                  <button disabled={ocupado} onClick={() => guardarMomento(m.id, { inicio: m.inicio + 1 })}>+1 s</button>
                  <span style={{ width: 12 }} />
                  Fin <b>{tiempo(m.fin)}</b>
                  <button disabled={ocupado} onClick={() => guardarMomento(m.id, { fin: m.fin - 1 })}>−1 s</button>
                  <button disabled={ocupado} onClick={() => guardarMomento(m.id, { fin: Math.min(p.duracion, m.fin + 1) })}>+1 s</button>
                </div>
              </div>
              <div className="campo">
                <span>Zoom {zoomDe(m) !== null ? `en el segundo ${zoomDe(m)!.toFixed(1)}` : ""}</span>
                <div className="acciones">
                  {(["auto", "no", "fijo"] as const).map((z) => (
                    <label key={z} style={{ display: "flex", gap: 4, alignItems: "center" }}>
                      <input type="radio" checked={m.zoom === z} disabled={ocupado || (z === "fijo" && m.zoom_en === null && m.zoom_auto === null)}
                        onChange={() => guardarMomento(m.id, z === "fijo" ? { zoom: "fijo", zoom_en: m.zoom_en ?? m.zoom_auto } : { zoom: z })} />
                      {z === "auto" ? `auto${m.zoom_auto === null ? " (no destaca: sin zoom)" : ""}` : z === "no" ? "sin zoom" : "en el marcador ◆"}
                    </label>
                  ))}
                </div>
              </div>
              <div className="campo">
                <span>Lo que se dice</span>
                <div className="dicho">{dicho || "(sin voz)"}</div>
              </div>
              <div className="acciones">
                <button className="ok" disabled={ocupado} onClick={() => guardarMomento(m.id, { estado: "aprobado" }).then(() => mover(1))}>
                  ✓ Aprobar <kbd>A</kbd>
                </button>
                <button className="peligro" disabled={ocupado} onClick={() => guardarMomento(m.id, { estado: "descartado" }).then(() => mover(1))}>
                  ✗ Descartar <kbd>D</kbd>
                </button>
                <span className="suave" style={{ fontSize: 13 }}>
                  <kbd>J</kbd>/<kbd>K</kbd> anterior/siguiente · <kbd>Espacio</kbd> reproducir
                </span>
              </div>
            </>
          ) : (
            <p className="suave">
              {o.modo_momentos === "manual" || !momentos.length
                ? "No hay momentos. Arrastra sobre la línea de tiempo para crear uno."
                : "Elige un momento."}
            </p>
          )}
        </div>
      </div>

      <div className="controles-linea">
        <b>Línea de tiempo</b>
        <button onClick={() => setVista(vista === "todo" ? "cerca" : "todo")} disabled={!m}>
          {vista === "todo" ? "🔍 Acercar al momento" : "↔ Ver todo"}
        </button>
        <span className="suave" style={{ fontSize: 13 }}>
          Arrastra los bordes para ajustar · arrastra en vacío para crear un momento · ◆ marcador de zoom
        </span>
        <span style={{ marginLeft: "auto" }} />
        <button className="principal" disabled={ocupado || !renderizables} onClick={async () => {
          await api.renderizar(id);
          avisar("Renderizando en segundo plano…");
          recargar();
        }} title="Renderiza los aprobados y los ya renderizados que hayas cambiado">
          🎬 Renderizar aprobados ({aprobados})
        </button>
      </div>
      <LineaTiempo
        duracion={p.duracion}
        curva={datos.curva}
        palabras={datos.palabras}
        momentos={momentos}
        activo={activo}
        vista={rango}
        bloqueado={ocupado}
        alElegir={(mid, s) => {
          setActivo(mid);
          setTimeout(() => previa.current?.irA(s), 50);
        }}
        alCambiar={guardarMomento}
        alCrear={async (i, f) => {
          try {
            const nuevo = await api.crearMomento(id, i, f);
            await recargar();
            setActivo(nuevo.id);
          } catch (e) {
            avisar((e as Error).message, true);
          }
        }}
      />
    </>
  );
};
