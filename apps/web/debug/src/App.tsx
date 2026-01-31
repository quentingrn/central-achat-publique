import { useEffect, useMemo, useState } from "react";

import { CopyForChatgptButton } from "./components/CopyForChatgptButton";
import { ErrorBanner } from "./components/ErrorBanner";
import { FoldableJson } from "./components/FoldableJson";
import {
  captureSnapshot,
  diffCompareRuns,
  getCompareRunFull,
  getCompareRunSummary,
  getSnapshot,
  listCompareRuns,
  listSnapshotsByUrl,
  recallExa,
} from "./lib/debugApiClient";
import { normalizeError } from "./lib/normalizeError";
import {
  buildChatGptDiffSummary,
  buildChatGptRecallSummary,
  buildChatGptSnapshotSummary,
} from "./lib/summary";
import type {
  DebugDiffSummary,
  DebugRecallSummary,
  DebugSnapshotSummary,
  DebugSummary,
} from "./lib/summary";

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

type RunFieldDiff = {
  left: string | null;
  right: string | null;
  severity: string;
};

type RunCountsDiff = {
  left: RunPhaseCounts;
  right: RunPhaseCounts;
  severity: string;
};

type RunErrorTopDiff = {
  left: RunErrorTop | null;
  right: RunErrorTop | null;
  severity: string;
};

type RunPhaseDiffItem = {
  phase_name: string;
  left_status: string | null;
  right_status: string | null;
  severity: string;
  left_message?: string | null;
  right_message?: string | null;
};

type RunRefSetDiff = {
  added_ids: string[];
  removed_ids: string[];
  common_count: number;
};

type RunRefsDiff = {
  snapshots: RunRefSetDiff;
  tool_runs: RunRefSetDiff;
  llm_runs: RunRefSetDiff;
  prompts: RunRefSetDiff;
};

type CompareRunDiffResponse = {
  left_run_id: string;
  right_run_id: string;
  left_created_at?: string | null;
  right_created_at?: string | null;
  status_diff: RunFieldDiff;
  source_url_diff: RunFieldDiff;
  agent_version_diff: RunFieldDiff;
  phase_counts: RunCountsDiff;
  error_top: RunErrorTopDiff;
  timeline: RunPhaseDiffItem[];
  refs: RunRefsDiff;
  notes?: string[];
};

type SnapshotLookup = {
  snapshot_id: string;
  run_id?: string | null;
  url: string;
  final_url?: string | null;
  provider: string;
  captured_at?: string | null;
  extraction_method?: string | null;
  extraction_status?: string | null;
  rules_version?: string | null;
  digest_hash?: string | null;
  http_status?: number | null;
  content_sha256?: string | null;
  content_size_bytes?: number | null;
  content_type?: string | null;
  missing_critical: string[];
  errors: Record<string, unknown>[];
};

type SnapshotGetResponse = {
  item: SnapshotLookup;
  extraction_v1?: Record<string, unknown> | null;
  digest_v1?: Record<string, unknown> | null;
  raw_extracted_json?: Record<string, unknown> | null;
};

type SnapshotByUrlListResponse = {
  items: SnapshotLookup[];
};

type SnapshotCaptureResponse = {
  snapshot_id: string;
  url: string;
  provider: string;
  status: string;
  summary: SnapshotGetResponse;
};

type ExaRecallRequest = {
  query: string;
  num_results: number;
  include_domains?: string[] | null;
  exclude_domains?: string[] | null;
  language?: string | null;
  country?: string | null;
  use_autoprompt?: boolean | null;
};

type ExaResultItem = {
  rank: number;
  title?: string | null;
  url: string;
  domain?: string | null;
  score?: number | null;
  snippet?: string | null;
  published_at?: string | null;
};

type ExaRecallResponse = {
  request: ExaRecallRequest;
  provider: string;
  took_ms?: number | null;
  items: ExaResultItem[];
  raw?: Record<string, unknown> | null;
  errors: Record<string, unknown>[];
  metrics: Record<string, unknown>;
};

const buildRecallStorageKey = (request: ExaRecallRequest) => {
  const normalized = {
    query: request.query,
    num_results: request.num_results,
    include_domains: request.include_domains ?? [],
    exclude_domains: request.exclude_domains ?? [],
    language: request.language ?? null,
    country: request.country ?? null,
    use_autoprompt: request.use_autoprompt ?? null,
  };
  const payload = JSON.stringify(normalized);
  try {
    return `recall:${btoa(unescape(encodeURIComponent(payload)))}`;
  } catch {
    return `recall:${payload}`;
  }
};

const loadRecallAnnotations = (key: string) => {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      return parsed as Record<string, { label: string; reason: string }>;
    }
  } catch {
    return {};
  }
  return {};
};

