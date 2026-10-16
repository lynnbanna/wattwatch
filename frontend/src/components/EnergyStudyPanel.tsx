"use client";

import { useRef, useState } from "react";
import {
  ampsToKw,
  comparisonRows,
  createEnergyStudy,
  DAILY_SHAPES,
  DEFAULT_ENERGY_FORM,
  formFromStudy,
  MAX_CONFIGURATIONS,
  payback,
  requestFromEnergyForm,
  SCENARIOS,
  usd,
  type ConfigForm,
  type EnergyForm,
  type EnergyStudy,
  type ScenarioName,
} from "@/lib/energy";
import { MONTHS } from "@/lib/solar";
import { CumulativeCashChart } from "./CumulativeCashChart";
import { BUTTON, BUTTON_SECONDARY } from "./EditToolbar";
import { EnergySourcesChart } from "./EnergySourcesChart";

type Props = {
  analysisId: string;
  study: EnergyStudy | null;
  designStale: boolean;
  onStudy: (study: EnergyStudy) => void;
};

export function EnergyStudyPanel({ analysisId, study, designStale, onStudy }: Props) {
  const [form, setForm] = useState<EnergyForm>(() =>
    study ? formFromStudy(study) : DEFAULT_ENERGY_FORM,
  );
  const [average, setAverage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scenario, setScenario] = useState<ScenarioName>("baseline");
  const controllerRef = useRef<AbortController | null>(null);

  const set = (patch: Partial<EnergyForm>) => setForm((f) => ({ ...f, ...patch }));
  const setConfig = (i: number, patch: Partial<ConfigForm>) =>
    setForm((f) => ({
      ...f,
      configurations: f.configurations.map((c, j) => (j === i ? { ...c, ...patch } : c)),
    }));

  const annual = form.monthlyKwh.reduce((sum, m) => sum + (Number(m.replace(",", ".")) || 0), 0);
  const amps = Number(form.generatorAmps.replace(",", "."));

  function run() {
    const parsed = requestFromEnergyForm(form);
    if ("error" in parsed) return setError(parsed.error);
    setError(null);
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setBusy(true);
    createEnergyStudy(analysisId, parsed.request, controller.signal)
      .then(onStudy)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Could not run the comparison");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
  }

  return (
    <section className="space-y-5 border-t border-slate-200 pt-6">
      <div>
        <h2 className="text-xl font-semibold text-slate-900">Costs and savings</h2>
        <p className="mt-1 text-sm text-slate-600">
          Compare options for this roof against your current supply. Every hour of a typical year
          is simulated: solar first, then the battery, then the grid while it is on, then the
          generator.
        </p>
      </div>

      <div className="space-y-5 rounded-lg border border-slate-200 p-4 text-sm">
        <fieldset className="space-y-2">
          <legend className="font-semibold text-slate-800">1. Household electricity use</legend>
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Same every month (kWh)">
              <Text value={average} onChange={setAverage} />
            </Field>
            <button
              type="button"
              className={BUTTON_SECONDARY}
              onClick={() => average.trim() && set({ monthlyKwh: Array(12).fill(average.trim()) })}
            >
              Fill all months
            </button>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {MONTHS.map((m, i) => (
              <Field key={m} label={m}>
                <Text
                  value={form.monthlyKwh[i]}
                  onChange={(v) =>
                    set({ monthlyKwh: form.monthlyKwh.map((x, j) => (j === i ? v : x)) })
                  }
                />
              </Field>
            ))}
          </div>
          <p className="text-xs text-slate-500">
            {annual > 0 ? `${Math.round(annual).toLocaleString("en-US")} kWh a year. ` : ""}
            Use your bills; summer air conditioning often doubles use.
          </p>
          <Field label="When electricity is used">
            <select
              value={form.dailyShape}
              onChange={(e) => set({ dailyShape: e.target.value as EnergyForm["dailyShape"] })}
              className={INPUT}
            >
              {DAILY_SHAPES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}: {s.hint}
                </option>
              ))}
            </select>
          </Field>
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="font-semibold text-slate-800">2. Current supply and prices</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Grid (EDL) hours per day">
              <Text value={form.gridHours} onChange={(v) => set({ gridHours: v })} />
            </Field>
            <Field
              label={`Generator subscription (A)${amps > 0 ? ` ≈ ${ampsToKw(amps).toFixed(1)} kW` : ""}`}
            >
              <Text value={form.generatorAmps} onChange={(v) => set({ generatorAmps: v })} />
            </Field>
            <Field label="Grid price ($ per kWh)">
              <Text value={form.gridPrice} onChange={(v) => set({ gridPrice: v })} />
            </Field>
            <Field label="Generator price ($ per kWh)">
              <Text value={form.generatorPrice} onChange={(v) => set({ generatorPrice: v })} />
            </Field>
            <Field label="Grid fixed fee ($ per month)">
              <Text value={form.gridFixed} onChange={(v) => set({ gridFixed: v })} />
            </Field>
            <Field label="Generator fixed fee ($ per month)">
              <Text value={form.generatorFixed} onChange={(v) => set({ generatorFixed: v })} />
            </Field>
          </div>
          <p className="text-xs text-slate-500">
            WattWatch has no built-in tariff: enter the prices from your EDL bill and generator
            invoice. Fixed fees are paid with and without solar.
          </p>
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="font-semibold text-slate-800">3. Equipment costs</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Solar system ($ per kWp: panels, inverter, mounting)">
              <Text value={form.solarCostPerKwp} onChange={(v) => set({ solarCostPerKwp: v })} />
            </Field>
            <Field label="Battery ($ per kWh)">
              <Text value={form.batteryCostPerKwh} onChange={(v) => set({ batteryCostPerKwh: v })} />
            </Field>
            <Field label="Installation ($, one-off)">
              <Text value={form.installation} onChange={(v) => set({ installation: v })} />
            </Field>
            <Field label="Maintenance ($ per year)">
              <Text value={form.maintenance} onChange={(v) => set({ maintenance: v })} />
            </Field>
          </div>
          <p className="text-xs text-slate-500">Use installer quotes where you have them.</p>
          <details>
            <summary className="cursor-pointer text-slate-700">Long-term assumptions</summary>
            <div className="mt-2 grid gap-3 sm:grid-cols-3">
              <Field label="Years">
                <Text value={form.years} onChange={(v) => set({ years: v })} />
              </Field>
              <Field label="Discount rate (%)">
                <Text value={form.discountPct} onChange={(v) => set({ discountPct: v })} />
              </Field>
              <Field label="Energy price change (% per year)">
                <Text value={form.escalationPct} onChange={(v) => set({ escalationPct: v })} />
              </Field>
              <Field label="Panel ageing (% per year)">
                <Text value={form.degradationPct} onChange={(v) => set({ degradationPct: v })} />
              </Field>
              <Field label="Battery life (years)">
                <Text value={form.batteryLife} onChange={(v) => set({ batteryLife: v })} />
              </Field>
            </div>
          </details>
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="font-semibold text-slate-800">4. Options to compare</legend>
          {form.configurations.map((c, i) => (
            <div key={i} className="grid items-end gap-2 rounded-md bg-slate-50 p-2 sm:grid-cols-[1fr_7rem_auto_auto]">
              <Field label="Name">
                <Text value={c.name} onChange={(v) => setConfig(i, { name: v })} />
              </Field>
              <Field label="Battery (kWh)">
                <Text value={c.batteryKwh} onChange={(v) => setConfig(i, { batteryKwh: v })} />
              </Field>
              <div className="flex flex-col gap-1 pb-1 text-xs text-slate-700">
                <label className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={c.solar}
                    onChange={(e) => setConfig(i, { solar: e.target.checked })}
                  />
                  Solar panels
                </label>
                <label className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={c.chargeFromGrid}
                    onChange={(e) => setConfig(i, { chargeFromGrid: e.target.checked })}
                  />
                  Charge battery from grid
                </label>
              </div>
              <button
                type="button"
                className="pb-1 text-xs text-slate-500 hover:text-red-700 disabled:opacity-40"
                disabled={form.configurations.length <= 1}
                onClick={() =>
                  set({ configurations: form.configurations.filter((_, j) => j !== i) })
                }
              >
                Remove
              </button>
            </div>
          ))}
          <button
            type="button"
            className={BUTTON_SECONDARY}
            disabled={form.configurations.length >= MAX_CONFIGURATIONS}
            onClick={() =>
              set({
                configurations: [
                  ...form.configurations,
                  {
                    name: `Option ${form.configurations.length + 1}`,
                    solar: true,
                    batteryKwh: "5",
                    chargeFromGrid: false,
                    policy: "backup_first",
                  },
                ],
              })
            }
          >
            Add option
          </button>
          <p className="text-xs text-slate-500">
            Solar uses the panels from the estimate above. Batteries are kept for grid outages
            (they discharge only when the grid is off), because generator power usually costs
            more than grid power.
          </p>
        </fieldset>

        {error && (
          <p role="alert" className="rounded-md bg-red-50 p-3 text-red-700">
            {error}
          </p>
        )}
        <button type="button" onClick={run} disabled={busy} className={BUTTON}>
          {busy ? "Comparing…" : study ? "Compare again" : "Compare options"}
        </button>
      </div>

      {study && (
        <StudyResults
          study={study}
          scenario={scenario}
          setScenario={setScenario}
          designStale={designStale || study.design_stale}
          dimmed={busy}
        />
      )}
    </section>
  );
}

