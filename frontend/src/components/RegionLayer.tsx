"use client";

import { useEffect, useRef, useState } from "react";
import type { Point } from "@/lib/api";
import { midpoint, type EditorAction, type Region, type Draft } from "@/lib/editing";
import { polygonToPoints, toImagePixels } from "@/lib/overlay";

const FILL: Record<Region["kind"], string> = {
  roof: "fill-teal-400/25 stroke-teal-600",
  obstacle: "fill-amber-400/40 stroke-amber-600",
};
const HANDLE_PX = 6; // on-screen radius of vertex handles

type Props = {
  width: number;
  height: number;
  regions: Region[];
  selectedId: string | null;
  draft: Draft | null;
  editing: boolean;
  dispatch: (action: EditorAction) => void;
};

/** Region outlines over the image; editable when `editing` is true. */
export function RegionLayer({ width, height, regions, selectedId, draft, editing, dispatch }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [displayWidth, setDisplayWidth] = useState(width);
  const [dragging, setDragging] = useState<{ id: string; index: number } | null>(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const observer = new ResizeObserver(() => setDisplayWidth(svg.clientWidth || width));
    observer.observe(svg);
    return () => observer.disconnect();
  }, [width]);

  const r = (HANDLE_PX * width) / Math.max(displayWidth, 1);
  const interactive = editing || draft !== null;

  function pointFrom(e: React.PointerEvent): Point {
    const box = svgRef.current!.getBoundingClientRect();
    return toImagePixels(e.clientX, e.clientY, box, width, height);
  }

  function startDrag(e: React.PointerEvent, id: string, index: number) {
    e.stopPropagation();
    svgRef.current?.setPointerCapture(e.pointerId);
    setDragging({ id, index });
  }

  const selected = regions.find((reg) => reg.id === selectedId);

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={`absolute inset-0 h-full w-full ${interactive ? "touch-none" : "pointer-events-none"} ${draft ? "cursor-crosshair" : ""}`}
      role={interactive ? "application" : undefined}
      aria-label={interactive ? "Outline editor" : undefined}
      aria-hidden={interactive ? undefined : true}
      onPointerDown={(e) => {
        if (draft) dispatch({ type: "addDraftPoint", point: pointFrom(e) });
        else if (editing) dispatch({ type: "select", id: null });
      }}
      onPointerMove={(e) => {
        if (dragging) dispatch({ type: "moveVertex", ...dragging, point: pointFrom(e) });
      }}
      onPointerUp={() => setDragging(null)}
      onPointerCancel={() => setDragging(null)}
    >
      {regions.map((reg) => (
        <polygon
          key={reg.id}
          points={polygonToPoints(reg.polygon)}
          className={`${FILL[reg.kind]} ${editing && !draft ? "cursor-pointer" : ""}`}
          strokeWidth={reg.id === selectedId ? 3 : 2}
          strokeDasharray={reg.source === "model" ? undefined : "6 4"}
          vectorEffect="non-scaling-stroke"
          onPointerDown={(e) => {
            if (!editing || draft) return;
            e.stopPropagation();
            dispatch({ type: "select", id: reg.id });
          }}
        />
      ))}

      {editing && !draft && selected && (
        <g>
          {selected.polygon.map((p, i) => {
            const next = selected.polygon[(i + 1) % selected.polygon.length];
            const [mx, my] = midpoint(p, next);
            return (
              <circle
                key={`mid-${i}`}
                cx={mx}
                cy={my}
                r={r * 0.6}
                className="cursor-copy fill-white/70 stroke-slate-500"
                vectorEffect="non-scaling-stroke"
                onPointerDown={(e) => {
                  dispatch({
                    type: "insertVertex",
                    id: selected.id,
                    afterIndex: i,
                    point: [mx, my],
                  });
                  startDrag(e, selected.id, i + 1);
                }}
              />
            );
          })}
          {selected.polygon.map(([x, y], i) => (
            <circle
              key={`v-${i}`}
              cx={x}
              cy={y}
              r={r}
              className="cursor-move fill-white stroke-slate-900"
              strokeWidth={2}
              vectorEffect="non-scaling-stroke"
              onPointerDown={(e) => {
                dispatch({ type: "checkpoint" });
                startDrag(e, selected.id, i);
              }}
              onDoubleClick={(e) => {
                e.stopPropagation();
                dispatch({ type: "removeVertex", id: selected.id, index: i });
              }}
            />
          ))}
        </g>
      )}

      {draft && draft.points.length > 0 && (
        <g className={FILL[draft.kind]}>
          <polyline
            points={polygonToPoints(draft.points)}
            fill="none"
            strokeWidth={2}
            strokeDasharray="6 4"
            vectorEffect="non-scaling-stroke"
          />
          {draft.points.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={r * 0.8} className="fill-white" />
          ))}
        </g>
      )}
    </svg>
  );
}