const saveRecallAnnotations = (
  key: string,
  value: Record<string, { label: string; reason: string }>
) => {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(value));
};

export default function App() {
  const [activeTab, setActiveTab] = useState(NAV_ITEMS[0]);
  const [runs, setRuns] = useState<CompareRunListItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [leftRunId, setLeftRunId] = useState<string | null>(null);
  const [rightRunId, setRightRunId] = useState<string | null>(null);
  const [summary, setSummary] = useState<CompareRunSummaryResponse | null>(null);
  const [fullRun, setFullRun] = useState<DebugRunFull | null>(null);
  const [diff, setDiff] = useState<CompareRunDiffResponse | null>(null);
  const [snapshotDetail, setSnapshotDetail] = useState<SnapshotGetResponse | null>(null);
  const [snapshotList, setSnapshotList] = useState<SnapshotLookup[]>([]);
  const [snapshotCapture, setSnapshotCapture] = useState<SnapshotCaptureResponse | null>(null);
  const [snapshotUrl, setSnapshotUrl] = useState("");
  const [snapshotIdQuery, setSnapshotIdQuery] = useState("");
  const [snapshotUrlQuery, setSnapshotUrlQuery] = useState("");
  const [captureProvider, setCaptureProvider] = useState("http");
  const [captureProofMode, setCaptureProofMode] = useState("none");
  const [captureScreenshot, setCaptureScreenshot] = useState(false);
  const [captureMaxBytes, setCaptureMaxBytes] = useState("");
  const [recallQuery, setRecallQuery] = useState("");
  const [recallNumResults, setRecallNumResults] = useState(10);
  const [recallIncludeDomains, setRecallIncludeDomains] = useState("");
  const [recallExcludeDomains, setRecallExcludeDomains] = useState("");
  const [recallLanguage, setRecallLanguage] = useState("");
  const [recallCountry, setRecallCountry] = useState("");
  const [recallAutoprompt, setRecallAutoprompt] = useState(false);
  const [recallResponse, setRecallResponse] = useState<ExaRecallResponse | null>(null);
  const [recallAnnotations, setRecallAnnotations] = useState<
    Record<string, { label: string; reason: string }>
  >({});
  const [recallExport, setRecallExport] = useState<Record<string, unknown> | null>(null);
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

  const diffSummaryText = useMemo(() => {
    if (!diff) {
      return null;
    }
    return buildChatGptDiffSummary(diff as DebugDiffSummary);
  }, [diff]);

  const snapshotSummaryText = useMemo(() => {
    if (!snapshotDetail) {
      return null;
    }
    const item = snapshotDetail.item;
    return buildChatGptSnapshotSummary({
      snapshotId: item.snapshot_id,
      url: item.url,
      finalUrl: item.final_url ?? undefined,
      provider: item.provider,
      status: snapshotCapture?.status ?? item.extraction_status ?? undefined,
      httpStatus: item.http_status ?? undefined,
      capturedAt: item.captured_at ?? undefined,
      extractionMethod: item.extraction_method ?? undefined,
      extractionStatus: item.extraction_status ?? undefined,
      rulesVersion: item.rules_version ?? undefined,
      digestHash: item.digest_hash ?? undefined,
      missingCritical: item.missing_critical,
      errors: item.errors,
    } as DebugSnapshotSummary);
  }, [snapshotDetail, snapshotCapture]);

  const recallSummaryText = useMemo(() => {
    if (!recallResponse) {
      return null;
    }
    return buildChatGptRecallSummary({
      query: recallResponse.request.query,
      numResults: recallResponse.request.num_results,
      includeDomains: recallResponse.request.include_domains ?? undefined,
      excludeDomains: recallResponse.request.exclude_domains ?? undefined,
      language: recallResponse.request.language ?? undefined,
      country: recallResponse.request.country ?? undefined,
      useAutoprompt: recallResponse.request.use_autoprompt ?? undefined,
      tookMs: recallResponse.took_ms ?? undefined,
      items: recallResponse.items.map((item) => ({
        title: item.title,
        url: item.url,
        domain: item.domain,
        score: item.score,
      })),
      metrics: recallResponse.metrics,
      errors: recallResponse.errors,
    } as DebugRecallSummary);
  }, [recallResponse]);

  const recallDuplicateUrls = useMemo(() => {
    if (!recallResponse) {
      return new Set<string>();
    }
    const counts = new Map<string, number>();
    recallResponse.items.forEach((item) => {
      counts.set(item.url, (counts.get(item.url) ?? 0) + 1);
    });
    const duplicates = new Set<string>();
    counts.forEach((count, url) => {
      if (count > 1) {
        duplicates.add(url);
      }
    });
    return duplicates;
  }, [recallResponse]);

  const recallTopDomains = useMemo(() => {
    if (!recallResponse) {
      return [] as { domain: string; count: number }[];
    }
    const topDomains = recallResponse.metrics?.["top_domains"];
    if (Array.isArray(topDomains)) {
      return topDomains.map((item) => ({
        domain: String(item.domain ?? "unknown"),
        count: Number(item.count ?? 0),
      }));
    }
    return [];
  }, [recallResponse]);

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

  const fetchDiff = async () => {
    if (!leftRunId || !rightRunId) {
      setErrors((prev) => [
        ...prev,
        normalizeError(new Error("Select left and right runs before comparing.")),
      ]);
      return;
    }
    setLoading(true);
    try {
      const data = await diffCompareRuns(leftRunId, rightRunId);
      setDiff(data as CompareRunDiffResponse);
    } catch (error) {
      setErrors((prev) => [...prev, normalizeError(error)]);
      setDiff(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchSnapshotById = async (snapshotId: string) => {
    setLoading(true);
    setErrors([]);
    try {
      const data = await getSnapshot(snapshotId);
      setSnapshotDetail(data as SnapshotGetResponse);
      setSnapshotCapture(null);
    } catch (error) {
      setErrors([normalizeError(error)]);
      setSnapshotDetail(null);
      setSnapshotCapture(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchSnapshotsByUrl = async () => {
    if (!snapshotUrlQuery.trim()) {
      setErrors([normalizeError(new Error("Provide a URL to search snapshots."))]);
      return;
    }
    setLoading(true);
    setErrors([]);
    try {
      const data = await listSnapshotsByUrl(snapshotUrlQuery.trim(), 10);
      const response = data as SnapshotByUrlListResponse;
      setSnapshotList(response.items);
    } catch (error) {
      setErrors([normalizeError(error)]);
      setSnapshotList([]);
    } finally {
      setLoading(false);
    }
  };

  const runSnapshotCapture = async () => {
    if (!snapshotUrl.trim()) {
      setErrors([normalizeError(new Error("Provide a URL to capture."))]);
      return;
    }
    setLoading(true);
    setErrors([]);
    try {
      const maxBytesValue = captureMaxBytes.trim()
        ? Number(captureMaxBytes.trim())
        : null;
      const payload = {
        url: snapshotUrl.trim(),
        provider: captureProvider || null,
        proof_mode: captureProofMode || null,
        screenshot_enabled: captureScreenshot ? true : null,
        max_bytes:
          maxBytesValue && Number.isFinite(maxBytesValue) ? Math.floor(maxBytesValue) : null,
      };
      const data = await captureSnapshot(payload);
      const response = data as SnapshotCaptureResponse;
      setSnapshotCapture(response);
      setSnapshotDetail(response.summary);
      setSnapshotIdQuery(response.snapshot_id);
      setSnapshotUrlQuery(response.summary.item.url);
    } catch (error) {
      setErrors([normalizeError(error)]);
      setSnapshotCapture(null);
      setSnapshotDetail(null);
    } finally {
      setLoading(false);
    }
  };

  const parseDomainList = (value: string) =>
    value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

  const runExaRecall = async () => {
    if (!recallQuery.trim()) {
      setErrors([normalizeError(new Error("Provide a query for recall."))]);
      return;
    }
    setLoading(true);
    setErrors([]);
    try {
      const includeDomains = parseDomainList(recallIncludeDomains);
      const excludeDomains = parseDomainList(recallExcludeDomains);
      const payload = {
        query: recallQuery.trim(),
        num_results: Math.min(20, Math.max(1, recallNumResults)),
        include_domains: includeDomains.length ? includeDomains : null,
        exclude_domains: excludeDomains.length ? excludeDomains : null,
        language: recallLanguage.trim() || null,
        country: recallCountry.trim() || null,
        use_autoprompt: recallAutoprompt ? true : null,
      };
      const data = await recallExa(payload);
      setRecallResponse(data as ExaRecallResponse);
      setRecallExport(null);
    } catch (error) {
      setErrors([normalizeError(error)]);
      setRecallResponse(null);
      setRecallExport(null);
    } finally {
      setLoading(false);
    }
  };

  const updateRecallAnnotation = (url: string, label: string) => {
    if (!recallStorageKey) {
      return;
    }
    const updated = {
      ...recallAnnotations,
      [url]: { label, reason: recallAnnotations[url]?.reason ?? "" },
    };
    setRecallAnnotations(updated);
    saveRecallAnnotations(recallStorageKey, updated);
  };

  const updateRecallReason = (url: string, reason: string) => {
    if (!recallStorageKey) {
      return;
    }
    const updated = {
      ...recallAnnotations,
      [url]: { label: recallAnnotations[url]?.label ?? "neutral", reason },
    };
    setRecallAnnotations(updated);
    saveRecallAnnotations(recallStorageKey, updated);
  };

  const exportRecallAnnotations = () => {
    if (!recallResponse || !recallStorageKey) {
      return;
    }
    setRecallExport({
      key: recallStorageKey,
      request: recallResponse.request,
      annotations: recallAnnotations,
    });
  };

  useEffect(() => {
    void fetchRuns();
  }, []);

  useEffect(() => {
    if (selectedRunId) {
      void fetchSummary(selectedRunId);
    }
  }, [selectedRunId]);

  const recallStorageKey = useMemo(() => {
    if (!recallResponse) {
      return null;
    }
    return buildRecallStorageKey(recallResponse.request);
  }, [recallResponse]);

  useEffect(() => {
    if (recallStorageKey) {
      setRecallAnnotations(loadRecallAnnotations(recallStorageKey));
    }
  }, [recallStorageKey]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <ErrorBanner errors={errors} />
      <div className="flex">
        <aside className="min-h-screen w-64 border-r border-slate-900 bg-slate-950 px-4 py-6">
          <div className="text-lg font-semibold text-slate-100">Debug Console</div>
          <div className="mt-6 space-y-2 text-sm">
            {NAV_ITEMS.map((item) => (
              <div
                key={item}
                className={`rounded-md px-3 py-2 ${
                  activeTab === item
                    ? "bg-slate-800 text-white"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <button
                  onClick={() => setActiveTab(item)}
                  className="w-full text-left"
                  type="button"
                >
                  {item}
                </button>
              </div>
            ))}
          </div>
          <div className="mt-8 rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-xs text-slate-300">
            Debug endpoints require DEBUG_API_ENABLED=1 + X-Debug-Token.
          </div>
        </aside>
        <main className="flex-1 px-6 py-8">
          {activeTab === "Run Explorer" ? (
            <>
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
                runs.map((item) => {
                  const isSelected = selectedRunId === item.run_id;
                  const isLeft = leftRunId === item.run_id;
                  const isRight = rightRunId === item.run_id;
                  return (
                    <div
                      key={item.run_id}
                      className={`flex w-full flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2 ${
                        isSelected ? "border-emerald-500 bg-emerald-500/10" : "border-slate-800"
                      }`}
                    >
                      <button
                        onClick={() => setSelectedRunId(item.run_id)}
                        className="min-w-[260px] text-left font-semibold text-slate-100"
                        type="button"
                      >
                        {item.run_id}
                      </button>
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
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setLeftRunId(item.run_id)}
                          className={`rounded-md px-2 py-1 text-[11px] ${
                            isLeft
                              ? "bg-emerald-300 text-emerald-950"
                              : "border border-slate-700 text-slate-200"
                          }`}
                          type="button"
                        >
                          L
                        </button>
                        <button
                          onClick={() => setRightRunId(item.run_id)}
                          className={`rounded-md px-2 py-1 text-[11px] ${
                            isRight
                              ? "bg-sky-300 text-sky-950"
                              : "border border-slate-700 text-slate-200"
                          }`}
                          type="button"
                        >
                          R
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </section>

          <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="text-xs uppercase text-slate-400">Diff mode</div>
                <div className="text-sm text-slate-200">
                  Left: {leftRunId ?? "n/a"} | Right: {rightRunId ?? "n/a"}
                </div>
              </div>
              <button
                onClick={fetchDiff}
                className="rounded-md bg-slate-200 px-3 py-2 text-sm font-semibold text-slate-900"
                type="button"
              >
                Comparer
              </button>
            </div>
          </section>

          {diff ? (
            <section className="mt-6 grid gap-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="text-xs uppercase text-slate-400">Diff summary</div>
                    <div className="mt-2 text-sm text-slate-200">
                      Left: {diff.left_run_id} ({diff.left_created_at ?? "n/a"})
                    </div>
                    <div className="text-sm text-slate-200">
                      Right: {diff.right_run_id} ({diff.right_created_at ?? "n/a"})
                    </div>
                  </div>
                  <CopyForChatgptButton textOverride={diffSummaryText ?? undefined} />
                </div>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-300">
                  <span>
                    Status: {diff.status_diff.left ?? "n/a"} →{" "}
                    {diff.status_diff.right ?? "n/a"}
                  </span>
                  <span>
                    Source: {diff.source_url_diff.left ?? "n/a"} →{" "}
                    {diff.source_url_diff.right ?? "n/a"}
                  </span>
                  <span>
                    Agent: {diff.agent_version_diff.left ?? "n/a"} →{" "}
                    {diff.agent_version_diff.right ?? "n/a"}
                  </span>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-xs uppercase text-slate-400">Phase counts</div>
                <div className="mt-2 grid gap-4 md:grid-cols-2 text-xs text-slate-300">
                  <div>
                    <div className="font-semibold text-slate-200">Left</div>
                    <div className="mt-1">
                      ok {diff.phase_counts.left.ok} / warn {diff.phase_counts.left.warning} /
                      err {diff.phase_counts.left.error} / skip {diff.phase_counts.left.skipped}
                    </div>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-200">Right</div>
                    <div className="mt-1">
                      ok {diff.phase_counts.right.ok} / warn {diff.phase_counts.right.warning} /
                      err {diff.phase_counts.right.error} / skip {diff.phase_counts.right.skipped}
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-xs uppercase text-slate-400">Top issues</div>
                <div className="mt-2 grid gap-4 md:grid-cols-2 text-xs text-slate-300">
                  <div>
                    <div className="font-semibold text-slate-200">Left</div>
                    <div className="mt-1">
                      {diff.error_top.left
                        ? `${diff.error_top.left.phase_name} (${diff.error_top.left.status}) ${diff.error_top.left.message}`
                        : "n/a"}
                    </div>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-200">Right</div>
                    <div className="mt-1">
                      {diff.error_top.right
                        ? `${diff.error_top.right.phase_name} (${diff.error_top.right.status}) ${diff.error_top.right.message}`
                        : "n/a"}
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-xs uppercase text-slate-400">Timeline diff</div>
                <div className="mt-3 space-y-2 text-xs text-slate-300">
                  {diff.timeline.map((item, index) => (
                    <div
                      key={`${item.phase_name}-${index}`}
                      className="rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="font-semibold text-slate-200">{item.phase_name}</div>
                        <div className="text-slate-400">
                          {item.left_status ?? "n/a"} → {item.right_status ?? "n/a"}
                        </div>
                        <div className="text-[10px] uppercase text-slate-500">
                          {item.severity}
                        </div>
                      </div>
                      {item.left_message || item.right_message ? (
                        <div className="mt-1 text-[11px] text-slate-400">
                          L: {item.left_message ?? "n/a"} | R:{" "}
                          {item.right_message ?? "n/a"}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-xs uppercase text-slate-400">Refs diff</div>
                <div className="mt-2 grid gap-3 text-xs text-slate-300 md:grid-cols-2">
                  <div>
                    snapshots +{diff.refs.snapshots.added_ids.length}/-
                    {diff.refs.snapshots.removed_ids.length} (common{" "}
                    {diff.refs.snapshots.common_count})
                  </div>
                  <div>
                    tool_runs +{diff.refs.tool_runs.added_ids.length}/-
                    {diff.refs.tool_runs.removed_ids.length} (common{" "}
                    {diff.refs.tool_runs.common_count})
                  </div>
                  <div>
                    llm_runs +{diff.refs.llm_runs.added_ids.length}/-
                    {diff.refs.llm_runs.removed_ids.length} (common{" "}
                    {diff.refs.llm_runs.common_count})
                  </div>
                  <div>
                    prompts +{diff.refs.prompts.added_ids.length}/-
                    {diff.refs.prompts.removed_ids.length} (common{" "}
                    {diff.refs.prompts.common_count})
                  </div>
                </div>
              </div>

              <FoldableJson title="diff (raw)" data={diff} />
            </section>
          ) : null}

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
            </>
          ) : null}

          {activeTab === "Snapshot Inspector" ? (
            <section className="space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="text-2xl font-semibold">Snapshot Inspector</div>
                  <div className="text-xs text-slate-400">
                    Condensed view by default. JSON is always folded.
                  </div>
                </div>
                <CopyForChatgptButton textOverride={snapshotSummaryText ?? undefined} />
              </div>

              <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-sm font-semibold text-slate-200">Capture URL</div>
                <div className="mt-3 grid gap-3 md:grid-cols-[2fr_1fr]">
                  <input
                    value={snapshotUrl}
                    onChange={(event) => setSnapshotUrl(event.target.value)}
                    placeholder="https://example.com/product"
                    className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                  />
                  <div className="flex gap-2">
                    <select
                      value={captureProvider}
                      onChange={(event) => setCaptureProvider(event.target.value)}
                      className="w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-slate-100"
                    >
                      <option value="http">http</option>
                      <option value="playwright_mcp">playwright_mcp</option>
                      <option value="stub">stub</option>
                    </select>
                    <button
                      onClick={runSnapshotCapture}
                      className="rounded-md bg-slate-200 px-3 py-2 text-xs font-semibold text-slate-900"
                      type="button"
                      disabled={loading}
                    >
                      Capturer
                    </button>
                  </div>
                </div>
                <div className="mt-3 grid gap-3 text-xs text-slate-300 md:grid-cols-3">
                  <label className="flex flex-col gap-1">
                    <span className="text-[11px] uppercase text-slate-500">proof mode</span>
                    <select
                      value={captureProofMode}
                      onChange={(event) => setCaptureProofMode(event.target.value)}
                      className="rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-slate-100"
                    >
                      <option value="none">none</option>
                      <option value="debug">debug</option>
                      <option value="audit">audit</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-[11px] uppercase text-slate-500">max bytes</span>
                    <input
                      value={captureMaxBytes}
                      onChange={(event) => setCaptureMaxBytes(event.target.value)}
                      placeholder="optional"
                      className="rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-slate-100"
                    />
                  </label>
                  <label className="flex items-center gap-2 text-xs text-slate-300">
                    <input
                      type="checkbox"
                      checked={captureScreenshot}
                      onChange={(event) => setCaptureScreenshot(event.target.checked)}
                    />
                    screenshot
                  </label>
                </div>
                {snapshotCapture ? (
                  <div className="mt-3 rounded-md border border-slate-800 bg-slate-950/70 p-3 text-xs text-slate-200">
                    <div>
                      snapshot_id: <span className="text-slate-100">{snapshotCapture.snapshot_id}</span>
                    </div>
                    <div>status: {snapshotCapture.status}</div>
                    <div>provider: {snapshotCapture.provider}</div>
                  </div>
                ) : null}
              </section>

              <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-sm font-semibold text-slate-200">Lookup</div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <div className="space-y-2">
                    <div className="text-xs uppercase text-slate-500">By snapshot_id</div>
                    <div className="flex gap-2">
                      <input
                        value={snapshotIdQuery}
                        onChange={(event) => setSnapshotIdQuery(event.target.value)}
                        placeholder="snapshot UUID"
                        className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100"
                      />
                      <button
                        onClick={() => fetchSnapshotById(snapshotIdQuery.trim())}
                        className="rounded-md border border-slate-700 px-3 py-2 text-xs text-slate-200"
                        type="button"
                      >
                        Ouvrir
                      </button>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="text-xs uppercase text-slate-500">By URL</div>
                    <div className="flex gap-2">
                      <input
                        value={snapshotUrlQuery}
                        onChange={(event) => setSnapshotUrlQuery(event.target.value)}
                        placeholder="https://example.com/product"
                        className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100"
                      />
                      <button
                        onClick={fetchSnapshotsByUrl}
                        className="rounded-md border border-slate-700 px-3 py-2 text-xs text-slate-200"
                        type="button"
                      >
                        Rechercher
                      </button>
                    </div>
                  </div>
                </div>
                {snapshotList.length ? (
                  <div className="mt-4 space-y-2 text-xs text-slate-300">
                    {snapshotList.map((item) => (
                      <button
                        key={item.snapshot_id}
                        onClick={() => fetchSnapshotById(item.snapshot_id)}
                        className="w-full rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2 text-left hover:border-slate-600"
                        type="button"
                      >
                        <div className="font-semibold text-slate-200">{item.snapshot_id}</div>
                        <div className="text-slate-400">
                          {item.captured_at ?? "n/a"} — {item.provider}
                        </div>
                        <div className="text-slate-400">{item.url}</div>
                      </button>
                    ))}
                  </div>
                ) : null}
              </section>

              {snapshotDetail ? (
                <section className="space-y-4">
                  {snapshotDetail.item.errors.length ? (
                    <div className="rounded-xl border border-red-900 bg-red-950/40 p-4 text-xs text-red-100">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-sm font-semibold text-red-200">Snapshot errors</div>
                          <ul className="mt-2 space-y-1">
                            {snapshotDetail.item.errors.map((error, index) => (
                              <li key={`snap-error-${index}`}>
                                {typeof error["code"] === "string" ? `[${error["code"]}] ` : ""}
                                {typeof error["message"] === "string" ? error["message"] : "error"}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <button
                          onClick={() =>
                            navigator.clipboard.writeText(
                              JSON.stringify(snapshotDetail.item.errors, null, 2)
                            )
                          }
                          className="rounded-md bg-red-200 px-3 py-2 text-xs font-semibold text-red-950"
                          type="button"
                        >
                          📋 Copier erreur brute
                        </button>
                      </div>
                    </div>
                  ) : null}

                  <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                    <div className="text-xs uppercase text-slate-400">Snapshot summary</div>
                    <div className="mt-2 text-sm font-semibold text-slate-100">
                      {snapshotDetail.item.snapshot_id}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-300">
                      <span>Provider: {snapshotDetail.item.provider}</span>
                      <span>Status: {snapshotCapture?.status ?? snapshotDetail.item.extraction_status ?? "n/a"}</span>
                      <span>Captured: {snapshotDetail.item.captured_at ?? "n/a"}</span>
                      <span>HTTP: {snapshotDetail.item.http_status ?? "n/a"}</span>
                      <span>Method: {snapshotDetail.item.extraction_method ?? "n/a"}</span>
                      <span>Extract: {snapshotDetail.item.extraction_status ?? "n/a"}</span>
                      {snapshotDetail.item.digest_hash ? (
                        <span>digest: {snapshotDetail.item.digest_hash}</span>
                      ) : null}
                    </div>
                    <div className="mt-2 text-xs text-slate-400">
                      url: {snapshotDetail.item.url}
                    </div>
                    {snapshotDetail.item.final_url ? (
                      <div className="text-xs text-slate-400">
                        final_url: {snapshotDetail.item.final_url}
                      </div>
                    ) : null}
                    {snapshotDetail.item.missing_critical.length ? (
                      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-200">
                        {snapshotDetail.item.missing_critical.map((item) => (
                          <span
                            key={item}
                            className="rounded-full border border-slate-700 px-2 py-1"
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <FoldableJson title="extraction_v1" data={snapshotDetail.extraction_v1} />
                  <FoldableJson title="digest_v1" data={snapshotDetail.digest_v1} />
                  <FoldableJson
                    title="raw_extracted_json"
                    data={snapshotDetail.raw_extracted_json}
                  />
                  <FoldableJson title="errors_json" data={snapshotDetail.item.errors} />
                </section>
              ) : (
                <section className="rounded-xl border border-dashed border-slate-800 bg-slate-900/20 p-6 text-sm text-slate-400">
                  No snapshot selected. Capture a URL or lookup a snapshot_id.
                </section>
              )}
            </section>
          ) : null}

          {activeTab === "Recall Lab (Exa)" ? (
            <section className="space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="text-2xl font-semibold">Recall Lab (Exa)</div>
                  <div className="text-xs text-slate-400">
                    Debug recall relevance and diversity. Annotations stored in localStorage only.
                  </div>
                </div>
                <CopyForChatgptButton textOverride={recallSummaryText ?? undefined} />
              </div>

              <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-sm font-semibold text-slate-200">Recall parameters</div>
                <div className="mt-3 grid gap-3">
                  <textarea
                    value={recallQuery}
                    onChange={(event) => setRecallQuery(event.target.value)}
                    placeholder="Query (brand + model + attributes)"
                    className="min-h-[96px] w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                  />
                  <div className="grid gap-3 text-xs text-slate-300 md:grid-cols-3">
                    <label className="flex flex-col gap-1">
                      <span className="text-[11px] uppercase text-slate-500">num results</span>
                      <input
                        type="number"
                        min={1}
                        max={20}
                        value={recallNumResults}
                        onChange={(event) => setRecallNumResults(Number(event.target.value))}
                        className="rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-slate-100"
                      />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="text-[11px] uppercase text-slate-500">include domains</span>
                      <input
                        value={recallIncludeDomains}
                        onChange={(event) => setRecallIncludeDomains(event.target.value)}
                        placeholder="example.com, example.org"
                        className="rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-slate-100"
                      />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="text-[11px] uppercase text-slate-500">exclude domains</span>
                      <input
                        value={recallExcludeDomains}
                        onChange={(event) => setRecallExcludeDomains(event.target.value)}
                        placeholder="ads.example.com"
                        className="rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-slate-100"
                      />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="text-[11px] uppercase text-slate-500">language</span>
                      <input
                        value={recallLanguage}
                        onChange={(event) => setRecallLanguage(event.target.value)}
                        placeholder="fr"
                        className="rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-slate-100"
                      />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="text-[11px] uppercase text-slate-500">country</span>
                      <input
                        value={recallCountry}
                        onChange={(event) => setRecallCountry(event.target.value)}
                        placeholder="FR"
                        className="rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-slate-100"
                      />
                    </label>
                    <label className="flex items-center gap-2 text-xs text-slate-300">
                      <input
                        type="checkbox"
                        checked={recallAutoprompt}
                        onChange={(event) => setRecallAutoprompt(event.target.checked)}
                      />
                      use autoprompt
                    </label>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      onClick={runExaRecall}
                      className="rounded-md bg-slate-200 px-3 py-2 text-xs font-semibold text-slate-900"
                      type="button"
                      disabled={loading}
                    >
                      Lancer recall
                    </button>
                    <button
                      onClick={exportRecallAnnotations}
                      className="rounded-md border border-slate-700 px-3 py-2 text-xs text-slate-200"
                      type="button"
                      disabled={!recallResponse}
                    >
                      Export annotations (json)
                    </button>
                  </div>
                </div>
              </section>

              {recallResponse ? (
                <section className="space-y-4">
                  {recallResponse.errors.length ? (
                    <div className="rounded-xl border border-red-900 bg-red-950/40 p-4 text-xs text-red-100">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-sm font-semibold text-red-200">Recall errors</div>
                          <ul className="mt-2 space-y-1">
                            {recallResponse.errors.map((error, index) => (
                              <li key={`recall-error-${index}`}>
                                {typeof error["kind"] === "string"
                                  ? `[${error["kind"]}] `
                                  : ""}
                                {typeof error["message"] === "string"
                                  ? error["message"]
                                  : "error"}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <button
                          onClick={() =>
                            navigator.clipboard.writeText(
                              JSON.stringify(recallResponse.errors, null, 2)
                            )
                          }
                          className="rounded-md bg-red-200 px-3 py-2 text-xs font-semibold text-red-950"
                          type="button"
                        >
                          📋 Copier erreur brute
                        </button>
                      </div>
                    </div>
                  ) : null}

                  <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-300">
                    <div className="flex flex-wrap gap-4">
                      <span>provider: {recallResponse.provider}</span>
                      <span>took_ms: {recallResponse.took_ms ?? "n/a"}</span>
                      <span>
                        unique_domains:{" "}
                        {recallResponse.metrics?.["unique_domains_count"] ?? "n/a"}
                      </span>
                      <span>
                        duplicate_urls:{" "}
                        {recallResponse.metrics?.["has_duplicate_urls"] ? "yes" : "no"}
                      </span>
                    </div>
                    {recallTopDomains.length ? (
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-200">
                        {recallTopDomains.map((item) => (
                          <span
                            key={item.domain}
                            className="rounded-full border border-slate-700 px-2 py-1"
                          >
                            {item.domain} ({item.count})
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                    <div className="text-xs uppercase text-slate-400">Results</div>
                    <div className="mt-3 space-y-3">
                      {recallResponse.items.map((item) => {
                        const annotation = recallAnnotations[item.url] ?? {
                          label: "neutral",
                          reason: "",
                        };
                        const isDuplicate = recallDuplicateUrls.has(item.url);
                        return (
                          <div
                            key={`${item.rank}-${item.url}`}
                            className="rounded-md border border-slate-800 bg-slate-950/60 px-3 py-3 text-xs text-slate-300"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="text-slate-100">
                                #{item.rank} {item.title ?? item.url}
                              </div>
                              {isDuplicate ? (
                                <span className="rounded-full border border-red-800 px-2 py-0.5 text-[10px] text-red-200">
                                  duplicate
                                </span>
                              ) : null}
                            </div>
                            <div className="mt-1 text-slate-400">
                              <a
                                href={item.url}
                                className="underline"
                                target="_blank"
                                rel="noreferrer"
                              >
                                {item.url}
                              </a>
                            </div>
                            <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-slate-400">
                              <span>domain: {item.domain ?? "n/a"}</span>
                              <span>score: {item.score ?? "n/a"}</span>
                            </div>
                            {item.snippet ? (
                              <div className="mt-2 text-xs text-slate-300">
                                {item.snippet}
                              </div>
                            ) : null}
                            <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] text-slate-300">
                              <label className="flex items-center gap-1">
                                <input
                                  type="radio"
                                  name={`annot-${item.rank}`}
                                  checked={annotation.label === "relevant"}
                                  onChange={() => updateRecallAnnotation(item.url, "relevant")}
                                />
                                pertinent
                              </label>
                              <label className="flex items-center gap-1">
                                <input
                                  type="radio"
                                  name={`annot-${item.rank}`}
                                  checked={annotation.label === "neutral"}
                                  onChange={() => updateRecallAnnotation(item.url, "neutral")}
                                />
                                neutre
                              </label>
                              <label className="flex items-center gap-1">
                                <input
                                  type="radio"
                                  name={`annot-${item.rank}`}
                                  checked={annotation.label === "irrelevant"}
                                  onChange={() => updateRecallAnnotation(item.url, "irrelevant")}
                                />
                                non pertinent
                              </label>
                            </div>
                            <input
                              value={annotation.reason}
                              onChange={(event) => updateRecallReason(item.url, event.target.value)}
                              placeholder="raison courte"
                              className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-slate-100"
                            />
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <FoldableJson title="raw" data={recallResponse.raw} />
                  <FoldableJson title="errors" data={recallResponse.errors} />
                  {recallExport ? (
                    <FoldableJson title="annotations (export)" data={recallExport} />
                  ) : null}
                </section>
              ) : (
                <section className="rounded-xl border border-dashed border-slate-800 bg-slate-900/20 p-6 text-sm text-slate-400">
                  No recall data yet. Provide a query and run recall.
                </section>
              )}
            </section>
          ) : null}

          {activeTab !== "Run Explorer" &&
          activeTab !== "Snapshot Inspector" &&
          activeTab !== "Recall Lab (Exa)" ? (
            <section className="rounded-xl border border-dashed border-slate-800 bg-slate-900/20 p-6 text-sm text-slate-400">
              {activeTab} is a placeholder. Use Run Explorer or Snapshot Inspector for now.
            </section>
          ) : null}
        </main>
      </div>
    </div>
  );
}
