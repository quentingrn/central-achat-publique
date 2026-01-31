const baseUrl = import.meta.env.VITE_DEBUG_API_BASE_URL || "";
const token = import.meta.env.VITE_DEBUG_API_TOKEN || "";

export type ApiError = {
  kind: "api";
  status: number;
  message: string;
  body: unknown;
};

const buildUrl = (path: string) => {
  if (!baseUrl) {
    return path;
  }
  return `${baseUrl.replace(/\/$/, "")}${path}`;
};

export async function debugGet<T>(path: string): Promise<T> {
  const response = await fetch(buildUrl(path), {
    headers: {
      "X-Debug-Token": token,
    },
  });
  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = await response.text();
    }
    const error: ApiError = {
      kind: "api",
      status: response.status,
      message: response.statusText || "API error",
      body,
    };
    throw error;
  }
  return response.json() as Promise<T>;
}

export type CompareRunListResponse = {
  items: unknown[];
  next_cursor: string | null;
};

export async function listCompareRuns(limit = 25, cursor?: string | null) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (cursor) {
    params.set("cursor", cursor);
  }
  const path = `/v1/debug/compare-runs?${params.toString()}`;
  return debugGet<CompareRunListResponse>(path);
}

export async function getCompareRunSummary(runId: string) {
  return debugGet(`/v1/debug/compare-runs/${runId}:summary`);
}

export async function getCompareRunFull(runId: string) {
  return debugGet(`/v1/debug/compare-runs/${runId}`);
}

export async function diffCompareRuns(leftRunId: string, rightRunId: string) {
  const params = new URLSearchParams();
  params.set("left_run_id", leftRunId);
  params.set("right_run_id", rightRunId);
  return debugGet(`/v1/debug/compare-runs:diff?${params.toString()}`);
}

export async function getSnapshot(snapshotId: string) {
  return debugGet(`/v1/debug/snapshots/${snapshotId}`);
}

export async function listSnapshotsByUrl(url: string, limit = 10) {
  const params = new URLSearchParams();
  params.set("url", url);
  params.set("limit", String(limit));
  return debugGet(`/v1/debug/snapshots:by-url?${params.toString()}`);
}

export type SnapshotCaptureRequest = {
  url: string;
  provider?: string | null;
  proof_mode?: string | null;
  screenshot_enabled?: boolean | null;
  max_bytes?: number | null;
};

export async function captureSnapshot(payload: SnapshotCaptureRequest) {
  const response = await fetch(buildUrl("/v1/debug/snapshots:capture"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Debug-Token": token,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = await response.text();
    }
    const error: ApiError = {
      kind: "api",
      status: response.status,
      message: response.statusText || "API error",
      body,
    };
    throw error;
  }
  return response.json();
}

export type ExaRecallRequest = {
  query: string;
  num_results?: number;
  include_domains?: string[] | null;
  exclude_domains?: string[] | null;
  language?: string | null;
  country?: string | null;
  use_autoprompt?: boolean | null;
};

export async function recallExa(payload: ExaRecallRequest) {
  const response = await fetch(buildUrl("/v1/debug/recall/exa"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Debug-Token": token,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = await response.text();
    }
    const error: ApiError = {
      kind: "api",
      status: response.status,
      message: response.statusText || "API error",
      body,
    };
    throw error;
  }
  return response.json();
}
