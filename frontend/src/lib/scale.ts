import type { Point, ScaleInput } from "./api";
import { pixelDistance } from "./overlay";

// Mirrors the API's limits (backend/app/measure/scale.py) for early feedback.
export const MIN_GSD_M = 0.005;
export const MAX_GSD_M = 2.0;
export const MIN_REFERENCE_PX = 10;

export type ScaleMode = "gsd" | "reference_line";

export type ScaleForm = {
  mode: ScaleMode;
  gsdCm: string;
  start: Point | null;
  end: Point | null;
  lengthM: string;
};

export type ScaleResult = { scale: ScaleInput; gsdM: number } | { error: string };

function positiveNumber(text: string): number | null {
  const value = Number(text.trim().replace(",", "."));
  return text.trim() !== "" && Number.isFinite(value) && value > 0 ? value : null;
}

function checkRange(gsdM: number): string | null {
  if (gsdM < MIN_GSD_M || gsdM > MAX_GSD_M) {
    return `That works out to ${(gsdM * 100).toPrecision(3)} cm per pixel, outside the supported ${MIN_GSD_M * 100}–${MAX_GSD_M * 100} cm range. Check the value or the reference line.`;
  }
  return null;
}

/** Validate the scale form and convert it to the API's scale input. */
export function scaleFromForm(form: ScaleForm): ScaleResult {
  if (form.mode === "gsd") {
    const cm = positiveNumber(form.gsdCm);
    if (cm === null) return { error: "Enter the image resolution in centimetres per pixel." };
    const gsdM = cm / 100;
    const outOfRange = checkRange(gsdM);
    return outOfRange ? { error: outOfRange } : { scale: { kind: "gsd", gsdM }, gsdM };
  }

  if (!form.start || !form.end) {
    return { error: "Click two points on the image to draw the reference line." };
  }
  const pixels = pixelDistance(form.start, form.end);
  if (pixels < MIN_REFERENCE_PX) {
    return { error: "The reference line is too short; draw it along a long, known edge." };
  }
  const lengthM = positiveNumber(form.lengthM);
  if (lengthM === null) return { error: "Enter the real length of the reference line in metres." };
  const gsdM = lengthM / pixels;
  const outOfRange = checkRange(gsdM);
  return outOfRange
    ? { error: outOfRange }
    : { scale: { kind: "reference_line", start: form.start, end: form.end, lengthM }, gsdM };
}

/** Next state of the reference line after a click: start, then end, then start over. */
export function nextReferenceLine(
  start: Point | null,
  end: Point | null,
  click: Point,
): { start: Point; end: Point | null } {
  if (!start || end) return { start: click, end: null };
  return { start, end: click };
}

export function parseMargin(text: string, max: number): number | null {
  const value = Number(text.trim().replace(",", "."));
  return text.trim() !== "" && Number.isFinite(value) && value >= 0 && value <= max ? value : null;
}
