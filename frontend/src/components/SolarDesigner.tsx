"use client";

import { useRef, useState } from "react";
import {
  createSolarDesign,
  DEFAULT_FORM,
  formatKwh,
  formFromDesign,
  LEBANESE_CITIES,
  requestFromForm,
  type SolarDesign,
  type SolarForm,
} from "@/lib/solar";
import { BUTTON } from "./EditToolbar";
import { MonthlyProductionChart } from "./MonthlyProductionChart";

type Props = {
  analysisId: string;
  design: SolarDesign | null;
  stale: boolean;
  outlinesSaving: boolean;
  onDesign: (design: SolarDesign) => void;
};

export function SolarDesigner({ analysisId, design, stale, outlinesSaving, onDesign }: Props) {
  const [form, setForm] = useState<SolarForm>(() => (design ? formFromDesign(design) : DEFAULT_FORM));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const set = (patch: Partial<SolarForm>) => setForm((f) => ({ ...f, ...patch }));

  function estimate() {
    const parsed = requestFromForm(form);
    if ("error" in parsed) return setError(parsed.error);
    setError(null);
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setBusy(true);
    createSolarDesign(analysisId, parsed.request, controller.signal)
      .then(onDesign)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Could not estimate production");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
  }

  return (
    <section className="space-y-5 border-t border-slate-200 pt-6">
      <div>
        <h2 className="text-xl font-semibold text-slate-900">Solar production</h2>
        <p className="mt-1 text-sm text-slate-600">
          Fit panels into the usable roof area and estimate how much electricity they would
          produce, using long-term satellite solar data for the location.
        </p>
      </div>

      <div className="space-y-4 rounded-lg border border-slate-200 p-4 text-sm">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Location">
            <select
              value={form.place}
              onChange={(e) => set({ place: e.target.value })}
              className={INPUT}
            >
              {LEBANESE_CITIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
              <option value="coordinates">Enter coordinates…</option>
            </select>
          </Field>
          {form.place === "coordinates" && (
            <div className="grid grid-cols-2 gap-2">
              <Field label="Latitude">
                <Text value={form.lat} onChange={(v) => set({ lat: v })} />
              </Field>
              <Field label="Longitude">
                <Text value={form.lon} onChange={(v) => set({ lon: v })} />
              </Field>
            </div>
          )}
        </div>
        <p className="text-xs text-slate-500">
          A nearby city is accurate enough: solar resource changes little over a few kilometres,
          and the home&apos;s exact location is not needed.
        </p>

        <fieldset>
          <legend className="font-medium text-slate-700">Mounting</legend>
          <div className="mt-1 flex flex-wrap gap-4">
            <Radio
              checked={form.kind === "flat_tilted"}
              onChange={() => set({ kind: "flat_tilted", tilt: "25", azimuth: "0" })}
              label="Flat roof, tilted rows"
            />
            <Radio
              checked={form.kind === "flush"}
              onChange={() => set({ kind: "flush", tilt: "30", azimuth: "0" })}
              label="Pitched roof, panels flat on it"
            />
          </div>
        </fieldset>

        <div className="grid gap-3 sm:grid-cols-3">
          <Field label={form.kind === "flat_tilted" ? "Panel tilt (°)" : "Roof pitch (°)"}>
            <Text value={form.tilt} onChange={(v) => set({ tilt: v })} />
          </Field>
          <Field label="Facing (azimuth, °)">
            <Text value={form.azimuth} onChange={(v) => set({ azimuth: v })} />
          </Field>
          <Field label="Panel orientation">
            <select
              value={form.orientation}
              onChange={(e) => set({ orientation: e.target.value as SolarForm["orientation"] })}
              className={INPUT}
            >
              <option value="landscape">Landscape</option>
              <option value="portrait">Portrait</option>
            </select>
          </Field>
        </div>
        <p className="text-xs text-slate-500">
          Azimuth: 0 = south, −90 = east, 90 = west; the image top is taken as north. For Beirut
          the yearly optimum is about 29° facing south; lower tilts let rows sit closer together.
        </p>

        <details>
          <summary className="cursor-pointer font-medium text-slate-700">
            Panel and loss settings
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <Field label="Panel power (W)">
              <Text value={form.powerW} onChange={(v) => set({ powerW: v })} />
            </Field>
            <Field label="Panel length (m)">
              <Text value={form.lengthM} onChange={(v) => set({ lengthM: v })} />
            </Field>
            <Field label="Panel width (m)">
              <Text value={form.widthM} onChange={(v) => set({ widthM: v })} />
            </Field>
            <Field label="Soiling loss (%)">
              <Text value={form.soilingPct} onChange={(v) => set({ soilingPct: v })} />
            </Field>
            <Field label="Wiring loss (%)">
              <Text value={form.wiringPct} onChange={(v) => set({ wiringPct: v })} />
            </Field>
            <Field label="Mismatch loss (%)">
              <Text value={form.mismatchPct} onChange={(v) => set({ mismatchPct: v })} />
            </Field>
            <Field label="Shading loss (%)">
              <Text value={form.shadingPct} onChange={(v) => set({ shadingPct: v })} />
            </Field>
            <Field label="Availability loss (%)">
              <Text value={form.availabilityPct} onChange={(v) => set({ availabilityPct: v })} />
            </Field>
            <Field label="Inverter efficiency (%)">
              <Text value={form.inverterPct} onChange={(v) => set({ inverterPct: v })} />
            </Field>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Defaults are typical industry values, not measurements from Lebanese installations.
            Raise soiling if panels are rarely cleaned and shading if the roof is shaded.
          </p>
        </details>

        {error && (
          <p role="alert" className="rounded-md bg-red-50 p-3 text-red-700">
            {error}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={estimate}
            disabled={busy || outlinesSaving}
            className={BUTTON}
          >
            {busy ? "Estimating…" : design ? "Recalculate" : "Estimate production"}
          </button>
          {outlinesSaving && (
            <span className="text-xs text-slate-500">Waiting for your outline changes to save…</span>
          )}
        </div>
      </div>

      {design && <DesignResults design={design} stale={stale} />}
    </section>
  );
}

function DesignResults({ design, stale }: { design: SolarDesign; stale: boolean }) {
  const { layout, production, resource } = design;
  return (
    <div className={`space-y-5 ${stale ? "opacity-60" : ""}`}>
      {stale && (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          The roof outlines changed after this estimate. Recalculate to update the panels and
          production.
        </p>
      )}
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Panels" value={String(layout.panel_count)} />
        <Stat label="System size" value={`${layout.kwp.toFixed(1)} kWp`} />
        <Stat label="Per year" value={formatKwh(production.annual_kwh)} emphasis />
        <Stat
          label="Per kWp"
          value={`${Math.round(production.specific_yield_kwh_per_kwp).toLocaleString("en-US")} kWh`}
        />
      </dl>
      <p className="text-xs text-slate-500">
        Panels cover {Math.round(layout.panel_area_m2)} m² of the{" "}
        {Math.round(layout.usable_area_m2)} m² usable area. A
        typical year differs by about ±{formatKwh(production.year_to_year_sd_kwh)} from this
        long-term average.
      </p>

      {layout.panel_count > 0 && <MonthlyProductionChart monthlyKwh={production.monthly_kwh} />}

      <Notes title="Assumptions" items={design.assumptions} />
      <Notes title="Limitations" items={design.limitations} />
      <p className="text-xs text-slate-400">
        Solar data: {resource.database} {resource.years}. {resource.attribution}.
      </p>
    </div>
  );
}

const INPUT = "mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-slate-700">{label}</span>
      {children}
    </label>
  );
}

function Text({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="text"
      inputMode="decimal"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={INPUT}
    />
  );
}

function Radio(props: { checked: boolean; onChange: () => void; label: string }) {
  return (
    <label className="flex items-center gap-2">
      <input type="radio" name="mounting" checked={props.checked} onChange={props.onChange} />
      <span className="text-slate-700">{props.label}</span>
    </label>
  );
}

function Stat({ label, value, emphasis }: { label: string; value: string; emphasis?: boolean }) {
  return (
    <div className={`rounded-lg border p-3 ${emphasis ? "border-sky-300 bg-sky-50" : "border-slate-200"}`}>
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-xl font-semibold text-slate-900">{value}</dd>
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
