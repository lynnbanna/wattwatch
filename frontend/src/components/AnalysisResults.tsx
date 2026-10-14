import type { RoofAnalysisResponse } from "@/lib/api";
import { formatArea, formatLabel, formatScore } from "@/lib/overlay";

export function AnalysisResults({ result }: { result: RoofAnalysisResponse }) {
  const { measurements: m, roofs, obstacles } = result;
  return (
    <section className="space-y-5">
      {result.model.is_stub && (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          These shapes come from a placeholder model and do not reflect this image.
        </p>
      )}

      <dl className="grid gap-3 sm:grid-cols-3">
        <Stat label="Usable area" value={formatArea(m.usable_area_m2)} emphasis />
        <Stat label="Roof area" value={formatArea(m.roof_area_m2)} />
        <Stat label="Obstacles on roof" value={formatArea(m.obstacle_area_m2)} />
      </dl>
      <p className="text-xs text-slate-500">
        Usable area keeps {m.edge_setback_m} m from roof edges and {m.obstacle_clearance_m} m
        around obstacles. All areas are estimates; see the assumptions and limitations below.
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        <RegionList
          title="Roofs"
          swatch="bg-teal-400"
          rows={roofs.map((r) => ({
            label: formatLabel(r.label),
            detail: `${formatArea(r.area_m2)} · usable ${formatArea(r.usable_area_m2)}`,
            score: r.model_score,
          }))}
        />
        <RegionList
          title="Obstacles"
          swatch="bg-amber-400"
          rows={obstacles.map((o) => ({
            label: formatLabel(o.label),
            detail: formatArea(o.area_m2),
            score: o.model_score,
          }))}
        />
      </div>
      <p className="text-xs text-slate-500">{result.model_score_note}</p>

      <Notes title="Assumptions" items={result.assumptions} />
      <Notes title="Limitations" items={result.limitations} />

      <p className="text-xs text-slate-400">
        Model {result.model.name} v{result.model.version} · image {result.image.width_px}×
        {result.image.height_px} px · {(result.scale.gsd_m * 100).toPrecision(3)} cm per pixel
      </p>
    </section>
  );
}

function Stat({ label, value, emphasis }: { label: string; value: string; emphasis?: boolean }) {
  return (
    <div
      className={`rounded-lg border p-3 ${emphasis ? "border-teal-300 bg-teal-50" : "border-slate-200"}`}
    >
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold text-slate-900">{value}</dd>
    </div>
  );
}

function RegionList(props: {
  title: string;
  swatch: string;
  rows: { label: string; detail: string; score: number }[];
}) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
        <span className={`inline-block h-3 w-3 rounded-sm ${props.swatch}`} />
        {props.title}
      </h3>
      {props.rows.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">None detected</p>
      ) : (
        <ul className="mt-2 space-y-1 text-sm text-slate-700">
          {props.rows.map((row, i) => (
            <li key={i} className="flex justify-between gap-2">
              <span>
                {row.label} <span className="text-slate-500">{row.detail}</span>
              </span>
              <span className="whitespace-nowrap text-slate-500">
                model score {formatScore(row.score)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Notes({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-600">
        {items.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </div>
  );
}
