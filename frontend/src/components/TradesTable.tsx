import { useMemo, useState } from "react";
import type { Trade } from "../types";
import { fmtDateTime, fmtMoney, fmtPct, tone } from "../format";

type Filter = "all" | "long" | "short";
const PAGE = 200;

export default function TradesTable({ trades }: { trades: Trade[] }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [showAll, setShowAll] = useState(false);

  const rows = useMemo(() => {
    const filtered = filter === "all" ? trades : trades.filter((t) => t.side === filter);
    const newestFirst = [...filtered].sort((a, b) => b.entry_t - a.entry_t);
    return showAll ? newestFirst : newestFirst.slice(0, PAGE);
  }, [trades, filter, showAll]);

  const total = filter === "all" ? trades.length : trades.filter((t) => t.side === filter).length;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Trades ({total})</h2>
        <div className="tools">
          <select value={filter} onChange={(e) => setFilter(e.target.value as Filter)}>
            <option value="all">Tous</option>
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
          {total > PAGE && (
            <button onClick={() => setShowAll((v) => !v)}>{showAll ? `Les ${PAGE} derniers` : "Afficher tout"}</button>
          )}
        </div>
      </div>
      {rows.length === 0 ? (
        <div className="empty">Aucun trade sur cette période.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Sens</th>
                <th>Entrée (NY)</th>
                <th>Sortie (NY)</th>
                <th>Prix entrée</th>
                <th>Prix sortie</th>
                <th>Qté</th>
                <th>P&amp;L</th>
                <th>Rendement</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id}>
                  <td>{t.id}</td>
                  <td>
                    <span className={`tag ${t.side}`}>{t.side === "long" ? "LONG" : "SHORT"}</span>
                  </td>
                  <td>{fmtDateTime(t.entry_t)}</td>
                  <td>{t.status === "open" ? <span className="tag flat">ouvert</span> : fmtDateTime(t.exit_t)}</td>
                  <td>{fmtMoney(t.entry_px, true)}</td>
                  <td>{fmtMoney(t.exit_px, true)}</td>
                  <td>{t.size}</td>
                  <td className={tone(t.pnl)}>{fmtMoney(t.pnl, true)}</td>
                  <td className={tone(t.ret_pct)}>{fmtPct(t.ret_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
