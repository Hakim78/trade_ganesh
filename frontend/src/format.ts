import type { Metric } from "./types";

const money = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const money2 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const number2 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
const integer = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });

export function fmtMoney(v: number | null | undefined, cents = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(cents ? money2 : money).format(v)} $`;
}

export function fmtPct(v: number | null | undefined, digits = 2, signed = true): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = signed && v > 0 ? "+" : "";
  return `${sign}${v.toFixed(digits).replace(".", ",")} %`;
}

/** Métriques dont le signe a un sens (vert / rouge, préfixe +). */
export const SIGNED_METRICS = new Set([
  "total_return_pct", "net_pnl", "expectancy", "sharpe_daily", "avg_trade_pct", "max_drawdown_pct",
]);

export function fmtNumber(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return number2.format(v);
}

export function fmtInt(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return integer.format(v);
}

export function fmtMetric(m: Metric): string {
  if (m.value === null || m.value === undefined) return "—";
  if (typeof m.value === "string") return m.value;
  switch (m.format) {
    case "pct":
      return fmtPct(m.value, 2, SIGNED_METRICS.has(m.key));
    case "money":
      return fmtMoney(m.value);
    case "int":
      return fmtInt(m.value);
    case "ratio":
    case "number":
      return fmtNumber(m.value);
    default:
      return String(m.value);
  }
}

export function fmtDateTime(unixSeconds: number | null | undefined, tz = "America/New_York"): string {
  if (!unixSeconds) return "—";
  return new Intl.DateTimeFormat("fr-FR", {
    timeZone: tz,
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(unixSeconds * 1000));
}

export function fmtIso(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" }).format(d);
}

/** Classe CSS selon le signe : positif / négatif / neutre. */
export function tone(v: number | null | undefined): "pos" | "neg" | "neutral" {
  if (v === null || v === undefined || Number.isNaN(v) || v === 0) return "neutral";
  return v > 0 ? "pos" : "neg";
}
