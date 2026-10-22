import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axis, day, tip } from "../util.js";

export default function Accuracy({ info, backtest }) {
  const data = backtest.daily.map((d) => ({ date: d.date, actual: d.actual, forecast: d.p50, range: [d.p10, d.p90] }));
  const models = [...backtest.model_comparison].sort((a, b) => a.wape - b.wape);

  return (
    <div className="stack">
      <div>
        <h2>How good is the forecast?</h2>
        <p className="intro">
          Tested on Jul – Dec 2011, which the model never saw while its settings were picked. At the start of each
          month it was retrained on everything before, then forecast each day 7 days ahead, the same way it would
          be used for real.
        </p>
      </div>

      <div className="stats">
        <div><b>{info.test_wape.toFixed(1)}%</b><span>daily error (WAPE)</span></div>
        <div><b>{info.naive_wape.toFixed(1)}%</b><span>error of "same as last week"</span></div>
        <div><b>{info.test_weekly_wape.toFixed(1)}%</b><span>error on weekly totals</span></div>
        <div><b>{Math.round(info.interval_coverage_pct)}%</b><span>of days inside the 80% range</span></div>
      </div>

      <div className="panel">
        <h3>Forecast vs actual, Jul – Dec 2011</h3>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={data} margin={{ top: 6, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={day} minTickGap={44} {...axis} />
            <YAxis {...axis} />
            <Tooltip {...tip} />
            <Area dataKey="range" name="80% range" fill="var(--gold)" fillOpacity={0.22} stroke="none" />
            <Line dataKey="actual" name="Actual" stroke="var(--text)" strokeWidth={1} dot={false} />
            <Line dataKey="forecast" name="Forecast" stroke="var(--blue)" strokeWidth={2} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
        <p className="legend"><i className="k dark" /> actual <i className="k blue" /> forecast <i className="k band" /> 80% range</p>
      </div>

      <div className="panel">
        <h3>Compared with simple methods</h3>
        <table className="grid">
          <thead><tr><th>Method</th><th className="r">Daily error</th><th className="r">Bias</th></tr></thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.model} className={m.model.startsWith("LightGBM") ? "mark" : ""}>
                <td>{m.model}</td><td className="r">{m.wape.toFixed(1)}%</td>
                <td className="r">{m.bias_pct > 0 ? "+" : ""}{m.bias_pct.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint pad">
          Honest reading: the model beats "same as last week" by 14%, but is only slightly better than scaling last
          year's level by this year's growth. Daily orders are lumpy (around 65 wholesale orders a day), so ~20% daily
          error is close to what this data allows. That is why staffing uses the upper end of the range.
        </p>
      </div>
    </div>
  );
}