function StudyResults(props: {
  study: EnergyStudy;
  scenario: ScenarioName;
  setScenario: (s: ScenarioName) => void;
  designStale: boolean;
  dimmed: boolean;
}) {
  const { study, scenario } = props;
  const rows = comparisonRows(study, scenario);
  const description = study.scenarios.find((s) => s.name === scenario)?.description;
  return (
    <div className={`space-y-5 ${props.dimmed ? "opacity-60" : ""}`}>
      {props.designStale && (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          The solar estimate or roof outlines changed after this comparison. Re-estimate
          production, then compare again.
        </p>
      )}

      <div className="space-y-1">
        <div role="radiogroup" aria-label="Scenario" className="inline-flex rounded-md border border-slate-300 p-0.5 text-sm">
          {SCENARIOS.map((s) => (
            <button
              key={s}
              type="button"
              role="radio"
              aria-checked={scenario === s}
              onClick={() => props.setScenario(s)}
              className={`rounded px-3 py-1 capitalize ${scenario === s ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"}`}
            >
              {s}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-500">{description} Scenarios show sensitivity, not probability.</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead>
            <tr className="text-xs text-slate-500">
              <th className="py-2 pr-3 font-medium">Option</th>
              <th className="py-2 pr-3 text-right font-medium">Upfront</th>
              <th className="py-2 pr-3 text-right font-medium">Energy bills / year</th>
              <th className="py-2 pr-3 text-right font-medium">Saved in year 1</th>
              <th className="py-2 pr-3 text-right font-medium">Pays back in</th>
              <th className="py-2 pr-3 text-right font-medium">Net value over {study.inputs.finance.years} y</th>
              <th className="py-2 pr-3 text-right font-medium">Generator kWh / year</th>
              <th className="py-2 text-right font-medium">Hours without power</th>
            </tr>
          </thead>
          <tbody className="tabular-nums text-slate-700">
            {rows.map((r) => (
              <tr key={r.name} className="border-t border-slate-100">
                <td className="py-2 pr-3">
                  {r.name}
                </td>
                <td className="py-2 pr-3 text-right">{r.finance ? usd(r.finance.upfront_usd) : "—"}</td>
                <td className="py-2 pr-3 text-right">{usd(r.energyCost)}</td>
                <td className="py-2 pr-3 text-right">{r.finance ? usd(r.finance.year1_savings_usd) : "—"}</td>
                <td className="py-2 pr-3 text-right">{r.finance ? payback(r.finance) : "—"}</td>
                <td className="py-2 pr-3 text-right font-medium text-slate-900">
                  {r.finance ? usd(r.finance.npv_usd) : "—"}
                </td>
                <td className="py-2 pr-3 text-right">
                  {Math.round(r.energy.generator_to_load_kwh).toLocaleString("en-US")}
                </td>
                <td className="py-2 text-right">{r.energy.unmet_hours.toLocaleString("en-US")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">
        Net value is the {study.inputs.finance.discount_rate * 100}%-discounted sum of savings
        minus upfront, maintenance and battery replacements, compared with no solar.
      </p>

      <EnergySourcesChart rows={rows} />
      <CumulativeCashChart rows={rows} />

      <Notes title="Assumptions" items={study.assumptions} />
      <Notes title="Limitations" items={study.limitations} />
    </div>
  );
}

const INPUT = "mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block min-w-0">
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
