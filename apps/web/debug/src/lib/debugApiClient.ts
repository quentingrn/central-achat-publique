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
