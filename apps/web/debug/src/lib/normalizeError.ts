import type { ApiError } from "./debugApiClient";

export type NormalizedError = {
  kind: "api" | "network" | "validation" | "unknown";
  status?: number;
  message: string;
  raw: unknown;
};

const isApiError = (error: unknown): error is ApiError =>
  typeof error === "object" &&
  error !== null &&
  "kind" in error &&
  (error as ApiError).kind === "api";

export function normalizeError(error: unknown): NormalizedError {
  if (isApiError(error)) {
    return {
      kind: "api",
      status: error.status,
      message: error.message,
      raw: error.body,
    };
  }

  if (error instanceof Error) {
    const message = error.message || "Unknown error";
    const kind = message.toLowerCase().includes("network") ? "network" : "unknown";
    return {
      kind,
      message,
      raw: {
        name: error.name,
        message: error.message,
        stack: error.stack,
      },
    };
  }

  return {
    kind: "unknown",
    message: "Unexpected error",
    raw: error,
  };
}
