import { useState } from "react";

type Props = {
  title: string;
  data: unknown;
  defaultOpen?: boolean;
};

export function FoldableJson({ title, data, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const json = JSON.stringify(data ?? null, null, 2);

  const copyJson = async () => {
    await navigator.clipboard.writeText(json);
  };

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="text-sm font-semibold text-slate-200">{title}</div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setOpen((prev) => !prev)}
            className="rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:border-slate-500"
            type="button"
          >
            {open ? "Masquer" : "Afficher"}
          </button>
          <button
            onClick={copyJson}
            className="rounded-md bg-slate-200 px-2 py-1 text-xs font-semibold text-slate-900"
            type="button"
          >
            📋 Copier JSON
          </button>
        </div>
      </div>
      {open ? (
        <pre className="max-h-96 overflow-auto border-t border-slate-800 px-4 py-3 text-xs text-slate-100">
          {json}
        </pre>
      ) : null}
    </div>
  );
}
