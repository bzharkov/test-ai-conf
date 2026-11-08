import { pct, rub, signedRub } from "../lib/format";

export interface AltItem {
  component_id: number;
  name: string;
  price_rub: number | null;
  price_delta_rub: number;
  total_delta_rub: number;
  perf_delta_pct: number | null;
  notes: string[];
  extra_component_id?: number | null;
  extra_component_name?: string | null;
}

interface Props {
  alt: AltItem;
  onApply: (alt: AltItem) => void;
  disabled?: boolean;
}

export function AlternativeCard({ alt, onApply, disabled }: Props) {
  const cheaper = alt.total_delta_rub < 0;
  return (
    <div className="panel p-3 text-sm" data-testid="alt-card">
      <p className="break-words font-medium">{alt.name}</p>
      <p className="mt-1 font-mono text-xs text-mute">{rub(alt.price_rub)}</p>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs">
        <span className={cheaper ? "text-accent" : "text-warn"}>
          цена {signedRub(alt.total_delta_rub)}
        </span>
        <span>произв. {pct(alt.perf_delta_pct)}</span>
      </div>
      {alt.notes.map((n) => (
        <p key={n} className="mt-1 text-xs text-warn">
          {n}
        </p>
      ))}
      <button
        className="btn btn-primary mt-3 w-full"
        disabled={disabled}
        onClick={() => onApply(alt)}
      >
        Применить
      </button>
    </div>
  );
}
