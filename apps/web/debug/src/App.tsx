import { useEffect, useMemo, useState } from "react";

import { CopyForChatgptButton } from "./components/CopyForChatgptButton";
import { ErrorBanner } from "./components/ErrorBanner";
import { FoldableJson } from "./components/FoldableJson";
import { getCompareRunFull, getCompareRunSummary, listCompareRuns } from "./lib/debugApiClient";
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
  phase_name: string;
  status: string;
  message?: string | null;
  created_at: string;
};

type RunPhaseCounts = {
  ok: number;
  warning: number;
  error: number;
  skipped: number;
};

type RunErrorTop = {
  phase_name: string;
  status: string;
  message: string;
};

type CompareRunListItem = {
  run_id: string;
  created_at: string;
  status: string;
  source_url?: string | null;
  agent_version?: string | null;
  duration_ms?: number | null;
  phase_counts: RunPhaseCounts;
  error_top?: RunErrorTop | null;
};

type CompareRunListResponse = {
  items: CompareRunListItem[];
  next_cursor: string | null;
};

type RunRefs = {
  snapshot_ids: string[];
  tool_run_ids: string[];
  llm_run_ids: string[];
  prompt_ids: string[];
};

type CompareRunSummaryResponse = {
  item: CompareRunListItem;
  timeline: RunEvent[];
  refs: RunRefs;
};

type DebugRunFull = Record<string, unknown>;

export default function App() {
  const [runs, setRuns] = useState<CompareRunListItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [summary, setSummary] = useState<CompareRunSummaryResponse | null>(null);
  const [fullRun, setFullRun] = useState<DebugRunFull | null>(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<ReturnType<typeof normalizeError>[]>([]);

  const debugSummary = useMemo<DebugSummary>(() => {
    if (!summary) {
      return { errors };
    }
    return {
      runId: summary.item.run_id,
      status: summary.item.status,
      agentVersion: summary.item.agent_version ?? undefined,
      createdAt: summary.item.created_at,
      sourceUrl: summary.item.source_url ?? undefined,
      phases: summary.timeline.map((event) => ({
        name: event.phase_name,
        status: event.status,
        message: event.message ?? undefined,
      })),
      phaseCounts: summary.item.phase_counts,
      errorTop: summary.item.error_top ?? undefined,
      refs: summary.refs,
      errors,
    };
  }, [summary, errors]);

  const fetchRuns = async (cursor?: string | null) => {
    setLoading(true);
    try {
      const data = await listCompareRuns(25, cursor);
      const response = data as CompareRunListResponse;
      if (cursor) {
        setRuns((prev) => [...prev, ...response.items]);
      } else {
        setRuns(response.items);
        if (response.items.length) {
          setSelectedRunId(response.items[0].run_id);
        }
      }
      setNextCursor(response.next_cursor);
    } catch (error) {
      setErrors((prev) => [...prev, normalizeError(error)]);
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async (runId: string) => {
    setLoading(true);
    setErrors([]);
    try {
      const data = await getCompareRunSummary(runId);
      setSummary(data as CompareRunSummaryResponse);
      setFullRun(null);
    } catch (error) {
      setErrors([normalizeError(error)]);
      setSummary(null);
      setFullRun(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchFull = async () => {
    if (!selectedRunId) {
      return;
    }
    setLoading(true);
    try {
      const data = await getCompareRunFull(selectedRunId);
      setFullRun(data as DebugRunFull);
    } catch (error) {
      setErrors((prev) => [...prev, normalizeError(error)]);
      setFullRun(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchRuns();
  }, []);

  useEffect(() => {
    if (selectedRunId) {
      void fetchSummary(selectedRunId);
    }
  }, [selectedRunId]);

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
            <CopyForChatgptButton summary={debugSummary} />
          </div>

          <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-slate-200">Latest runs</div>
              <button
                onClick={() => fetchRuns(nextCursor)}
                className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-200"
                type="button"
                disabled={!nextCursor || loading}
              >
                {nextCursor ? "Charger plus" : "Fin"}
              </button>
            </div>
            <div className="mt-3 space-y-2 text-xs">
              {runs.length === 0 ? (
                <div className="text-slate-400">No runs yet.</div>
              ) : (
                runs.map((item) => (
                  <button
                    key={item.run_id}
                    onClick={() => setSelectedRunId(item.run_id)}
                    className={`flex w-full flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2 text-left ${
                      selectedRunId === item.run_id
                        ? "border-emerald-500 bg-emerald-500/10"
                        : "border-slate-800 bg-slate-950/50"
                    }`}
                    type="button"
                  >
                    <div className="min-w-[260px] font-semibold text-slate-100">
                      {item.run_id}
                    </div>
                    <div className="text-slate-400">
                      {new Date(item.created_at).toLocaleString()}
                    </div>
                    <div className="text-slate-300">Status: {item.status}</div>
                    <div className="text-slate-400">
                      {item.source_url ? item.source_url : "source_url: n/a"}
                    </div>
                    <div className="flex gap-2 text-[11px] text-slate-300">
                      <span>ok {item.phase_counts.ok}</span>
                      <span>warn {item.phase_counts.warning}</span>
                      <span>err {item.phase_counts.error}</span>
                      <span>skip {item.phase_counts.skipped}</span>
                    </div>
                    {item.error_top ? (
                      <div className="text-xs text-red-300">
                        {item.error_top.phase_name}: {item.error_top.message}
                      </div>
                    ) : null}
                  </button>
                ))
              )}
            </div>
          </section>

          {summary ? (
            <section className="mt-6 grid gap-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <div className="text-xs uppercase text-slate-400">Run summary</div>
                    <div className="mt-1 text-lg font-semibold text-slate-100">
                      {summary.item.run_id}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-300">
                      <span>Status: {summary.item.status}</span>
                      <span>Created: {summary.item.created_at}</span>
                      <span>
                        Duration:{" "}
                        {summary.item.duration_ms !== null && summary.item.duration_ms !== undefined
                          ? `${summary.item.duration_ms}ms`
                          : "n/a"}
                      </span>
                      {summary.item.agent_version ? (
                        <span>Agent: {summary.item.agent_version}</span>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-xs uppercase text-slate-400">Timeline</div>
                <div className="mt-3 space-y-2 text-sm">
                  {summary.timeline.map((event, index) => (
                    <div
                      key={`${event.phase_name}-${event.created_at}-${index}`}
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

              <FoldableJson title="run_events (raw)" data={summary.timeline} />

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-xs uppercase text-slate-400">Refs</div>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-300">
                  <span>snapshots: {summary.refs.snapshot_ids.length}</span>
                  <span>tool_runs: {summary.refs.tool_run_ids.length}</span>
                  <span>llm_runs: {summary.refs.llm_run_ids.length}</span>
                  <span>prompts: {summary.refs.prompt_ids.length}</span>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-xs uppercase text-slate-400">JSON complet</div>
                  <button
                    onClick={fetchFull}
                    className="rounded-md bg-slate-200 px-3 py-1 text-xs font-semibold text-slate-900"
                    type="button"
                  >
                    Charger JSON complet
                  </button>
                </div>
                {fullRun ? (
                  <div className="mt-3">
                    <FoldableJson title="compare_run (full)" data={fullRun} />
                  </div>
                ) : null}
              </div>
            </section>
          ) : (
            <section className="mt-6 rounded-xl border border-dashed border-slate-800 bg-slate-900/20 p-6 text-sm text-slate-400">
              No run selected. Choose a run from the list to view details. Large JSON stays
              hidden by default.
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
