import { Meter } from "./Rules.jsx";

const BEST = "6 pickers, split 3 x 09-17 + 3 x 11-19";

export default function Shifts({ simulation }) {
  const rows = simulation.scenarios;
  const maxLate = Math.max(...rows.map((r) => r.late_lines_pct));
  const maxCost = Math.max(...rows.map((r) => Math.abs(r.cost_vs_all_early_pct)));
  const pretty = (s) => s.replace(" x ", " × ").replace(" x ", " × ").replace(/(\d\d)-(\d\d)/g, "$1–$2");

  return (
    <div className="stack">
      <div>
        <h2>When should the pickers start?</h2>
        <p className="intro">
          The plan sets pickers per day, but orders arrive through the day: 16% between 12 and 1 PM, 12% after 4 PM,
          almost none after 6 PM. A discrete-event simulation (SimPy) replays a busy forecast day, Monday 12 Dec 2011,
          {" "}{simulation.replications} times for each shift pattern. Every pattern faces the same simulated days.
        </p>
      </div>

      <div className="panel">
        <table className="grid rules">
          <thead>
            <tr><th>Crew and shifts</th><th>Lines picked late</th><th className="r">Orders done in 4 h</th>
                <th className="r">Utilisation</th><th>Labour cost vs all 08–16</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.scenario} className={r.scenario === BEST ? "mark" : ""}>
                <td>{pretty(r.scenario)}</td>
                <td><Meter value={r.late_lines_pct} max={maxLate} color="var(--wine)"
                           label={`${r.late_lines_pct.toFixed(1)}%`} /></td>
                <td className="r">{r.within_4h_pct.toFixed(0)}%</td>
                <td className="r">{r.utilisation_pct.toFixed(0)}%</td>
                <td><Meter value={r.cost_vs_all_early_pct} max={maxCost} signed color="var(--blue)"
                           label={`${r.cost_vs_all_early_pct > 0 ? "+" : ""}${r.cost_vs_all_early_pct}%`} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint pad">Means over {simulation.replications} simulated days. Pickers do up to 2 h overtime;
          anything left is picked the next day. Orders over 40 lines are split across carts.</p>
      </div>

      <div className="panel takeaways">
        <h3>What this says</h3>
        <ul>
          <li><b>Timing matters as much as head count.</b> The same 6 pickers on 08–16 leave 9.4% of lines to the
            next day, because the crew goes home before the afternoon orders are done.</li>
          <li><b>Best service:</b> 3 pickers on 09–17 and 3 on 11–19 cut late lines to 1.4% and cost 6.5% less.</li>
          <li><b>Timing can replace a picker:</b> 5 pickers on 10–18 do better than 6 on 08–16, at 19% lower cost.</li>
          <li><b>Checked in a second tool:</b> the same model rebuilt in Arena gives the same ranking, e.g. 9.1% vs
            9.4% late for 08–16 and 1.5% vs 1.4% for the split shift (details in the README).</li>
        </ul>
      </div>
    </div>
  );
}
