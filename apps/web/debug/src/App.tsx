import { useMemo, useState } from "react";

import { CopyForChatgptButton } from "./components/CopyForChatgptButton";
import { ErrorBanner } from "./components/ErrorBanner";
import { FoldableJson } from "./components/FoldableJson";
import { debugGet } from "./lib/debugApiClient";
import { normalizeError } from "./lib/normalizeError";
import type { DebugSummary } from "./lib/summary";

const NAV_ITEMS = [
  "Run Explorer",
  "Snapshot Inspector",
  "Recall Lab (Exa)",
  "Candidate Judge",
  "LLM Runs",
  "Golden Set Runner",
];

type RunEvent = {
  id: string;
  phase_name: string;
  status: string;
  message?: string | null;
  created_at: string;
};

type DebugRun = {
  id: string;
  status: string;
  source_url?: string | null;
  agent_version?: string | null;
  created_at: string;
  updated_at: string;
  events: RunEvent[];
};

type DebugArtifact = Record<string, unknown>;

const formatDuration = (start: string, end: string) => {
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) {
    return "n/a";
  }
  const diffSec = Math.max(0, Math.round((endMs - startMs) / 1000));
  return `${diffSec}s`;
};

export default function App() {
  const [runIdInput, setRunIdInput] = useState("");
  const [run, setRun] = useState<DebugRun | null>(null);
  const [toolRunId, setToolRunId] = useState("");
  const [llmRunId, setLlmRunId] = useState("");
  const [toolRun, setToolRun] = useState<DebugArtifact | null>(null);
  const [llmRun, setLlmRun] = useState<DebugArtifact | null>(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<ReturnType<typeof normalizeError>[]>([]);

  const summary = useMemo<DebugSummary>(() => {
    if (!run) {
      return { errors };
    }
    return {
      runId: run.id,
      status: run.status,
      agentVersion: run.agent_version ?? undefined,
      createdAt: run.created_at,
      updatedAt: run.updated_at,
      phases: run.events.map((event) => ({
        name: event.phase_name,
        status: event.status,
        message: event.message ?? undefined,
      })),
      errors,
      notes: run.source_url ? [`source_url: ${run.source_url}`] : undefined,
    };
  }, [run, errors]);

  const fetchRun = async () => {
    if (!runIdInput) {
      return;
    }
    setLoading(true);
    setErrors([]);
    try {
      const data = await debugGet<DebugRun>(`/v1/debug/compare-runs/${runIdInput}`);
      setRun(data);
    } catch (error) {
      setErrors([normalizeError(error)]);
      setRun(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchToolRun = async () => {
    if (!toolRunId) {
      return;
    }
    setLoading(true);
    try {
      const data = await debugGet<DebugArtifact>(`/v1/debug/tool-runs/${toolRunId}`);
      setToolRun(data);
    } catch (error) {
      setErrors((prev) => [...prev, normalizeError(error)]);
      setToolRun(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchLlmRun = async () => {
    if (!llmRunId) {
      return;
    }
    setLoading(true);
    try {
      const data = await debugGet<DebugArtifact>(`/v1/debug/llm-runs/${llmRunId}`);
      setLlmRun(data);
    } catch (error) {
      setErrors((prev) => [...prev, normalizeError(error)]);
      setLlmRun(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <ErrorBanner errors={errors} />
      <div className="flex">
        <aside className="min-h-screen w-64 border-r border-slate-900 bg-slate-950 px-4 py-6">
          <div className="text-lg font-semibold text-slate-100">Debug Console</div>
          <div className="mt-6 space-y-2 text-sm">
            {NAV_ITEMS.map((item, index) => (
              <div
                key={item}
                className={`rounded-md px-3 py-2 ${
                  index === 0
                    ? "bg-slate-800 text-white"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {item}
              </div>
            ))}
          </div>
          <div className="mt-8 rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-xs text-slate-300">
            Listing endpoint not available yet. Use run_id to open a run.
          </div>
        </aside>
        <main className="flex-1 px-6 py-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-2xl font-semibold">Run Explorer</div>
              <div className="text-xs text-slate-400">
                Condensed view by default. Expand JSON only when needed.
              </div>
            </div>
            <CopyForChatgptButton summary={summary} />
          </div>

          <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <div className="text-sm font-semibold text-slate-200">Open run</div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                className="w-80 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                placeholder="run_id"
                value={runIdInput}
                onChange={(event) => setRunIdInput(event.target.value)}
              />
              <button
                onClick={fetchRun}
                className="rounded-md bg-slate-200 px-3 py-2 text-sm font-semibold text-slate-900"
                type="button"
              >
                {loading ? "Loading..." : "Open"}
              </button>
            </div>
          </section>

          {run ? (
            <section className="mt-6 grid gap-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <div className="text-xs uppercase text-slate-400">Run summary</div>
                    <div className="mt-1 text-lg font-semibold text-slate-100">{run.id}</div>
                    <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-300">
                      <span>Status: {run.status}</span>
                      <span>Created: {run.created_at}</span>
                      <span>Updated: {run.updated_at}</span>
                      <span>Duration: {formatDuration(run.created_at, run.updated_at)}</span>
                      {run.agent_version ? <span>Agent: {run.agent_version}</span> : null}
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-xs uppercase text-slate-400">Timeline</div>
                <div className="mt-3 space-y-2 text-sm">
                  {run.events.map((event) => (
                    <div
                      key={event.id}
                      className="rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="font-semibold text-slate-200">
                          {event.phase_name}
                        </div>
                        <div className="text-xs text-slate-400">{event.status}</div>
                      </div>
                      {event.message ? (
                        <div className="mt-1 text-xs text-slate-400">{event.message}</div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>

              <FoldableJson title="run_events (raw)" data={run.events} />

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                  <div className="text-xs uppercase text-slate-400">Tool run by id</div>
                  <div className="mt-3 flex gap-2">
                    <input
                      className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                      placeholder="tool_run_id"
                      value={toolRunId}
                      onChange={(event) => setToolRunId(event.target.value)}
                    />
                    <button
                      onClick={fetchToolRun}
                      className="rounded-md bg-slate-200 px-3 py-2 text-sm font-semibold text-slate-900"
                      type="button"
                    >
                      Fetch
                    </button>
                  </div>
                  {toolRun ? (
                    <div className="mt-3">
                      <FoldableJson title="tool_run (raw)" data={toolRun} />
                    </div>
                  ) : null}
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                  <div className="text-xs uppercase text-slate-400">LLM run by id</div>
                  <div className="mt-3 flex gap-2">
                    <input
                      className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                      placeholder="llm_run_id"
                      value={llmRunId}
                      onChange={(event) => setLlmRunId(event.target.value)}
                    />
                    <button
                      onClick={fetchLlmRun}
                      className="rounded-md bg-slate-200 px-3 py-2 text-sm font-semibold text-slate-900"
                      type="button"
                    >
                      Fetch
                    </button>
                  </div>
                  {llmRun ? (
                    <div className="mt-3">
                      <FoldableJson title="llm_run (raw)" data={llmRun} />
                    </div>
                  ) : null}
                </div>
              </div>
            </section>
          ) : (
            <section className="mt-6 rounded-xl border border-dashed border-slate-800 bg-slate-900/20 p-6 text-sm text-slate-400">
              No run loaded. Enter a run_id to view details. Large JSON stays hidden by
              default.
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
