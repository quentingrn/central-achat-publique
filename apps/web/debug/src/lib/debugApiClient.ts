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
