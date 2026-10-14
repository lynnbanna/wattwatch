import type { Point } from "./api";

/** SVG `points` attribute for a polygon in image pixel coordinates. */
export function polygonToPoints(polygon: Point[]): string {
  return polygon.map(([x, y]) => `${x},${y}`).join(" ");
}

export function formatScore(score: number): string {
  return score.toFixed(2);
}

export function formatArea(m2: number): string {
  return `${m2 < 10 ? m2.toFixed(1) : Math.round(m2).toLocaleString("en-US")} m²`;
}

export function formatLabel(label: string): string {
  const words = label.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Convert a pointer position on the displayed image to the image's own pixel coordinates. */
export function toImagePixels(
  clientX: number,
  clientY: number,
  box: { left: number; top: number; width: number; height: number },
  naturalWidth: number,
  naturalHeight: number,
): Point {
  const x = ((clientX - box.left) / box.width) * naturalWidth;
  const y = ((clientY - box.top) / box.height) * naturalHeight;
  return [
    Math.round(Math.min(Math.max(x, 0), naturalWidth) * 10) / 10,
    Math.round(Math.min(Math.max(y, 0), naturalHeight) * 10) / 10,
  ];
}

export function pixelDistance([x1, y1]: Point, [x2, y2]: Point): number {
  return Math.hypot(x2 - x1, y2 - y1);
}
