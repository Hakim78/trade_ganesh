import { useEffect, useState } from "react";
import { fetchDashboard } from "./api";
import type { Dashboard } from "./types";
import KpiTiles from "./components/KpiTiles";
import PriceChart from "./components/PriceChart";
import EquityChart from "./components/EquityChart";
import TradesTable from "./components/TradesTable";
import YearlyTable from "./components/YearlyTable";
import LivePanel from "./components/LivePanel";
import StrategyCard from "./components/StrategyCard";
import { fmtIso } from "./format";

export default function App() {
  const [dashboard, setDashboard] = useState<Dashboard | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard()
      .then(setDashboard)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Liquidity Sweep + VWAP</h1>
          <div className="sub">
            {dashboard
              ? `${dashboard.meta.symbol} · ${dashboard.meta.timeframe} · ${dashboard.meta.period_label} (${dashboard.meta.start} → ${dashboard.meta.end})`
              : "Backtest et paper trading — tableau de bord"}
          </div>
        </div>
        <div className="badges">
          {dashboard && <span className="badge strong">{dashboard.meta.symbol}</span>}
          {dashboard && <span className="badge">{dashboard.meta.timeframe}</span>}
          {dashboard && dashboard.meta.period === "smoke" && (
            <span className="badge warn">fenêtre de mise au point : hors étude, aucune conclusion</span>
          )}
          {dashboard && <span className="badge">généré {fmtIso(dashboard.meta.generated_at)}</span>}
        </div>
      </header>

      {error && <div className="error">Impossible de charger le backtest : {error}</div>}
      {dashboard === null && (
        <div className="empty">
          Aucun backtest trouvé (<code>outputs/dashboard.json</code>). Lancer <code>docker compose run backtest</code> puis
          recharger cette page.
        </div>
      )}
      {dashboard === undefined && !error && <div className="empty">Chargement…</div>}

      {dashboard && (
        <>
          <KpiTiles metrics={dashboard.metrics} />
          <PriceChart bars={dashboard.bars} signals={dashboard.signals} trades={dashboard.trades} />
          <EquityChart equity={dashboard.equity} initCash={dashboard.meta.strategy.init_cash} />
          <div className="two-col">
            <YearlyTable rows={dashboard.yearly} />
            <StrategyCard meta={dashboard.meta} />
          </div>
          <TradesTable trades={dashboard.trades} />
        </>
      )}

      <LivePanel />

      <footer className="footer">
        Paper trading uniquement : aucun ordre réel n'est jamais passé. Un backtest mesure le passé, il ne prédit pas le
        futur. Frais et slippage sont déduits de tous les chiffres affichés. Détails : <code>README.md</code>,{" "}
        <code>docs/HYPOTHESIS.md</code>, <code>docs/AUDIT.md</code>.
      </footer>
    </div>
  );
}
