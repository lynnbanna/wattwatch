"use client";

import { useEffect, useRef, useState } from "react";
import { rangeTicks, usd, type ComparisonRow } from "@/lib/energy";
import { compact } from "@/lib/solar";

const HEIGHT = 240;
const MARGIN = { top: 12, right: 12, bottom: 26, left: 52 };
const END_LABEL_MIN_GAP = 14;

type Series = { name: string; color: string; values: number[] }; // values[0] = year 0

/** Cumulative cash of each option: −upfront at year 0, then running net savings. */
export function CumulativeCashChart({ rows }: { rows: ComparisonRow[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [year, setYear] = useState<number | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(el.clientWidth));
    observer.observe(el);
    setWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);

  const series: Series[] = rows
    .filter((r) => r.finance && r.color)
    .map((r) => ({
      name: r.name,
      color: r.color!,
      values: [-r.finance!.upfront_usd, ...r.finance!.cumulative_usd],
    }));
  if (!series.length) return null;

  const years = series[0].values.length - 1;
  const all = series.flatMap((s) => s.values);
  const yTicks = rangeTicks(Math.min(0, ...all), Math.max(0, ...all));
  const lo = yTicks[0];
  const hi = yTicks[yTicks.length - 1];
  const plotW = Math.max(width - MARGIN.left - MARGIN.right, 0);
  const plotH = HEIGHT - MARGIN.top - MARGIN.bottom;
  const x = (yr: number) => MARGIN.left + (yr / years) * plotW;
  const y = (v: number) => MARGIN.top + plotH - ((v - lo) / (hi - lo)) * plotH;
  const xTicks = Array.from({ length: Math.floor(years / 5) + 1 }, (_, i) => i * 5);

  // End labels only when they do not collide; otherwise the legend and tooltip carry names.
  const ends = series
    .map((s) => ({ s, y: y(s.values[years]) }))
    .sort((a, b) => a.y - b.y);
  const labelsFit =
    width >= 480 && ends.every((e, i) => i === 0 || e.y - ends[i - 1].y >= END_LABEL_MIN_GAP);

  function onMove(e: React.PointerEvent<SVGSVGElement>) {
    const box = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - box.left;
    const yr = Math.round(((px - MARGIN.left) / plotW) * years);
    setYear(Math.min(Math.max(yr, 0), years));
  }

  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-semibold text-slate-800">
        Cumulative cash compared with no solar (US$)
      </figcaption>
      {series.length > 1 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600" aria-label="Legend">
          {series.map((s) => (
            <li key={s.name} className="flex items-center gap-1.5">
              <span className="inline-block h-0.5 w-4" style={{ background: s.color }} />
              {s.name}
            </li>
          ))}
        </ul>
      )}
      <div ref={ref} className="relative">
        {width > 0 && (
          <svg
            width={width}
            height={HEIGHT}
            role="img"
            aria-label="Cumulative cash by year for each option"
            tabIndex={0}
            className="outline-none"
            onPointerMove={onMove}
            onPointerLeave={() => setYear(null)}
            onFocus={() => setYear(years)}
            onBlur={() => setYear(null)}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft") setYear((v) => Math.max((v ?? years) - 1, 0));
              if (e.key === "ArrowRight") setYear((v) => Math.min((v ?? 0) + 1, years));
            }}
          >
            {yTicks.map((t) => (
              <g key={t}>
                <line
                  x1={MARGIN.left}
                  x2={width - MARGIN.right}
                  y1={y(t)}
                  y2={y(t)}
                  stroke={t === 0 ? "#94a3b8" : "#e2e8f0"}
                  strokeWidth={1}
                />
                <text
                  x={MARGIN.left - 6}
                  y={y(t)}
                  textAnchor="end"
                  dominantBaseline="middle"
                  className="fill-slate-500 text-[11px] tabular-nums"
                >
                  {t < 0 ? "−" : ""}${compact(Math.abs(t))}
                </text>
              </g>
            ))}
            {xTicks.map((t) => (
              <text
                key={t}
                x={x(t)}
                y={HEIGHT - 8}
                textAnchor={t === years ? "end" : t === 0 ? "start" : "middle"}
                className="fill-slate-500 text-[11px] tabular-nums"
              >
                {t === 0 ? "Now" : `Year ${t}`}
              </text>
            ))}
            {year !== null && (
              <line
                x1={x(year)}
                x2={x(year)}
                y1={MARGIN.top}
                y2={MARGIN.top + plotH}
                stroke="#94a3b8"
                strokeWidth={1}
              />
            )}
            {series.map((s) => (
              <g key={s.name}>
                <polyline
                  points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                {year !== null && (
                  <circle
                    cx={x(year)}
                    cy={y(s.values[year])}
                    r={4}
                    fill={s.color}
                    stroke="#ffffff"
                    strokeWidth={2}
                  />
                )}
              </g>
            ))}
            {labelsFit &&
              year === null &&
              ends.map(({ s, y: ly }) => (
                <text
                  key={s.name}
                  x={x(years) - 4}
                  y={ly - 6}
                  textAnchor="end"
                  className="fill-slate-700 text-[11px] font-medium"
                >
                  {s.name}: {usd(s.values[years])}
                </text>
              ))}
          </svg>
        )}
        {year !== null && width > 0 && (
          <div
            role="tooltip"
            className="pointer-events-none absolute top-0 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs shadow-sm"
            style={x(year) > width / 2 ? { left: MARGIN.left + 4 } : { right: MARGIN.right + 4 }}
          >
            <div className="mb-0.5 text-slate-500">{year === 0 ? "At purchase" : `After year ${year}`}</div>
            {series.map((s) => (
              <div key={s.name} className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-1.5 text-slate-500">
                  <span className="inline-block h-0.5 w-3" style={{ background: s.color }} />
                  {s.name}
                </span>
                <span className="font-semibold text-slate-900 tabular-nums">{usd(s.values[year])}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <p className="text-xs text-slate-500">
        Plain cash, not discounted: the net value in the table discounts future years, so it is
        smaller. Dips are battery replacements. Where a line crosses $0, the option has paid for
        itself.
      </p>
      <details className="text-sm">
        <summary className="cursor-pointer text-slate-600">Show as table</summary>
        <div className="mt-2 max-h-64 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-slate-500">
                <th className="py-1 pr-3 font-medium">Year</th>
                {series.map((s) => (
                  <th key={s.name} className="py-1 pr-3 text-right font-medium">
                    {s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular-nums text-slate-700">
              {Array.from({ length: years + 1 }, (_, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="py-1 pr-3">{i === 0 ? "Now" : i}</td>
                  {series.map((s) => (
                    <td key={s.name} className="py-1 pr-3 text-right">
                      {usd(s.values[i])}
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
