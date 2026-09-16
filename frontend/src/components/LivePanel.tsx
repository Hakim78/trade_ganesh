import { useEffect, useState } from "react";
import type { LiveState } from "../types";
import { fetchLiveState } from "../api";
import { fmtIso, fmtMoney, fmtPct, tone } from "../format";

const POLL_MS = 5000;

export default function LivePanel() {
  const [state, setState] = useState<LiveState | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const s = await fetchLiveState();
        if (!cancelled) {
          setState(s);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    };
    void tick();
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Paper trading Alpaca (temps réel)</h2>
        <div className="tools">
          {state && (
            <>
              <span className={`status-dot ${state.status}`} />
              {state.status === "running" && "en cours"}
              {state.status === "halted" && "coupe-circuit actif"}
              {state.status === "stopped" && "arrêté"}
              {state.status === "starting" && "démarrage"}
              <span> · mis à jour {fmtIso(state.updated_at)}</span>
            </>
          )}
        </div>
      </div>
      {error && <div className="error">Lecture de live/state.json impossible : {error}</div>}
      {state === null && (
        <div className="empty">
          Aucune session live. Lancer <code>docker compose up live</code> (clés Alpaca paper dans <code>.env</code>).
        </div>
      )}
      {state && (
        <>
          <div className="grid-kpi" style={{ marginBottom: 12 }}>
            <div className="kpi">
              <div className="label">Capital (paper)</div>
              <div className="value">{fmtMoney(state.equity)}</div>
            </div>
            <div className="kpi">
              <div className="label">P&amp;L du jour</div>
              <div className={`value ${tone(state.daily_pnl_pct)}`}>{fmtPct(state.daily_pnl_pct)}</div>
              <div className="hint">coupe-circuit à −{state.breaker.threshold_pct} %</div>
            </div>
            <div className="kpi">
              <div className="label">Position</div>
              <div className="value">
                {state.position ? (
                  <>
                    <span className={`tag ${state.position.side}`}>{state.position.side.toUpperCase()}</span>{" "}
                    {state.position.qty} @ {fmtMoney(state.position.avg_price, true)}
                  </>
                ) : (
                  <span className="tag flat">FLAT</span>
                )}
              </div>
            </div>
            <div className="kpi">
              <div className="label">Dernière bougie clôturée</div>
              <div className="value">{state.last_bar ? fmtMoney(state.last_bar.c, true) : "—"}</div>
              <div className="hint">{state.last_bar ? fmtIso(state.last_bar.t) : "en attente du flux"}</div>
            </div>
          </div>
          {state.breaker.active && (
            <div className="error" style={{ marginBottom: 12 }}>
              Coupe-circuit : {state.breaker.reason ?? "seuil de perte journalière atteint"}. Plus aucune entrée
              aujourd'hui ; les positions ouvertes gardent leur TP / SL.
            </div>
          )}
          {state.message && <div className="badge warn" style={{ marginBottom: 12 }}>{state.message}</div>}
          {state.recent_signals.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Heure</th>
                  <th>Signal</th>
                  <th>Prix</th>
                  <th>Ordre</th>
                  <th>Statut</th>
                </tr>
              </thead>
              <tbody>
                {state.recent_signals.slice(-20).reverse().map((s, i) => (
                  <tr key={`${s.t}-${i}`}>
                    <td>{fmtIso(s.t)}</td>
                    <td>
                      <span className={`tag ${s.side}`}>{s.side.toUpperCase()}</span>
                    </td>
                    <td>{fmtMoney(s.price, true)}</td>
                    <td>{s.order_id ? <code>{s.order_id.slice(0, 8)}</code> : "—"}</td>
                    <td>{s.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty">Aucun signal émis pour l'instant.</div>
          )}
        </>
      )}
    </div>
  );
}
