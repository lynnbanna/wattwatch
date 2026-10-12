import Link from "next/link";
import { RoofAnalyzer } from "@/components/RoofAnalyzer";

export const metadata = { title: "Analyze a roof · WattWatch" };

export default function AnalyzePage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-16">
      <Link href="/" className="text-sm text-teal-700 hover:underline">
        ← WattWatch
      </Link>
      <h1 className="mt-4 text-3xl font-bold tracking-tight text-slate-900">Analyze a roof</h1>
      <p className="mt-2 text-slate-600">
        Upload a rooftop image to see the detected roof outline and obstacles, with the
        model&apos;s confidence and limitations.
      </p>
      <div className="mt-8">
        <RoofAnalyzer />
      </div>
    </main>
  );
}
