import type { DashboardMeta } from "../types";

const pct = (v: number) => `${(v * 100).toFixed(3).replace(".", ",")} %`;

export default function StrategyCard({ meta }: { meta: DashboardMeta }) {
  const s = meta.strategy;
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Règles de la stratégie</h2>
        <div className="tools">
          source : <code>docs/STRATEGY.md</code> · paramètres : <code>config.yaml</code>
        </div>
      </div>
      <dl className="rules">
        <div>
          <dt>Entrée long</dt>
          <dd>
            mèche sous le plus bas des {s.lookback} bougies précédentes, clôture au-dessus, clôture &gt; VWAP de séance
            et &gt; EMA {s.ema_len}
          </dd>
        </div>
        <div>
          <dt>Entrée short</dt>
          <dd>
            mèche au-dessus du plus haut des {s.lookback} bougies précédentes, clôture en dessous, clôture &lt; VWAP et
            &lt; EMA {s.ema_len}
          </dd>
        </div>
        <div>
          <dt>Fenêtre horaire</dt>
          <dd>{s.session} (entrées uniquement) · exécution à l'ouverture de la bougie suivante</dd>
        </div>
        <div>
          <dt>Sorties</dt>
          <dd>
            TP {s.tp_points} pts d'indice ({pct(s.tp_pct)}) · SL {s.sl_points} pts ({pct(s.sl_pct)}) · ordres persistants ·
            signal inverse = retournement
          </dd>
        </div>
        <div>
          <dt>Taille et coûts</dt>
          <dd>
            {s.size_pct_equity} % du capital par trade, actions entières · frais {pct(s.fees_pct)} + slippage{" "}
            {pct(s.slippage_pct)} par côté · capital initial {s.init_cash.toLocaleString("fr-FR")} $
          </dd>
        </div>
        <div>
          <dt>Données</dt>
          <dd>
            {meta.symbol} {meta.timeframe}, séance uniquement · {meta.source} · {meta.bars_total.toLocaleString("fr-FR")}{" "}
            bougies
          </dd>
        </div>
      </dl>
    </div>
  );
}
