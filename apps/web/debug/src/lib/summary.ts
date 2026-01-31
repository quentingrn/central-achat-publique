import type { NormalizedError } from "./normalizeError";

type PhaseSummary = {
  name: string;
  status: string;
  message?: string | null;
};

export type DebugSummary = {
  runId?: string;
  status?: string;
  agentVersion?: string | null;
  createdAt?: string;
  updatedAt?: string;
  phases?: PhaseSummary[];
  errors?: NormalizedError[];
  notes?: string[];
};

export function buildChatGptSummary(summary: DebugSummary): string {
  const lines: string[] = [];
  lines.push("Debug summary (condensed)");
  if (summary.runId) {
    lines.push(`run_id: ${summary.runId}`);
  }
  if (summary.status) {
    lines.push(`status: ${summary.status}`);
  }
  if (summary.agentVersion) {
    lines.push(`agent_version: ${summary.agentVersion}`);
  }
  if (summary.createdAt) {
    lines.push(`created_at: ${summary.createdAt}`);
  }
  if (summary.updatedAt) {
    lines.push(`updated_at: ${summary.updatedAt}`);
  }
  if (summary.phases && summary.phases.length) {
    lines.push("phases:");
    summary.phases.forEach((phase) => {
      const message = phase.message ? ` — ${phase.message}` : "";
      lines.push(`- ${phase.name}: ${phase.status}${message}`);
    });
  }
  if (summary.errors && summary.errors.length) {
    lines.push("errors:");
    summary.errors.forEach((error) => {
      const status = error.status ? ` (${error.status})` : "";
      lines.push(`- [${error.kind}]${status} ${error.message}`);
    });
  }
  if (summary.notes && summary.notes.length) {
    lines.push("notes:");
    summary.notes.forEach((note) => lines.push(`- ${note}`));
  }
  return lines.join("\n");
}
