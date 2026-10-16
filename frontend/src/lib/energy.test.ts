import { describe, expect, it } from "vitest";
import {
  ampsToKw,
  comparisonRows,
  DEFAULT_ENERGY_FORM,
  formFromStudy,
  payback,
  rangeTicks,
  requestFromEnergyForm,
  usd,
  type EnergyForm,
  type EnergyStudy,
} from "./energy";

const filled: EnergyForm = {
  ...DEFAULT_ENERGY_FORM,
  monthlyKwh: Array(12).fill("350"),
  gridHours: "6",
  generatorAmps: "10",
  gridPrice: "0.27",
  generatorPrice: "0.45",
  solarCostPerKwp: "600",
  batteryCostPerKwh: "250",
};

describe("requestFromEnergyForm", () => {
  it("refuses to run without the user's own prices", () => {
    const empty = requestFromEnergyForm({ ...filled, gridPrice: "" });
    expect(empty).toEqual({ error: "Grid price ($/kWh): enter a number between 0 and 5." });
  });

  it("converts amperes, percentages and text to the API's units", () => {
    const result = requestFromEnergyForm(filled);
    if (!("request" in result)) throw new Error(result.error);
    const r = result.request;
    expect(r.supply.generator_kw).toBeCloseTo(2.2);
    expect(r.household.monthly_kwh).toEqual(Array(12).fill(350));
    expect(r.finance).toEqual({
      years: 25,
      discount_rate: 0.08,
      price_escalation: 0.02,
      solar_degradation: 0.005,
      battery_life_years: 10,
    });
    expect(r.configurations.map((c) => [c.name, c.battery_kwh])).toEqual([
      ["Solar only", 0],
      ["Solar + battery", 10],
    ]);
  });

  it("needs some consumption and distinct option names", () => {
    expect(requestFromEnergyForm({ ...filled, monthlyKwh: Array(12).fill("0") })).toEqual({
      error: "Enter the household's consumption.",
    });
    const same = filled.configurations.map((c) => ({ ...c, name: "A" }));
    expect(requestFromEnergyForm({ ...filled, configurations: same })).toEqual({
      error: "Option names must be different.",
    });
  });
});

describe("formFromStudy", () => {
  it("restores a saved study's inputs", () => {
    const result = requestFromEnergyForm(filled);
    if (!("request" in result)) throw new Error(result.error);
    const study = { inputs: result.request } as EnergyStudy;
    expect(formFromStudy(study)).toEqual({
      ...filled,
      monthlyKwh: Array(12).fill("350"),
      gridFixed: "0",
      generatorFixed: "0",
    });
  });
});

describe("results helpers", () => {
  const energy = (gen: number) => ({ generator_to_load_kwh: gen }) as never;
  const finance = { energy_cost_usd_per_year: 100, simple_payback_years: 4.25 } as never;
  const study = {
    reference: [{ scenario: "baseline", energy: energy(3000), energy_cost_usd_per_year: 1700 }],
    results: [
      { configuration: { name: "A" }, scenarios: [{ scenario: "baseline", energy: energy(1), finance }] },
    ],
  } as unknown as EnergyStudy;

  it("puts the no-solar reference first and colours options by position", () => {
    const rows = comparisonRows(study, "baseline");
    expect(rows.map((r) => [r.name, r.color, r.energyCost])).toEqual([
      ["No solar", null, 1700],
      ["A", "#2a78d6", 100],
    ]);
  });

  it("formats money and payback", () => {
    expect(usd(11746.4)).toBe("$11,746");
    expect(usd(-1421)).toBe("−$1,421");
    expect(payback(finance)).toBe("4.3 years");
    expect(payback({ simple_payback_years: null } as never)).toBe("Never");
    expect(ampsToKw(10)).toBeCloseTo(2.2);
  });
});

describe("cash chart ticks", () => {
  it("cover the whole data range, rounding outward", () => {
    const t = rangeTicks(-5160, 27000);
    expect(t[0]).toBeLessThanOrEqual(-5160);
    expect(t[t.length - 1]).toBeGreaterThanOrEqual(27000);
    expect(t).toContain(0);
  });
});
