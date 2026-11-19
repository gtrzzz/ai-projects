import React from "react";
import { api, ClipPublicar, Plataforma, PLATAFORMAS, usarSondeo } from "../api";
import { avisar } from "../main";

const NOMBRES: Record<Plataforma, string> = { tiktok: "TikTok", reels: "Reels", shorts: "Shorts" };

const franjaTexto = ([a, b]: [string, string]) => {
  const ini = new Date(a);
  const fin = new Date(b);
  const ahora = new Date();
  const hora = (d: Date) => d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
  if (ini <= ahora) return `ahora, hasta las ${hora(fin)}`;
  const dia = ini.toDateString() === ahora.toDateString() ? "hoy" : "mañana";
  return `${dia} ${hora(ini)}–${hora(fin)}`;
};

const Clip: React.FC<{ c: ClipPublicar; franjas: Record<Plataforma, [string, string]>; recargar: () => void }> = ({ c, franjas, recargar }) => {
  const copiar = async (p: Plataforma) => {
    await navigator.clipboard.writeText(c.textos[p]);
    avisar(`Texto de ${NOMBRES[p]} copiado`);
  };
  const marcar = async (p: Plataforma, v: boolean) => {
    try {
      await api.momento(c.pid, c.mid, { subido: { ...c.subido, [p]: v } });
      recargar();
    } catch (e) {
      avisar((e as Error).message, true);
    }
  };
  return (
    <div className="tarjeta publicar">
      <video src={c.video} controls preload="metadata" />
      <div>
        <h3 style={{ margin: "0 0 4px" }}>{c.titulo}</h3>
        <div className="suave" style={{ marginBottom: 10 }}>
          {c.nombre} · {c.duracion} s ·{" "}
          <a href={c.video} download>
            Descargar mp4
          </a>
        </div>
        {c.textos.aviso && <div className="aviso">{c.textos.aviso}</div>}
        <div className="plataformas">
          {PLATAFORMAS.map((p) => (
            <div key={p} className="plataforma">
              <div className="acciones" style={{ justifyContent: "space-between" }}>
                <b>{NOMBRES[p]}</b>
                <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
                  <input type="checkbox" checked={c.subido[p]} onChange={(e) => marcar(p, e.target.checked)} />
                  Subido
                </label>
              </div>
              <div className="suave" style={{ fontSize: 13, margin: "4px 0 8px" }}>
                🕒 Mejor hora: {franjaTexto(franjas[p])}
              </div>
              <button onClick={() => copiar(p)} style={{ width: "100%" }}>
                📋 Copiar texto
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export const Publicar: React.FC = () => {
  const { datos, recargar } = usarSondeo(api.publicar, 5000);
  if (!datos) return <p className="suave">Cargando…</p>;
  const pendientes = datos.clips.filter((c) => !PLATAFORMAS.every((p) => c.subido[p]));
  const subidos = datos.clips.filter((c) => PLATAFORMAS.every((p) => c.subido[p]));
  return (
    <div className="lista">
      <p className="suave" style={{ margin: 0 }}>
        Las horas son orientativas (hora de este PC) y se cambian en Ajustes. Lo mejor es mirar después tus
        estadísticas en cada plataforma.
      </p>
      {pendientes.map((c) => (
        <Clip key={c.mid} c={c} franjas={datos.franjas} recargar={recargar} />
      ))}
      {!datos.clips.length && <p className="suave">Todavía no hay clips renderizados.</p>}
      {subidos.length > 0 && (
        <details>
          <summary className="suave">Ya subidos a todo ({subidos.length})</summary>
          <div className="lista" style={{ marginTop: 10 }}>
            {subidos.map((c) => (
              <Clip key={c.mid} c={c} franjas={datos.franjas} recargar={recargar} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
};
