"use client";

import { useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "@/lib/api";

type State =
  | { kind: "loading" }
  | { kind: "ok"; health: HealthResponse }
  | { kind: "error"; message: string };

export function ApiStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((health) => setState({ kind: "ok", health }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : "Unknown error",
        });
      });
    return () => controller.abort();
  }, []);

  if (state.kind === "loading") {
    return <p className="text-sm text-slate-500">Checking API…</p>;
  }
  if (state.kind === "error") {
    return (
      <p className="text-sm text-red-600">
        API unreachable: {state.message}
      </p>
    );
  }
  const { health } = state;
  return (
    <dl className="grid grid-cols-3 gap-4 text-sm">
      <div>
        <dt className="text-slate-500">API</dt>
        <dd className="font-medium">{health.status}</dd>
      </div>
      <div>
        <dt className="text-slate-500">Database</dt>
        <dd className="font-medium">{health.database}</dd>
      </div>
      <div>
        <dt className="text-slate-500">Version</dt>
        <dd className="font-medium">{health.version}</dd>
      </div>
    </dl>
  );
}
