import type { Metric } from "../types";
import { SIGNED_METRICS, fmtMetric, tone } from "../format";

export default function KpiTiles({ metrics }: { metrics: Metric[] }) {
  return (
    <div className="grid-kpi">
      {metrics.map((m) => {
        const signed = SIGNED_METRICS.has(m.key) && m.key !== "max_drawdown_pct";
        const cls = signed && typeof m.value === "number" ? tone(m.value) : "neutral";
        return (
          <div className="kpi" key={m.key}>
            <div className="label">{m.label}</div>
            <div className={`value ${cls}`}>{fmtMetric(m)}</div>
            {m.hint && <div className="hint">{m.hint}</div>}
          </div>
        );
      })}
    </div>
  );
}
