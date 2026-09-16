import { useEffect, useMemo, useRef, useState } from "react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import type { Bar, Signal, Trade } from "../types";
import { toChartTime } from "../chartTime";
import { fmtMoney } from "../format";

interface Props {
  bars: Bar[];
  signals: Signal[];
  trades: Trade[];
}

const COLORS = {
  up: "#26a69a",
  down: "#ef5350",
  vwap: "#4f8cff",
  ema: "#f59e0b",
  levels: "#5b6b7d",
  bg: "#111820",
  grid: "#1a2330",
  text: "#8b98a8",
  border: "#223040",
};

export default function PriceChart({ bars, signals, trades }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [showLevels, setShowLevels] = useState(false);
  const [showExits, setShowExits] = useState(true);

  const markers = useMemo<SeriesMarker<Time>[]>(() => {
    const out: SeriesMarker<Time>[] = [];
    for (const s of signals) {
      out.push(
        s.side === "long"
          ? { time: toChartTime(s.t), position: "belowBar", color: COLORS.up, shape: "arrowUp", text: "L" }
          : { time: toChartTime(s.t), position: "aboveBar", color: COLORS.down, shape: "arrowDown", text: "S" },
      );
    }
    if (showExits) {
      for (const t of trades) {
        if (t.exit_t === null) continue;
        out.push({
          time: toChartTime(t.exit_t),
          position: t.side === "long" ? "aboveBar" : "belowBar",
          color: t.pnl >= 0 ? COLORS.up : COLORS.down,
          shape: "circle",
          text: fmtMoney(t.pnl, true),
          size: 0.8,
        });
      }
    }
    out.sort((a, b) => (a.time as number) - (b.time as number));
    return out;
  }, [signals, trades, showExits]);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: COLORS.bg }, textColor: COLORS.text },
      grid: { vertLines: { color: COLORS.grid }, horzLines: { color: COLORS.grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: COLORS.border },
      timeScale: { borderColor: COLORS.border, timeVisible: true, secondsVisible: false, rightOffset: 6 },
      localization: { locale: "fr-FR" },
    });
    chartRef.current = chart;

    const candles = chart.addCandlestickSeries({
      upColor: COLORS.up,
      downColor: COLORS.down,
      borderVisible: false,
      wickUpColor: COLORS.up,
      wickDownColor: COLORS.down,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    candles.setData(
      bars.map((b) => ({ time: toChartTime(b.t), open: b.o, high: b.h, low: b.l, close: b.c })),
    );

    const vwap = chart.addLineSeries({ color: COLORS.vwap, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "VWAP" });
    vwap.setData(bars.filter((b) => b.vwap !== null).map((b) => ({ time: toChartTime(b.t), value: b.vwap as number })));

    const ema = chart.addLineSeries({ color: COLORS.ema, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "EMA 50" });
    ema.setData(bars.filter((b) => b.ema !== null).map((b) => ({ time: toChartTime(b.t), value: b.ema as number })));

    if (showLevels) {
      const ph = chart.addLineSeries({ color: COLORS.levels, lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false, title: "Plus haut 10" });
      ph.setData(bars.filter((b) => b.ph !== null).map((b) => ({ time: toChartTime(b.t), value: b.ph as number })));
      const pl = chart.addLineSeries({ color: COLORS.levels, lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false, title: "Plus bas 10" });
      pl.setData(bars.filter((b) => b.pl !== null).map((b) => ({ time: toChartTime(b.t), value: b.pl as number })));
    }

    candles.setMarkers(markers);

    // Vue initiale : les 3 dernières séances (≈ 234 bougies de 5 min), en plage logique (par index),
    // plus robuste que par horodatage. fitContent d'abord pour forcer un premier calcul de layout.
    chart.timeScale().fitContent();
    const frame = window.requestAnimationFrame(() => {
      if (bars.length > 240) {
        chart.timeScale().setVisibleLogicalRange({ from: bars.length - 234, to: bars.length + 4 });
      }
    });

    return () => {
      window.cancelAnimationFrame(frame);
      chart.remove();
      chartRef.current = null;
    };
  }, [bars, markers, showLevels]);

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Graphique 5 minutes — signaux et sorties</h2>
        <div className="tools">
          <label>
            <input type="checkbox" checked={showLevels} onChange={(e) => setShowLevels(e.target.checked)} /> niveaux 10 bougies
          </label>
          <label>
            <input type="checkbox" checked={showExits} onChange={(e) => setShowExits(e.target.checked)} /> sorties
          </label>
          <button onClick={() => chartRef.current?.timeScale().fitContent()}>Tout afficher</button>
        </div>
      </div>
      <div className="legend" style={{ marginBottom: 8 }}>
        <span><i className="sw" style={{ background: COLORS.vwap }} />VWAP de séance</span>
        <span><i className="sw" style={{ background: COLORS.ema }} />EMA 50</span>
        <span><i className="sw" style={{ background: COLORS.up }} />▲ L = entrée long</span>
        <span><i className="sw" style={{ background: COLORS.down }} />▼ S = entrée short</span>
        <span>● = sortie (TP, SL ou retournement), couleur = gain / perte</span>
        <span>Axe des temps en heure de New York</span>
      </div>
      <div ref={ref} className="chart" />
    </div>
  );
}
