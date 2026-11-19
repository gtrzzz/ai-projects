import React, { useRef, useState } from "react";
import { api, ESTADOS, Resumen, subir, tamaño, tiempo, usarSondeo } from "../api";
import { avisar } from "../main";

const nombreDe = (ruta: string) => ruta.split(/[\\/]/).pop();

const Fila: React.FC<{ p: Resumen; recargar: () => void }> = ({ p, recargar }) => {
  const ocupado = ["en_cola", "importando", "preparando", "transcribiendo", "analizando", "renderizando"].includes(p.estado);
  const m = p.momentos;
  const liberar = async () => {
    const ok = window.confirm(
      `¿Liberar ${tamaño(p.liberable)} de «${p.nombre}»?\n\n` +
        "Se borran el vídeo original y el preparado. Los clips ya renderizados se quedan.\n" +
        "Después no podrás editar ni volver a renderizar este vídeo (salvo que lo vuelvas a importar).",
    );
    if (!ok) return;
    try {
      const r = await api.liberar(p.id);
      avisar(`Liberados ${tamaño(r.liberado)}`);
      recargar();
    } catch (e) {
      avisar((e as Error).message, true);
    }
  };
  return (
    <div className="tarjeta fila">
      {p.miniatura ? (
        <video className="miniatura" src={`${p.miniatura}#t=5`} preload="metadata" muted />
      ) : (
        <div className="miniatura" />
      )}
      <div>
        <h3>
          <a href={`#/proyecto/${p.id}`}>{p.nombre}</a>
        </h3>
        <div className="suave">
          {tiempo(p.duracion)} · {ESTADOS[p.estado] ?? p.estado}
          {p.estado !== "error" && (m.propuesto || m.aprobado || m.renderizado) ? (
            <>
              {" · "}
              {m.propuesto ? <span className="chip">{m.propuesto} por revisar</span> : null}
              {m.aprobado ? <span className="chip">{m.aprobado} aprobados</span> : null}
              {m.renderizado ? <span className="chip">📦 {m.renderizado} renderizados</span> : null}
            </>
          ) : null}
        </div>
        {p.error && <div style={{ color: "var(--mal)", marginTop: 4 }}>{p.error}</div>}
        {ocupado && (
          <div className="barra">
            <i style={{ width: `${Math.round(p.progreso * 100)}%` }} />
          </div>
        )}
      </div>
      <div className="acciones">
        <a href={`#/proyecto/${p.id}`}>
          <button className={p.estado === "listo" && m.propuesto ? "principal" : ""} disabled={p.estado === "liberado"}>
            Revisar
          </button>
        </a>
        {p.liberable > 0 && !ocupado && (
          <button className="peligro" onClick={liberar} title="Borra el original y el preparado; conserva los clips">
            🧹 Liberar {tamaño(p.liberable)}
          </button>
        )}
      </div>
    </div>
  );
};

export const Inicio: React.FC = () => {
  const { datos, error, recargar } = usarSondeo(api.estado);
  const [encima, setEncima] = useState(false);
  const [subiendo, setSubiendo] = useState<number | null>(null);
  const elegir = useRef<HTMLInputElement>(null);

  const subirArchivos = async (lista: FileList | null) => {
    const archivos = Array.from(lista ?? []).filter((f) => /\.(mp4|webm|mov|mkv)$/i.test(f.name));
    if (!archivos.length) return avisar("Solo vídeos mp4, webm, mov o mkv", true);
    setSubiendo(0);
    try {
      await subir(archivos, setSubiendo);
      avisar(`${archivos.length} vídeo(s) añadidos`);
      recargar();
    } catch (e) {
      avisar((e as Error).message, true);
    } finally {
      setSubiendo(null);
    }
  };

  const usb = datos?.usb.nuevos ?? [];
  return (
    <>
      {error && <div className="aviso mal">No hay conexión con el panel ({error}). ¿Está abierta la ventana de panel.bat?</div>}
      {usb.length > 0 && (
        <div className="aviso">
          <span style={{ fontSize: 22 }}>🔌</span>
          <div style={{ flex: 1 }}>
            <b>USB de PS5 detectado: {usb.length} vídeo(s) nuevo(s)</b>
            <div className="suave">{usb.slice(0, 4).map(nombreDe).join(" · ")}{usb.length > 4 ? " …" : ""}</div>
          </div>
          <button
            className="principal"
            onClick={async () => {
              await api.importar(usb);
              avisar("Importando… se analizarán solos");
              recargar();
            }}
          >
            Importar
          </button>
        </div>
      )}
      <div
        className={`suelta ${encima ? "encima" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setEncima(true);
        }}
        onDragLeave={() => setEncima(false)}
        onDrop={(e) => {
          e.preventDefault();
          setEncima(false);
          subirArchivos(e.dataTransfer.files);
        }}
      >
        {subiendo !== null ? (
          <>Subiendo… {Math.round(subiendo * 100)} %</>
        ) : (
          <>
            Arrastra aquí vídeos o <button onClick={() => elegir.current?.click()}>Elegir archivos</button>
            <div style={{ marginTop: 6, fontSize: 13 }}>
              También vale meterlos en la carpeta <b>entrada</b> o conectar el USB de la PS5.
            </div>
          </>
        )}
        <input ref={elegir} type="file" accept="video/*" multiple hidden onChange={(e) => subirArchivos(e.target.files)} />
      </div>
      <div className="lista">
        {datos?.proyectos.map((p) => <Fila key={p.id} p={p} recargar={recargar} />)}
        {datos && datos.proyectos.length === 0 && (
          <p className="suave" style={{ textAlign: "center" }}>
            Todavía no hay vídeos. Añade uno para empezar.
          </p>
        )}
      </div>
    </>
  );
};
