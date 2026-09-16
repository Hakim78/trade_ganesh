/** Contrat de données : produit par backtest/run.py (dashboard.json) et live/run.py (live/state.json). */

export interface StrategyMeta {
  lookback: number;
  ema_len: number;
  session: string;
  tp_points: number;
  sl_points: number;
  tp_pct: number;
  sl_pct: number;
  fees_pct: number;
  slippage_pct: number;
  init_cash: number;
  size_pct_equity: number;
}

export interface DashboardMeta {
  symbol: string;
  timeframe: string;
  period: string;
  period_label: string;
  start: string;
  end: string;
  generated_at: string;
  source: string;
  bars_total: number;
  bars_exported: number;
  strategy: StrategyMeta;
}

export interface Bar {
  t: number; // unix seconds (UTC) de l'ouverture de la bougie
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
  vwap: number | null;
  ema: number | null;
  ph: number | null; // prev_high
  pl: number | null; // prev_low
  s: 0 | 1; // in_session
}

export interface Signal {
  t: number;
  side: "long" | "short";
}

export interface Trade {
  id: number;
  side: "long" | "short";
  entry_t: number;
  exit_t: number | null;
  entry_px: number;
  exit_px: number | null;
  size: number;
  pnl: number;
  ret_pct: number;
  status: "open" | "closed";
}

export interface EquityPoint {
  t: number;
  value: number;
  dd_pct: number;
}

export interface YearRow {
  year: number;
  return_pct: number;
  trades: number;
  win_rate_pct: number | null;
}

export interface Metric {
  key: string;
  label: string;
  value: number | string | null;
  format: "pct" | "money" | "number" | "ratio" | "int" | "text";
  hint?: string;
}

export interface Dashboard {
  meta: DashboardMeta;
  metrics: Metric[];
  bars: Bar[];
  signals: Signal[];
  trades: Trade[];
  equity: EquityPoint[];
  yearly: YearRow[];
}

export interface LiveSignal {
  t: string;
  side: "long" | "short" | "flat";
  price: number;
  order_id: string | null;
  status: string;
}

export interface LiveState {
  updated_at: string;
  status: "running" | "halted" | "stopped" | "starting";
  symbol: string;
  equity: number | null;
  cash: number | null;
  daily_pnl_pct: number | null;
  position: { side: "long" | "short"; qty: number; avg_price: number } | null;
  breaker: { active: boolean; reason: string | null; threshold_pct: number };
  last_bar: { t: string; o: number; h: number; l: number; c: number; v: number } | null;
  recent_signals: LiveSignal[];
  message: string | null;
}
