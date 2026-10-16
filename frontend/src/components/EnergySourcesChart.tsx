"use client";

import { useEffect, useRef, useState } from "react";
import { SOURCES, type ComparisonRow } from "@/lib/energy";
import { compact, formatKwh } from "@/lib/solar";

const ROW_H = 20; // bar thickness (<= 24px)
const ROW_GAP = 22;
const LABEL_W = 120;
const GAP = 2; // surface gap between segments
const MIN_LABEL_W = 40; // only label a segment when the text fits

/** Part-to-whole: each option's yearly electricity split by source (horizontal stacks). */
export function EnergySourcesChart({ rows }: { rows: ComparisonRow[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [active, setActive] = useState<{ row: number; source: number } | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(el.clientWidth));
    observer.observe(el);
    setWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);

  const narrow = width < 480;
  const labelW = narrow ? 0 : LABEL_W;
  const plotW = Math.max(width - labelW - 8, 0);
  const max = Math.max(...rows.map((r) => r.energy.demand_kwh), 1);
  const rowStep = ROW_H + ROW_GAP + (narrow ? 16 : 0);
  const height = rows.length * rowStep;

  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-semibold text-slate-800">
        Where the year&apos;s electricity comes from (kWh)
      </figcaption>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600" aria-label="Legend">
        {SOURCES.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
            {s.label}
          </li>
        ))}
      </ul>
      <div ref={ref} className="relative">
        {width > 0 && (
          <svg width={width} height={height} role="img" aria-label="Electricity sources by option">
            {rows.map((row, r) => {
              const y = r * rowStep + (narrow ? 16 : 0);
              let x = labelW;
              return (
                <g key={row.name}>
                  <text
                    x={narrow ? 0 : labelW - 8}
                    y={narrow ? y - 4 : y + ROW_H / 2}
                    textAnchor={narrow ? "start" : "end"}
                    dominantBaseline={narrow ? "auto" : "middle"}
                    className="fill-slate-700 text-[12px]"
                  >
                    {row.name}
                  </text>
                  {SOURCES.map((s, i) => {
                    const value = row.energy[s.key];
                    const w = (value / max) * plotW;
                    const segX = x;
                    x += w;
                    if (w <= 0) return null;
                    const drawn = Math.max(w - GAP, 1);
                    const isActive = active?.row === r && active.source === i;
                    return (
                      <g
                        key={s.key}
                        tabIndex={0}
                        role="img"
                        aria-label={`${row.name}, ${s.label}: ${formatKwh(value)}`}
                        className="outline-none"
                        onPointerEnter={() => setActive({ row: r, source: i })}
                        onPointerLeave={() => setActive(null)}
                        onFocus={() => setActive({ row: r, source: i })}
                        onBlur={() => setActive(null)}
                      >
                        <rect
                          x={segX}
                          y={y - 6}
                          width={w}
                          height={ROW_H + 12}
                          fill="transparent"
                        />
                        <rect
                          x={segX}
                          y={y}
                          width={drawn}
                          height={ROW_H}
                          rx={i === lastIndex(row) ? 4 : 0}
                          fill={s.color}
                          opacity={active && !isActive ? 0.55 : 1}
                        />
                        {drawn >= MIN_LABEL_W && (
                          <text
                            x={segX + drawn / 2}
                            y={y + ROW_H / 2}
                            textAnchor="middle"
                            dominantBaseline="middle"
                            className="pointer-events-none fill-white text-[11px] font-medium"
                            style={{ fill: i >= 2 ? "#0b0b0b" : "#ffffff" }}
                          >
                            {compact(value)}
                          </text>
                        )}
                      </g>
                    );
                  })}
                </g>
              );
            })}
          </svg>
        )}
        {active && width > 0 && (
          <Tooltip row={rows[active.row]} source={active.source} top={active.row * rowStep} />
        )}
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-slate-600">Show as table</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-slate-500">
                <th className="py-1 pr-3 font-medium">Option</th>
                {SOURCES.map((s) => (
                  <th key={s.key} className="py-1 pr-3 text-right font-medium">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular-nums text-slate-700">
              {rows.map((row) => (
                <tr key={row.name} className="border-t border-slate-100">
                  <td className="py-1 pr-3">{row.name}</td>
                  {SOURCES.map((s) => (
                    <td key={s.key} className="py-1 pr-3 text-right">
                      {Math.round(row.energy[s.key]).toLocaleString("en-US")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

/** Index of the last non-zero segment, which gets the rounded data-end. */
function lastIndex(row: ComparisonRow): number {
  let last = 0;
  SOURCES.forEach((s, i) => {
    if (row.energy[s.key] > 0) last = i;
  });
  return last;
}

function Tooltip({ row, source, top }: { row: ComparisonRow; source: number; top: number }) {
  const s = SOURCES[source];
  const value = row.energy[s.key];
  const share = row.energy.demand_kwh ? value / row.energy.demand_kwh : 0;
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute right-0 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs shadow-sm"
      style={{ top: Math.max(top - 44, 0) }}
    >
      <div className="font-semibold text-slate-900 tabular-nums">
        {formatKwh(value)} <span className="font-normal text-slate-500">({Math.round(share * 100)}%)</span>
      </div>
      <div className="flex items-center gap-1.5 text-slate-500">
        <span className="inline-block h-0.5 w-3" style={{ background: s.color }} />
        {s.label} · {row.name}
      </div>
    </div>
  );
}
