/** SVG `points` attribute for a polygon in image pixel coordinates. */
export function polygonToPoints(polygon: [number, number][]): string {
  return polygon.map(([x, y]) => `${x},${y}`).join(" ");
}

export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

export function formatLabel(label: string): string {
  const words = label.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
