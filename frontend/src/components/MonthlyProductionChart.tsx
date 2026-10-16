"use client";

import { useEffect, useRef, useState } from "react";
import { compact, formatKwh, MONTHS, niceTicks } from "@/lib/solar";

// Validated single-series hue (dataviz reference palette, slot 1) and its hover lift.
const BAR = "#2a78d6";
const BAR_ACTIVE = "#3987e5";
const HEIGHT = 220;
const MARGIN = { top: 20, right: 8, bottom: 24, left: 40 };
const MAX_BAR = 24;
const RADIUS = 4;

const FULL_MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** Column with a rounded data-end and a square baseline. */
function columnPath(x: number, y: number, w: number, h: number): string {
  const r = Math.min(RADIUS, w / 2, h);
  return [
    `M${x},${y + h}`,
    `V${y + r}`,
    `Q${x},${y} ${x + r},${y}`,
    `H${x + w - r}`,
    `Q${x + w},${y} ${x + w},${y + r}`,
    `V${y + h}`,
    "Z",
  ].join(" ");
}

export function MonthlyProductionChart({ monthlyKwh }: { monthlyKwh: number[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [active, setActive] = useState<number | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(el.clientWidth));
    observer.observe(el);
    setWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);

  const ticks = niceTicks(Math.max(...monthlyKwh));
  const top = ticks[ticks.length - 1];
  const plotW = Math.max(width - MARGIN.left - MARGIN.right, 0);
  const plotH = HEIGHT - MARGIN.top - MARGIN.bottom;
  const band = plotW / 12;
  const barW = Math.min(MAX_BAR, band * 0.6);
  const y = (v: number) => MARGIN.top + plotH - (v / top) * plotH;
  const peak = monthlyKwh.indexOf(Math.max(...monthlyKwh));

  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-semibold text-slate-800">
        Estimated production per month (kWh)
      </figcaption>
      <div ref={ref} className="relative">
        {width > 0 && (
          <svg width={width} height={HEIGHT} role="img" aria-label="Monthly production chart">
            {ticks.map((t) => (
              <g key={t}>
                <line
                  x1={MARGIN.left}
                  x2={width - MARGIN.right}
                  y1={y(t)}
                  y2={y(t)}
                  stroke="#e2e8f0"
                  strokeWidth={1}
                />
                <text
                  x={MARGIN.left - 6}
                  y={y(t)}
                  textAnchor="end"
                  dominantBaseline="middle"
                  className="fill-slate-500 text-[11px] tabular-nums"
                >
                  {compact(t)}
                </text>
              </g>
            ))}
            {monthlyKwh.map((kwh, i) => {
              const cx = MARGIN.left + band * i + band / 2;
              const h = Math.max(y(0) - y(kwh), 0);
              return (
                <g
                  key={i}
                  tabIndex={0}
                  role="img"
                  aria-label={`${FULL_MONTHS[i]}: ${formatKwh(kwh)}`}
                  className="outline-none"
                  onPointerEnter={() => setActive(i)}
                  onPointerLeave={() => setActive(null)}
                  onFocus={() => setActive(i)}
                  onBlur={() => setActive(null)}
                >
                  {/* Hit target: the whole band, taller than the mark. */}
                  <rect
                    x={MARGIN.left + band * i}
                    y={MARGIN.top}
                    width={band}
                    height={plotH}
                    fill="transparent"
                  />
                  <path
                    d={columnPath(cx - barW / 2, y(kwh), barW, h)}
                    fill={active === i ? BAR_ACTIVE : BAR}
                  />
                  <text
                    x={cx}
                    y={HEIGHT - 6}
                    textAnchor="middle"
                    className={`text-[11px] ${active === i ? "fill-slate-900" : "fill-slate-500"}`}
                  >
                    {width < 420 ? MONTHS[i][0] : MONTHS[i]}
                  </text>
                  {i === peak && active === null && (
                    <text
                      x={cx}
                      y={y(kwh) - 6}
                      textAnchor="middle"
                      className="fill-slate-700 text-[11px] font-medium tabular-nums"
                    >
                      {compact(kwh)}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        )}
        {active !== null && width > 0 && (
          <div
            role="tooltip"
            className="pointer-events-none absolute rounded-md border border-slate-200 bg-white px-2 py-1 text-xs shadow-sm"
            style={{
              left: Math.min(
                Math.max(MARGIN.left + band * active + band / 2 - 60, 0),
                width - 120,
              ),
              top: Math.max(y(monthlyKwh[active]) - 46, 0),
              width: 120,
            }}
          >
            <div className="font-semibold text-slate-900 tabular-nums">
              {formatKwh(monthlyKwh[active])}
            </div>
            <div className="flex items-center gap-1.5 text-slate-500">
              <span className="inline-block h-0.5 w-3" style={{ background: BAR }} />
              {FULL_MONTHS[active]}
            </div>
          </div>
        )}
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-slate-600">Show as table</summary>
        <table className="mt-2 w-full max-w-xs text-left text-sm">
          <thead>
            <tr className="text-slate-500">
              <th className="py-1 font-medium">Month</th>
              <th className="py-1 text-right font-medium">kWh</th>
            </tr>
          </thead>
          <tbody className="tabular-nums text-slate-700">
            {monthlyKwh.map((kwh, i) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="py-1">{FULL_MONTHS[i]}</td>
                <td className="py-1 text-right">{Math.round(kwh).toLocaleString("en-US")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
