import type { DebugSummary } from "../lib/summary";
import { buildChatGptSummary } from "../lib/summary";

type Props = {
  summary?: DebugSummary;
  textOverride?: string;
  label?: string;
};

export function CopyForChatgptButton({ summary, textOverride, label }: Props) {
  const copySummary = async () => {
    const text = textOverride ?? (summary ? buildChatGptSummary(summary) : "");
    if (!text) {
      return;
    }
    await navigator.clipboard.writeText(text);
  };

  return (
    <button
      onClick={copySummary}
      className="rounded-md bg-emerald-300 px-3 py-2 text-xs font-semibold text-emerald-950"
      type="button"
      disabled={Boolean(textOverride || summary) === false}
    >
      {label ?? "📋 Copier résumé debug"}
    </button>
  );
}
