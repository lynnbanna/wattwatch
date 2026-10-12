import { ApiStatus } from "@/components/ApiStatus";

const journey = [
  "Upload rooftop image",
  "Analyze roof",
  "Estimate usable area",
  "Configure solar and battery",
  "Compare costs and savings",
  "Save or share a report",
];

export default function Home() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-4xl font-bold tracking-tight text-slate-900">
        WattWatch
      </h1>
      <p className="mt-3 text-lg text-slate-600">
        Rooftop computer vision, solar estimation, and household energy
        financial modeling, with every assumption shown.
      </p>

      <section className="mt-10">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-700">
          Core journey
        </h2>
        <ol className="mt-3 space-y-2">
          {journey.map((step, i) => (
            <li key={step} className="flex gap-3 text-slate-700">
              <span className="font-mono text-slate-400">{i + 1}.</span>
              {step}
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-10 rounded-lg border border-slate-200 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-teal-700">
          System status
        </h2>
        <ApiStatus />
      </section>
    </main>
  );
}
