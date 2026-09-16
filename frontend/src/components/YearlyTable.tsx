import type { YearRow } from "../types";
import { fmtInt, fmtPct, tone } from "../format";

export default function YearlyTable({ rows }: { rows: YearRow[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Par année</h2>
        <div className="tools">une stratégie robuste ne dépend pas d'une seule année</div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Année</th>
            <th>Rendement</th>
            <th>Trades</th>
            <th>Taux de réussite</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.year}>
              <td>{r.year}</td>
              <td className={tone(r.return_pct)}>{fmtPct(r.return_pct)}</td>
              <td>{fmtInt(r.trades)}</td>
              <td>{r.win_rate_pct === null ? "—" : fmtPct(r.win_rate_pct, 1).replace("+", "")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
