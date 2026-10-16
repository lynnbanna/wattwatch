import { apiErrorMessage, apiUrl } from "./api";

export type DailyShape = "evening_peak" | "home_all_day" | "flat";
export type ScenarioName = "optimistic" | "baseline" | "conservative";
export const SCENARIOS: ScenarioName[] = ["optimistic", "baseline", "conservative"];

export const DAILY_SHAPES: { value: DailyShape; label: string; hint: string }[] = [
  { value: "evening_peak", label: "Evening peak", hint: "Out during the day; most use after sunset" },
  { value: "home_all_day", label: "Home all day", hint: "Use spread through the day" },
  { value: "flat", label: "Even", hint: "The same every hour" },
];

/** Generator subscriptions in Lebanon are sold in amperes at about 220 V. */
export const GENERATOR_VOLTAGE = 220;
export const ampsToKw = (amps: number) => (amps * GENERATOR_VOLTAGE) / 1000;

export type Configuration = {
  name: string;
  solar: boolean;
  battery_kwh: number;
  battery_power_kw?: number | null;
  usable_fraction?: number;
  round_trip_efficiency?: number;
  charge_from_grid: boolean;
  policy: "backup_first" | "self_consumption";
};

export type EnergyStudyRequest = {
  household: { monthly_kwh: number[]; daily_shape: DailyShape };
  supply: { grid_hours_per_day: number; generator_kw: number };
  prices: {
    grid_usd_per_kwh: number;
    generator_usd_per_kwh: number;
    grid_fixed_usd_per_month: number;
    generator_fixed_usd_per_month: number;
  };
  costs: {
    solar_usd_per_kwp: number;
    battery_usd_per_kwh: number;
    installation_usd: number;
    maintenance_usd_per_year: number;
  };
  finance: {
    years: number;
    discount_rate: number;
    price_escalation: number;
    solar_degradation: number;
    battery_life_years: number;
  };
  configurations: Configuration[];
};

export type EnergyTotals = {
  demand_kwh: number;
  solar_kwh: number;
  solar_to_load_kwh: number;
  battery_to_load_kwh: number;
  grid_to_load_kwh: number;
  grid_to_battery_kwh: number;
  generator_to_load_kwh: number;
  unmet_kwh: number;
  unmet_hours: number;
  curtailed_kwh: number;
  solar_and_battery_share: number;
  solar_used_share: number;
  battery_cycles: number;
};

export type FinanceOut = {
  energy_cost_usd_per_year: number;
  upfront_usd: number;
  year1_savings_usd: number;
  simple_payback_years: number | null;
  payback_year: number | null;
  npv_usd: number;
  cumulative_usd: number[];
};

export type EnergyStudy = {
  created_at: string;
  design_outline_hash: string;
  design_stale: boolean;
  kwp: number;
  inputs: EnergyStudyRequest;
  scenarios: { name: ScenarioName; description: string }[];
  reference: { scenario: ScenarioName; energy: EnergyTotals; energy_cost_usd_per_year: number }[];
  results: {
    configuration: Configuration;
    kwp: number;
    scenarios: { scenario: ScenarioName; energy: EnergyTotals; finance: FinanceOut }[];
  }[];
  assumptions: string[];
  limitations: string[];
};

