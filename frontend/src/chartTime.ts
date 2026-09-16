import type { UTCTimestamp } from "lightweight-charts";

/**
 * lightweight-charts affiche les horodatages en UTC. Pour lire l'heure de New York sur l'axe (comme sur
 * TradingView), on décale chaque timestamp de l'offset ET du moment (EDT ou EST).
 */
const parts = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  hourCycle: "h23",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

const offsetCache = new Map<number, number>();

function etOffsetSeconds(unixSeconds: number): number {
  const dayKey = Math.floor(unixSeconds / 21_600); // cache par tranche de 6 h (les changements d'heure sont à 2 h du matin)
  const cached = offsetCache.get(dayKey);
  if (cached !== undefined) return cached;
  const p = parts.formatToParts(new Date(unixSeconds * 1000));
  const get = (type: string) => Number(p.find((x) => x.type === type)?.value ?? 0);
  const asUtc = Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second")) / 1000;
  const offset = asUtc - unixSeconds;
  offsetCache.set(dayKey, offset);
  return offset;
}

export function toChartTime(unixSeconds: number): UTCTimestamp {
  return (unixSeconds + etOffsetSeconds(unixSeconds)) as UTCTimestamp;
}
