import type { NormalizedError } from "./normalizeError";

type PhaseSummary = {
  name: string;
  status: string;
  message?: string | null;
};

type PhaseCounts = {
  ok: number;
  warning: number;
  error: number;
  skipped: number;
};

type ErrorTop = {
  phase_name: string;
  status: string;
  message: string;
};

type RunRefs = {
  snapshot_ids: string[];
  tool_run_ids: string[];
  llm_run_ids: string[];
  prompt_ids: string[];
};

export type DebugSummary = {
  runId?: string;
  status?: string;
  agentVersion?: string | null;
  createdAt?: string;
  updatedAt?: string;
  sourceUrl?: string | null;
  phases?: PhaseSummary[];
  phaseCounts?: PhaseCounts;
  errorTop?: ErrorTop | null;
  refs?: RunRefs;
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
  if (summary.sourceUrl) {
    lines.push(`source_url: ${summary.sourceUrl}`);
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
  if (summary.phaseCounts) {
    const counts = summary.phaseCounts;
    lines.push(
      `phase_counts: ok=${counts.ok} warning=${counts.warning} error=${counts.error} skipped=${counts.skipped}`
    );
  }
  if (summary.errorTop) {
    lines.push(
      `top_issue: ${summary.errorTop.phase_name} (${summary.errorTop.status}) ${summary.errorTop.message}`
    );
  }
  if (summary.refs) {
    lines.push(
      `refs: snapshots=${summary.refs.snapshot_ids.length} tool_runs=${summary.refs.tool_run_ids.length} llm_runs=${summary.refs.llm_run_ids.length} prompts=${summary.refs.prompt_ids.length}`
    );
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