export async function createEnergyStudy(
  analysisId: string,
  body: EnergyStudyRequest,
  signal?: AbortSignal,
): Promise<EnergyStudy> {
  const res = await fetch(apiUrl(`analyses/${encodeURIComponent(analysisId)}/energy-study`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(apiErrorMessage(res.status, data));
  }
  return res.json();
}

// --- form ---------------------------------------------------------------------

export type ConfigForm = {
  name: string;
  solar: boolean;
  batteryKwh: string;
  chargeFromGrid: boolean;
  policy: Configuration["policy"];
};

export type EnergyForm = {
  monthlyKwh: string[];
  dailyShape: DailyShape;
  gridHours: string;
  generatorAmps: string;
  gridPrice: string;
  generatorPrice: string;
  gridFixed: string;
  generatorFixed: string;
  solarCostPerKwp: string;
  batteryCostPerKwh: string;
  installation: string;
  maintenance: string;
  years: string;
  discountPct: string;
  escalationPct: string;
  degradationPct: string;
  batteryLife: string;
  configurations: ConfigForm[];
};

/** Prices and costs start empty on purpose: WattWatch has no built-in tariff. */
export const DEFAULT_ENERGY_FORM: EnergyForm = {
  monthlyKwh: Array(12).fill(""),
  dailyShape: "evening_peak",
  gridHours: "",
  generatorAmps: "",
  gridPrice: "",
  generatorPrice: "",
  gridFixed: "0",
  generatorFixed: "0",
  solarCostPerKwp: "",
  batteryCostPerKwh: "",
  installation: "0",
  maintenance: "0",
  years: "25",
  discountPct: "8",
  escalationPct: "2",
  degradationPct: "0.5",
  batteryLife: "10",
  configurations: [
    { name: "Solar only", solar: true, batteryKwh: "0", chargeFromGrid: false, policy: "backup_first" },
    { name: "Solar + battery", solar: true, batteryKwh: "10", chargeFromGrid: false, policy: "backup_first" },
  ],
};

export const MAX_CONFIGURATIONS = 4;

function parse(text: string, min: number, max: number, what: string): number {
  const value = Number(text.trim().replace(",", "."));
  if (text.trim() === "" || !Number.isFinite(value) || value < min || value > max) {
    throw new Error(`${what}: enter a number between ${min} and ${max}.`);
  }
  return value;
}

export function requestFromEnergyForm(
  f: EnergyForm,
): { request: EnergyStudyRequest } | { error: string } {
  try {
    const monthly = f.monthlyKwh.map((m, i) =>
      parse(m, 0, 20_000, `Consumption for month ${i + 1} (kWh)`),
    );
    if (monthly.every((m) => m === 0)) throw new Error("Enter the household's consumption.");
    const names = f.configurations.map((c) => c.name.trim());
    if (names.some((n) => !n)) throw new Error("Give every option a name.");
    if (new Set(names).size !== names.length) throw new Error("Option names must be different.");
    if (!f.configurations.length) throw new Error("Add at least one option to compare.");
    return {
      request: {
        household: { monthly_kwh: monthly, daily_shape: f.dailyShape },
        supply: {
          grid_hours_per_day: parse(f.gridHours, 0, 24, "Grid hours per day"),
          generator_kw: ampsToKw(parse(f.generatorAmps, 0, 200, "Generator subscription (A)")),
        },
        prices: {
          grid_usd_per_kwh: parse(f.gridPrice, 0, 5, "Grid price ($/kWh)"),
          generator_usd_per_kwh: parse(f.generatorPrice, 0, 5, "Generator price ($/kWh)"),
          grid_fixed_usd_per_month: parse(f.gridFixed, 0, 1000, "Grid fixed fee ($/month)"),
          generator_fixed_usd_per_month: parse(
            f.generatorFixed, 0, 1000, "Generator fixed fee ($/month)",
          ),
        },
        costs: {
          solar_usd_per_kwp: parse(f.solarCostPerKwp, 0, 10_000, "Solar cost ($/kWp)"),
          battery_usd_per_kwh: parse(f.batteryCostPerKwh, 0, 5_000, "Battery cost ($/kWh)"),
          installation_usd: parse(f.installation, 0, 1_000_000, "Installation ($)"),
          maintenance_usd_per_year: parse(f.maintenance, 0, 100_000, "Maintenance ($/year)"),
        },
        finance: {
          years: Math.round(parse(f.years, 5, 40, "Years")),
          discount_rate: parse(f.discountPct, 0, 30, "Discount rate (%)") / 100,
          price_escalation: parse(f.escalationPct, -10, 20, "Price change (%/year)") / 100,
          solar_degradation: parse(f.degradationPct, 0, 3, "Panel ageing (%/year)") / 100,
          battery_life_years: Math.round(parse(f.batteryLife, 3, 25, "Battery life (years)")),
        },
        configurations: f.configurations.map((c, i) => ({
          name: names[i],
          solar: c.solar,
          battery_kwh: parse(c.batteryKwh, 0, 200, `Battery size for "${names[i]}" (kWh)`),
          charge_from_grid: c.chargeFromGrid,
          policy: c.policy,
        })),
      },
    };
  } catch (err) {
    return { error: (err as Error).message };
  }
}

export function formFromStudy(s: EnergyStudy): EnergyForm {
  const i = s.inputs;
  const pct = (v: number) => String(Math.round(v * 1000) / 10);
  return {
    monthlyKwh: i.household.monthly_kwh.map(String),
    dailyShape: i.household.daily_shape,
    gridHours: String(i.supply.grid_hours_per_day),
    generatorAmps: String(Math.round((i.supply.generator_kw * 1000) / GENERATOR_VOLTAGE * 10) / 10),
    gridPrice: String(i.prices.grid_usd_per_kwh),
    generatorPrice: String(i.prices.generator_usd_per_kwh),
    gridFixed: String(i.prices.grid_fixed_usd_per_month),
    generatorFixed: String(i.prices.generator_fixed_usd_per_month),
    solarCostPerKwp: String(i.costs.solar_usd_per_kwp),
    batteryCostPerKwh: String(i.costs.battery_usd_per_kwh),
    installation: String(i.costs.installation_usd),
    maintenance: String(i.costs.maintenance_usd_per_year),
    years: String(i.finance.years),
    discountPct: pct(i.finance.discount_rate),
    escalationPct: pct(i.finance.price_escalation),
    degradationPct: pct(i.finance.solar_degradation),
    batteryLife: String(i.finance.battery_life_years),
    configurations: i.configurations.map((c) => ({
      name: c.name,
      solar: c.solar,
      batteryKwh: String(c.battery_kwh),
      chargeFromGrid: c.charge_from_grid,
      policy: c.policy,
    })),
  };
}

// --- results ----------------------------------------------------------------------

/** Where the household's electricity comes from, in dispatch order. */
export const SOURCES = [
  { key: "solar_to_load_kwh", label: "Solar, used directly", color: "#2a78d6" },
  { key: "battery_to_load_kwh", label: "Battery", color: "#eb6834" },
  { key: "grid_to_load_kwh", label: "Grid", color: "#1baf7a" },
  { key: "generator_to_load_kwh", label: "Generator", color: "#eda100" },
  { key: "unmet_kwh", label: "Without power", color: "#e87ba4" },
] as const satisfies readonly { key: keyof EnergyTotals; label: string; color: string }[];

/** Configuration colours follow the configuration's position, never its rank. */
export const CONFIG_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"];

export type ComparisonRow = {
  name: string;
  color: string | null;
  energy: EnergyTotals;
  finance: FinanceOut | null;
  energyCost: number;
};

/** Rows for one scenario: the no-solar reference first, then each configuration. */
export function comparisonRows(study: EnergyStudy, scenario: ScenarioName): ComparisonRow[] {
  const ref = study.reference.find((r) => r.scenario === scenario)!;
  return [
    { name: "No solar", color: null, energy: ref.energy, finance: null, energyCost: ref.energy_cost_usd_per_year },
    ...study.results.map((r, i) => {
      const s = r.scenarios.find((x) => x.scenario === scenario)!;
      return {
        name: r.configuration.name,
        color: CONFIG_COLORS[i],
        energy: s.energy,
        finance: s.finance,
        energyCost: s.finance.energy_cost_usd_per_year,
      };
    }),
  ];
}

export function usd(value: number): string {
  const sign = value < 0 ? "−" : "";
  return `${sign}$${Math.round(Math.abs(value)).toLocaleString("en-US")}`;
}

export function payback(f: FinanceOut): string {
  if (f.simple_payback_years === null) return "Never";
  return `${f.simple_payback_years.toFixed(1)} years`;
}

/** Clean ticks whose range covers [min, max] (rounded outward on both ends). */
export function rangeTicks(min: number, max: number): number[] {
  const span = max - min || 1;
  const raw = span / 4;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw)!;
  const start = Math.floor(min / step) * step;
  const end = Math.ceil(max / step) * step;
  const out = [];
  for (let v = start; v <= end + step / 2; v += step) out.push(+v.toFixed(6));
  return out;
}
