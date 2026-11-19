import React, { useEffect, useState } from "react";
import { Ajustes, api, Plantillas, Plataforma, PLATAFORMAS } from "../api";
import { avisar } from "../main";

const lineas = (t: string) => t.split("\n").map((x) => x.trim()).filter(Boolean);
const palabras = (t: string) => t.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean);

export const AjustesPantalla: React.FC = () => {
  const [aj, setAj] = useState<Ajustes | null>(null);
  const [pl, setPl] = useState<Plantillas | null>(null);
  const [tipo, setTipo] = useState("momento");

  useEffect(() => {
    api.ajustes().then(setAj);
    api.plantillas().then(setPl);
  }, []);
  if (!aj || !pl) return <p className="suave">Cargando…</p>;

  const pon = (k: string, v: unknown) => setAj({ ...aj, [k]: v });
  const num = (k: string) => (
    <input type="number" value={aj[k] as number} onChange={(e) => pon(k, Number(e.target.value))} />
  );
  const guardar = async () => {
    try {
      await api.guardarAjustes(aj);
      const limpias = Object.fromEntries(
        Object.entries(pl.tipos).map(([k, v]) => [k, { ...v, ganchos: v.ganchos.map((g) => g.trim()).filter(Boolean) }]),
      );
      setPl(await api.guardarPlantillas({ ...pl, tipos: limpias }));
      avisar("Guardado");
    } catch (e) {
      avisar((e as Error).message, true);
    }
  };
  const franja = (p: Plataforma, i: number, j: 0 | 1, v: string) => {
    const f = { ...aj.franjas, [p]: aj.franjas[p].map((x, k) => (k === i ? (j ? [x[0], v] : [v, x[1]]) : x)) };
    pon("franjas", f);
  };
  const t = pl.tipos[tipo];
  const ponTipo = (cambios: Partial<typeof t>) => setPl({ ...pl, tipos: { ...pl.tipos, [tipo]: { ...t, ...cambios } } });

  return (
    <div className="ajustes">
      <section className="tarjeta">
        <h2>Al importar un vídeo</h2>
        <div className="formulario">
          <label>
            Momentos
            <select value={aj.modo_momentos as string} onChange={(e) => pon("modo_momentos", e.target.value)}>
              <option value="auto">Automático</option>
              <option value="entero">Vídeo entero</option>
              <option value="manual">Los marco yo</option>
            </select>
          </label>
          <label>
            Nº de clips (vacío = automático)
            <input type="number" value={(aj.clips as number | null) ?? ""} onChange={(e) => pon("clips", e.target.value ? Number(e.target.value) : null)} />
          </label>
          <label>Duración objetivo (s){num("duracion_clip")}</label>
          <label>Duración máxima (s){num("duracion_max")}</label>
          <label>Vídeo corto (entero) hasta (s){num("umbral_largo")}</label>
          <label>
            Tipo
            <select value={aj.tipo as string} onChange={(e) => pon("tipo", e.target.value)}>
              {Object.keys(pl.tipos).map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
          <label>
            Formato
            <select value={aj.formato as string} onChange={(e) => pon("formato", e.target.value)}>
              <option value="zoom">Zoom (juego grande)</option>
              <option value="blur">Entero (sin recortar)</option>
              <option value="recorte">Recorte (pantalla completa)</option>
            </select>
          </label>
          <label>
            Idioma de la voz
            <select value={aj.idioma as string} onChange={(e) => pon("idioma", e.target.value)}>
              <option value="es">Español</option>
              <option value="en">Inglés</option>
              <option value="auto">Automático</option>
            </select>
          </label>
          <label className="casilla">
            <input type="checkbox" checked={aj.importar_usb_auto as boolean} onChange={(e) => pon("importar_usb_auto", e.target.checked)} />
            Importar del USB de la PS5 sin preguntar
          </label>
          <label className="casilla">
            <input type="checkbox" checked={aj.revisar_antes as boolean} onChange={(e) => pon("revisar_antes", e.target.checked)} />
            Revisar antes de renderizar (si no, renderiza todo lo propuesto)
          </label>
        </div>
      </section>

      <section className="tarjeta">
        <h2>Zoom automático</h2>
        <p className="suave" style={{ marginTop: 0 }}>
          Solo hace zoom si el pico del clip supera este percentil de toda la partida y es varias veces la media del clip.
          Súbelos si hace zoom de más.
        </p>
        <div className="formulario">
          <label>Percentil de la partida (85){num("zoom_percentil")}</label>
          <label>Veces la mediana del clip (1,6)<input type="number" step="0.1" value={aj.zoom_factor_mediana as number} onChange={(e) => pon("zoom_factor_mediana", Number(e.target.value))} /></label>
        </div>
      </section>

      <section className="tarjeta">
        <h2>Horas sugeridas para publicar</h2>
        <div className="formulario">
          {PLATAFORMAS.map((p) => (
            <div key={p}>
              <b style={{ textTransform: "capitalize" }}>{p}</b>
              {aj.franjas[p].map((x, i) => (
                <div key={i} className="acciones" style={{ marginTop: 6 }}>
                  <input type="time" value={x[0]} onChange={(e) => franja(p, i, 0, e.target.value)} />–
                  <input type="time" value={x[1]} onChange={(e) => franja(p, i, 1, e.target.value)} />
                  <button className="peligro" disabled={aj.franjas[p].length < 2}
                    onClick={() => pon("franjas", { ...aj.franjas, [p]: aj.franjas[p].filter((_, k) => k !== i) })}>✕</button>
                </div>
              ))}
              <button style={{ marginTop: 6 }} onClick={() => pon("franjas", { ...aj.franjas, [p]: [...aj.franjas[p], ["12:00", "13:00"]] })}>
                + franja
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="tarjeta">
        <h2>Textos (plantillas)</h2>
        <div className="formulario">
          <label>
            Llamada final del vídeo
            <input value={pl.cta} onChange={(e) => setPl({ ...pl, cta: e.target.value })} />
          </label>
          <label>
            Hashtags de siempre
            <input value={pl.hashtags_base.join(" ")} onChange={(e) => setPl({ ...pl, hashtags_base: palabras(e.target.value) })} />
          </label>
        </div>
        <div className="acciones" style={{ margin: "16px 0 10px" }}>
          Tipo:
          <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
            {Object.keys(pl.tipos).map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </div>
        <div className="formulario">
          <label style={{ gridColumn: "1 / -1" }}>
            Ganchos (uno por línea; el panel los va rotando)
            <textarea value={t.ganchos.join("\n")} onChange={(e) => ponTipo({ ganchos: e.target.value.split("\n") })}
              onBlur={(e) => ponTipo({ ganchos: lineas(e.target.value) })} />
          </label>
          <label>
            Pregunta para comentarios
            <input value={t.pregunta} onChange={(e) => ponTipo({ pregunta: e.target.value })} />
          </label>
          <label>
            Hashtags del tipo
            <input value={t.hashtags.join(" ")} onChange={(e) => ponTipo({ hashtags: palabras(e.target.value) })} />
          </label>
          <label style={{ gridColumn: "1 / -1" }}>
            Descripción de YouTube
            <input value={t.descripcion_yt} onChange={(e) => ponTipo({ descripcion_yt: e.target.value })} />
          </label>
        </div>
      </section>

      <div className="acciones" style={{ position: "sticky", bottom: 16 }}>
        <button className="principal" onClick={guardar}>
          Guardar ajustes
        </button>
      </div>
    </div>
  );
};
