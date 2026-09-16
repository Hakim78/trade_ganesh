import { useEffect, useRef } from "react";
import { ColorType, CrosshairMode, createChart } from "lightweight-charts";
import type { EquityPoint } from "../types";
import { toChartTime } from "../chartTime";

interface Props {
  equity: EquityPoint[];
  initCash: number;
}

const THEME = {
  bg: "#111820",
  grid: "#1a2330",
  text: "#8b98a8",
  border: "#223040",
};

function useAreaChart(
  ref: React.RefObject<HTMLDivElement>,
  points: { time: number; value: number }[],
  color: string,
  format: (v: number) => string,
  baseline?: number,
) {
  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: THEME.bg }, textColor: THEME.text },
      grid: { vertLines: { color: THEME.grid }, horzLines: { color: THEME.grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: THEME.border },
      timeScale: { borderColor: THEME.border, timeVisible: true, secondsVisible: false },
      localization: { locale: "fr-FR" },
    });
    const series = chart.addAreaSeries({
      lineColor: color,
      topColor: `${color}55`,
      bottomColor: `${color}05`,
      lineWidth: 2,
      priceLineVisible: false,
      priceFormat: { type: "custom", formatter: format, minMove: 0.01 },
    });
    series.setData(points.map((p) => ({ time: toChartTime(p.time), value: p.value })));
    if (baseline !== undefined) {
      series.createPriceLine({ price: baseline, color: THEME.text, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "départ" });
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [ref, points, color, format, baseline]);
}

const fmtEquity = (v: number) => `${Math.round(v).toLocaleString("fr-FR")} $`;
const fmtDd = (v: number) => `${v.toFixed(2).replace(".", ",")} %`;

export default function EquityChart({ equity, initCash }: Props) {
  const equityRef = useRef<HTMLDivElement>(null);
  const ddRef = useRef<HTMLDivElement>(null);
  const equityPoints = equity.map((p) => ({ time: p.t, value: p.value }));
  const ddPoints = equity.map((p) => ({ time: p.t, value: p.dd_pct }));
  useAreaChart(equityRef, equityPoints, "#4f8cff", fmtEquity, initCash);
  useAreaChart(ddRef, ddPoints, "#ef4444", fmtDd);

  return (
    <div className="two-col">
      <div className="panel">
        <div className="panel-head">
          <h2>Courbe de capital</h2>
          <div className="tools">valeur du portefeuille, frais et slippage déduits</div>
        </div>
        <div ref={equityRef} className="chart small" />
      </div>
      <div className="panel">
        <div className="panel-head">
          <h2>Drawdown</h2>
          <div className="tools">recul depuis le dernier plus haut du capital</div>
        </div>
        <div ref={ddRef} className="chart small" />
      </div>
    </div>
  );
}
