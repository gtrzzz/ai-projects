import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { Player, PlayerRef } from "@remotion/player";
import { Clip } from "../../src/Clip";
import type { ClipProps } from "../../src/tipos";
import { api } from "../api";

export type PreviaRef = { irA: (segundo: number) => void; alternar: () => void };

// Vista previa con el mismo Clip.tsx que el render. Las props vienen siempre del servidor
// (GET /api/proyectos/{id}/props/{mid}), así no puede salir distinta del vídeo final.
export const Previa = forwardRef<PreviaRef, { pid: string; mid: string; version: number }>(({ pid, mid, version }, ref) => {
  const [props, setProps] = useState<ClipProps | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reproductor = useRef<PlayerRef>(null);

  useEffect(() => {
    let vivo = true;
    api
      .props(pid, mid)
      .then((p) => vivo && (setProps(p), setError(null)))
      .catch((e) => vivo && setError((e as Error).message));
    return () => {
      vivo = false;
    };
  }, [pid, mid, version]);

  useImperativeHandle(ref, () => ({
    irA: (s: number) => props && reproductor.current?.seekTo(Math.max(0, Math.round(s * props.fps))),
    alternar: () => reproductor.current?.toggle(),
  }));

  if (error) return <div className="previa suave" style={{ padding: 16 }}>{error}</div>;
  if (!props) return <div className="previa" />;
  return (
    <div className="previa">
      <Player
        ref={reproductor}
        component={Clip as unknown as React.FC<Record<string, unknown>>}
        inputProps={props as unknown as Record<string, unknown>}
        compositionWidth={1080}
        compositionHeight={1920}
        fps={props.fps}
        durationInFrames={Math.max(1, Math.round(props.duracion * props.fps))}
        style={{ width: "100%", height: "100%" }}
        controls
        acknowledgeRemotionLicense
      />
    </div>
  );
});
