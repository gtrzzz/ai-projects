import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./estilos.css";
import { Inicio } from "./pantallas/Inicio";
import { ProyectoPantalla } from "./pantallas/Proyecto";
import { Publicar } from "./pantallas/Publicar";
import { AjustesPantalla } from "./pantallas/Ajustes";

const ruta = () => window.location.hash.replace(/^#/, "") || "/";

// Avisos breves abajo a la derecha
export const avisar = (texto: string, mal = false) =>
  window.dispatchEvent(new CustomEvent("aviso", { detail: { texto, mal } }));

const Avisos: React.FC = () => {
  const [aviso, setAviso] = useState<{ texto: string; mal: boolean } | null>(null);
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const f = (e: Event) => {
      setAviso((e as CustomEvent).detail);
      clearTimeout(t);
      t = setTimeout(() => setAviso(null), 4000);
    };
    window.addEventListener("aviso", f);
    return () => window.removeEventListener("aviso", f);
  }, []);
  return aviso ? <div className={`toast ${aviso.mal ? "mal" : ""}`}>{aviso.texto}</div> : null;
};

const App: React.FC = () => {
  const [r, setR] = useState(ruta());
  useEffect(() => {
    const f = () => setR(ruta());
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  const proyecto = r.match(/^\/proyecto\/([a-z0-9-]+)/);
  const enlace = (href: string, texto: string, activo: boolean) => (
    <a href={`#${href}`} className={activo ? "activo" : ""}>
      {texto}
    </a>
  );
  return (
    <>
      <header className="cabecera">
        <a href="#/" className="marca">
          🎬 CLIPPER
        </a>
        <nav>
          {enlace("/", "Vídeos", r === "/" || !!proyecto)}
          {enlace("/publicar", "Publicar", r === "/publicar")}
          {enlace("/ajustes", "⚙ Ajustes", r === "/ajustes")}
        </nav>
      </header>
      <main>
        {proyecto ? (
          <ProyectoPantalla key={proyecto[1]} id={proyecto[1]} />
        ) : r === "/publicar" ? (
          <Publicar />
        ) : r === "/ajustes" ? (
          <AjustesPantalla />
        ) : (
          <Inicio />
        )}
      </main>
      <Avisos />
    </>
  );
};

createRoot(document.getElementById("raiz")!).render(<App />);
