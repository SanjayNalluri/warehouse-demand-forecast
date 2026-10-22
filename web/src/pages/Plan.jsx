import { useEffect, useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { get } from "../api.js";
import { axis, day, num, tip, weekday } from "../util.js";

const RULES = [
  { id: "p50", name: "P50", hint: "Cheapest. About 2% of lines end up a day late." },
  { id: "p75", name: "P75", hint: "Recommended. Under 1% late for ~8% more labour." },
  { id: "p90", name: "P90", hint: "Almost never late, but ~22% more labour." },
];

export default function Plan({ shared }) {
  const [rule, setRule] = useState("p75");
  const [rate, setRate] = useState(80);
  const [days, setDays] = useState(7);
  const [fc, setFc] = useState(null);

  useEffect(() => {
    get("/forecast", { days, rule, pick_rate: rate }).then(setFc).catch(() => {});
  }, [days, rule, rate]);

  const chart = useMemo(() => {
    if (!fc || !shared) return [];
    const past = shared.history.filter((d) => d.is_open).map((d) => ({ date: d.date, actual: d.lines }));
    const next = fc.days.filter((d) => d.is_open)
      .map((d) => ({ date: d.date, forecast: d.lines_p50, range: [d.lines_p10, d.lines_p90] }));
    return [...past, ...next];
  }, [fc, shared]);

  const open = fc ? fc.days.filter((d) => d.is_open) : [];
  const first = fc?.days[0]?.date, last = fc?.days.at(-1)?.date;

  return (
    <div className="plan">
      <aside className="panel settings">
        <h3>Settings</h3>

        <div className="field">
          <span className="label">Staff to which forecast?</span>
          {RULES.map((r) => (
            <label key={r.id} className={`option ${rule === r.id ? "picked" : ""}`}>
              <input type="radio" name="rule" checked={rule === r.id} onChange={() => setRule(r.id)} />
              <span><b>{r.name}</b> {r.hint}</span>
            </label>
          ))}
        </div>

        <div className="field">
          <span className="label">Pick rate <b>{rate}</b> lines / picker-hour</span>
          <input type="range" min="40" max="200" step="10" value={rate} onChange={(e) => setRate(+e.target.value)} />
          <span className="hint">Assumed 80. Change it to match your floor.</span>
        </div>

        <div className="field">
          <span className="label">Days ahead <b>{days}</b></span>
          <input type="range" min="1" max="7" value={days} onChange={(e) => setDays(+e.target.value)} />
        </div>
      </aside>

      <section className="content">
        {fc ? (
          <>
            <p className="answer">
              For <b>{day(first)} – {day(last)} 2011</b>, schedule <b>{fc.total_picker_shifts} picker-shifts</b> across{" "}
              {open.length} working days (about {num(fc.total_lines_p50)} pick lines expected).
            </p>

            <div className="panel">
              <table className="grid">
                <thead>
                  <tr><th>Day</th><th className="r">Likely lines</th><th className="r">Range (80%)</th>
                      <th className="r">Pickers</th></tr>
                </thead>
                <tbody>
                  {fc.days.map((d) => (
                    <tr key={d.date} className={d.is_open ? "" : "off"}>
                      <td className="nowrap">{weekday(d.date).slice(0, 3)} <span className="muted">{day(d.date)}</span></td>
                      {d.is_open ? (
                        <>
                          <td className="r">{num(d.lines_p50)}</td>
                          <td className="r muted nowrap">{num(d.lines_p10)} – {num(d.lines_p90)}</td>
                          <td className="r"><span className="pill">{d.pickers}</span></td>
                        </>
                      ) : <td colSpan={3} className="r muted">Closed</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="hint pad">One picker covers {num(fc.lines_per_picker_shift)} lines per 8-hour shift
                ({rate} lines/h, 85% of the shift spent picking).</p>
            </div>

            <div className="panel">
              <h3>Last 9 weeks and the forecast</h3>
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={chart} margin={{ top: 6, right: 8, left: -8, bottom: 0 }}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={day} minTickGap={36} {...axis} />
                  <YAxis {...axis} />
                  <Tooltip {...tip} />
                  <Area dataKey="range" name="80% range" fill="var(--gold)" fillOpacity={0.22} stroke="none" />
                  <Line dataKey="actual" name="Actual" stroke="var(--text)" strokeWidth={1.4} dot={false} />
                  <Line dataKey="forecast" name="Forecast" stroke="var(--blue)" strokeWidth={2.4} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
              <p className="legend"><i className="k dark" /> actual pick lines <i className="k blue" /> forecast <i className="k band" /> 80% range</p>
            </div>
          </>
        ) : <div className="panel muted">Waiting for the forecast…</div>}
      </section>
    </div>
  );
}
