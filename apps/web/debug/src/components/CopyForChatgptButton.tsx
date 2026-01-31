import type { DebugSummary } from "../lib/summary";
import { buildChatGptSummary } from "../lib/summary";

type Props = {
  summary: DebugSummary;
};

export function CopyForChatgptButton({ summary }: Props) {
  const copySummary = async () => {
    await navigator.clipboard.writeText(buildChatGptSummary(summary));
  };

  return (
    <button
      onClick={copySummary}
      className="rounded-md bg-emerald-300 px-3 py-2 text-xs font-semibold text-emerald-950"
      type="button"
    >
      📋 Copier résumé debug
    </button>
  );
}
