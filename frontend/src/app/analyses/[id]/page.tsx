import Link from "next/link";
import { AnalysisWorkspace } from "@/components/AnalysisWorkspace";

export const metadata = { title: "Roof analysis · WattWatch" };

export default async function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <main className="mx-auto max-w-3xl px-4 py-16">
      <Link href="/" className="text-sm text-teal-700 hover:underline">
        ← WattWatch
      </Link>
      <h1 className="mt-4 text-3xl font-bold tracking-tight text-slate-900">Roof analysis</h1>
      <div className="mt-8">
        <AnalysisWorkspace id={id} />
      </div>
    </main>
  );
}
