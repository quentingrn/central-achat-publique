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

type DiffField = {
  left: string | null;
  right: string | null;
  severity: string;
};

type DiffCounts = {
  left: PhaseCounts;
  right: PhaseCounts;
  severity: string;
};

type DiffErrorTop = {
  left: ErrorTop | null;
  right: ErrorTop | null;
  severity: string;
};

type DiffTimelineItem = {
  phase_name: string;
  left_status: string | null;
  right_status: string | null;
  severity: string;
  left_message?: string | null;
  right_message?: string | null;
};

type DiffRefSet = {
  added_ids: string[];
  removed_ids: string[];
  common_count: number;
};

type DiffRefs = {
  snapshots: DiffRefSet;
  tool_runs: DiffRefSet;
  llm_runs: DiffRefSet;
  prompts: DiffRefSet;
};

export type DebugDiffSummary = {
  left_run_id: string;
  right_run_id: string;
  left_created_at?: string | null;
  right_created_at?: string | null;
  status_diff: DiffField;
  source_url_diff: DiffField;
  agent_version_diff: DiffField;
  phase_counts: DiffCounts;
  error_top: DiffErrorTop;
  timeline: DiffTimelineItem[];
  refs: DiffRefs;
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

export function buildChatGptDiffSummary(diff: DebugDiffSummary): string {
  const lines: string[] = [];
  lines.push("Debug diff summary (condensed)");
  lines.push(`left_run_id: ${diff.left_run_id}`);
  lines.push(`right_run_id: ${diff.right_run_id}`);
  if (diff.left_created_at) {
    lines.push(`left_created_at: ${diff.left_created_at}`);
  }
  if (diff.right_created_at) {
    lines.push(`right_created_at: ${diff.right_created_at}`);
  }
  lines.push(`status: ${diff.status_diff.left ?? "n/a"} -> ${diff.status_diff.right ?? "n/a"}`);
  lines.push(
    `source_url: ${diff.source_url_diff.left ?? "n/a"} -> ${diff.source_url_diff.right ?? "n/a"}`
  );
  lines.push(
    `agent_version: ${diff.agent_version_diff.left ?? "n/a"} -> ${diff.agent_version_diff.right ?? "n/a"}`
  );
  lines.push(
    `phase_counts: left ok=${diff.phase_counts.left.ok} warning=${diff.phase_counts.left.warning} error=${diff.phase_counts.left.error} skipped=${diff.phase_counts.left.skipped} | right ok=${diff.phase_counts.right.ok} warning=${diff.phase_counts.right.warning} error=${diff.phase_counts.right.error} skipped=${diff.phase_counts.right.skipped}`
  );
  if (diff.error_top.left || diff.error_top.right) {
    lines.push(
      `top_issue_left: ${diff.error_top.left?.phase_name ?? "n/a"} (${diff.error_top.left?.status ?? "n/a"}) ${diff.error_top.left?.message ?? ""}`
    );
    lines.push(
      `top_issue_right: ${diff.error_top.right?.phase_name ?? "n/a"} (${diff.error_top.right?.status ?? "n/a"}) ${diff.error_top.right?.message ?? ""}`
    );
  }
  const changedPhases = diff.timeline.filter((item) => item.severity !== "same");
  if (changedPhases.length) {
    lines.push("phase_changes:");
    changedPhases.slice(0, 12).forEach((item) => {
      lines.push(
        `- ${item.phase_name}: ${item.left_status ?? "n/a"} -> ${item.right_status ?? "n/a"}`
      );
    });
    if (changedPhases.length > 12) {
      lines.push(`- ... (${changedPhases.length - 12} more)`);
    }
  }
  lines.push(
    `refs: snapshots +${diff.refs.snapshots.added_ids.length}/-${diff.refs.snapshots.removed_ids.length} common=${diff.refs.snapshots.common_count}, tool_runs +${diff.refs.tool_runs.added_ids.length}/-${diff.refs.tool_runs.removed_ids.length} common=${diff.refs.tool_runs.common_count}, llm_runs +${diff.refs.llm_runs.added_ids.length}/-${diff.refs.llm_runs.removed_ids.length} common=${diff.refs.llm_runs.common_count}, prompts +${diff.refs.prompts.added_ids.length}/-${diff.refs.prompts.removed_ids.length} common=${diff.refs.prompts.common_count}`
  );
  return lines.join("\n");
}
