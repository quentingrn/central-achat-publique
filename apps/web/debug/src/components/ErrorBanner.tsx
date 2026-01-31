import type { NormalizedError } from "../lib/normalizeError";

type Props = {
  errors: NormalizedError[];
};

export function ErrorBanner({ errors }: Props) {
  if (!errors.length) {
    return null;
  }

  const copyRaw = async () => {
    await navigator.clipboard.writeText(JSON.stringify(errors.map((e) => e.raw), null, 2));
  };

  return (
    <div className="sticky top-0 z-20 border-b border-red-900 bg-red-950/80 px-4 py-3 backdrop-blur">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-red-200">Erreurs / warnings</div>
          <ul className="mt-2 space-y-1 text-xs text-red-100">
            {errors.map((error, index) => (
              <li key={`${error.kind}-${index}`}>
                <span className="font-semibold">[{error.kind}]</span>{" "}
                {error.status ? `(${error.status}) ` : ""}
                {error.message}
              </li>
            ))}
          </ul>
        </div>
        <button
          onClick={copyRaw}
          className="rounded-md bg-red-200 px-3 py-2 text-xs font-semibold text-red-950"
          type="button"
        >
          📋 Copier erreur brute
        </button>
      </div>
    </div>
  );
}
