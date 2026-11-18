import React from "react";
import { Composition } from "remotion";
import { Clip } from "./Clip";
import { ClipProps, EJEMPLO } from "./tipos";

export const Root: React.FC = () => (
  <Composition
    id="Clip"
    component={Clip as unknown as React.FC<Record<string, unknown>>}
    width={1080}
    height={1920}
    fps={60}
    durationInFrames={600}
    defaultProps={EJEMPLO as unknown as Record<string, unknown>}
    calculateMetadata={({ props }) => {
      const p = props as unknown as ClipProps;
      return {
        fps: p.fps,
        durationInFrames: Math.max(1, Math.round(p.duracion * p.fps)),
      };
    }}
  />
);
