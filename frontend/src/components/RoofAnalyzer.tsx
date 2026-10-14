"use client";

import { useEffect, useRef, useState } from "react";
import {
  ACCEPTED_IMAGE_TYPES,
  analyzeRoof,
  validateImageFile,
  type Detection,
  type RoofAnalysisResponse,
} from "@/lib/api";
import { formatConfidence, formatLabel, polygonToPoints } from "@/lib/overlay";

type State =
  | { kind: "empty" }
  | { kind: "loading"; imageUrl: string }
  | { kind: "done"; imageUrl: string; result: RoofAnalysisResponse }
  | { kind: "error"; imageUrl: string | null; message: string };

const ROOF_STYLE = "fill-teal-400/25 stroke-teal-600";
const OBSTACLE_STYLE = "fill-amber-400/40 stroke-amber-600";

export function RoofAnalyzer() {
  const [state, setState] = useState<State>({ kind: "empty" });
  const controllerRef = useRef<AbortController | null>(null);
  const imageUrl = state.kind === "empty" ? null : state.imageUrl;

  useEffect(() => {
    return () => {
      if (imageUrl) URL.revokeObjectURL(imageUrl);
    };
  }, [imageUrl]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  function handleFile(file: File | undefined) {
    if (!file) return;
    const invalid = validateImageFile(file);
    if (invalid) {
      setState({ kind: "error", imageUrl: null, message: invalid });
      return;
    }

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const url = URL.createObjectURL(file);
    setState({ kind: "loading", imageUrl: url });

    analyzeRoof(file, controller.signal)
      .then((result) => setState({ kind: "done", imageUrl: url, result }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          kind: "error",
          imageUrl: url,
          message: err instanceof Error ? err.message : "Analysis failed",
        });
      });
  }

  return (
    <div className="space-y-6">
      <label className="block rounded-lg border-2 border-dashed border-slate-300 p-6 text-center hover:border-teal-500">
        <span className="font-medium text-slate-800">Choose a rooftop image</span>
        <span className="mt-1 block text-sm text-slate-500">PNG or JPEG, up to 10 MB</span>
        <input
          type="file"
          accept={ACCEPTED_IMAGE_TYPES.join(",")}
          className="sr-only"
          onChange={(e) => {
            handleFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </label>

      {state.kind === "empty" && (
        <p className="text-sm text-slate-500">
          Upload a top-down aerial or drone image, ideally about 15 cm per pixel, to see the
          detected roof outlines and obstacles. Photos taken at an angle will not give reliable
          results.
        </p>
      )}

      {state.kind === "error" && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {state.message}
        </p>
      )}

      {imageUrl && (
        <figure className="relative overflow-hidden rounded-lg border border-slate-200">
          {/* eslint-disable-next-line @next/next/no-img-element -- local blob URL */}
          <img src={imageUrl} alt="Uploaded rooftop" className="block h-auto w-full" />
          {state.kind === "done" && <Overlay result={state.result} />}
          {state.kind === "loading" && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/60 text-sm font-medium text-slate-700">
              Analyzing roof…
            </div>
          )}
        </figure>
      )}

      {state.kind === "done" && <Results result={state.result} />}
    </div>
  );
}

function Overlay({ result }: { result: RoofAnalysisResponse }) {
  const { width_px, height_px } = result.image;
  return (
    <svg
      viewBox={`0 0 ${width_px} ${height_px}`}
      preserveAspectRatio="none"
      className="absolute inset-0 h-full w-full"
      aria-hidden="true"
    >
      {result.roofs.map((d, i) => (
        <polygon
          key={`roof-${i}`}
          points={polygonToPoints(d.polygon_px)}
          className={ROOF_STYLE}
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      ))}
      {result.obstacles.map((d, i) => (
        <polygon
          key={`obstacle-${i}`}
          points={polygonToPoints(d.polygon_px)}
          className={OBSTACLE_STYLE}
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      ))}
    </svg>
  );
}

function Results({ result }: { result: RoofAnalysisResponse }) {
  return (
    <section className="space-y-4">
      {result.model.is_stub && (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          These shapes come from a placeholder model and do not reflect this image.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <DetectionList title="Roof" swatch="bg-teal-400" items={result.roofs} />
        <DetectionList title="Obstacles" swatch="bg-amber-400" items={result.obstacles} />
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-800">Limitations</h3>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-600">
          {result.limitations.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </div>

      <p className="text-xs text-slate-400">
        Model {result.model.name} v{result.model.version} · image {result.image.width_px}×
        {result.image.height_px} px
      </p>
    </section>
  );
}

function DetectionList({
  title,
  swatch,
  items,
}: {
  title: string;
  swatch: string;
  items: Detection[];
}) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
        <span className={`inline-block h-3 w-3 rounded-sm ${swatch}`} />
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">None detected</p>
      ) : (
        <ul className="mt-2 space-y-1 text-sm text-slate-700">
          {items.map((d, i) => (
            <li key={i} className="flex justify-between">
              <span>{formatLabel(d.label)}</span>
              <span className="text-slate-500">confidence {formatConfidence(d.confidence)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
