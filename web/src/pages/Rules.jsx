export default function Rules({ backtest }) {
  const rules = backtest.staffing_rules;
  const maxCost = Math.max(...rules.map((r) => Math.abs(r.cost_vs_flat_pct)));
  const maxLate = Math.max(...rules.map((r) => r.late_lines_pct));

  return (
    <div className="stack">
      <div>
        <h2>Which staffing rule should the warehouse use?</h2>
        <p className="intro">
          Each rule set the number of pickers a week ahead. Then the real orders for Jul – Dec 2011 came in. If the
          crew fell short, pickers did up to 2 hours of overtime; anything still left was picked the next day.
          Labour cost counts overtime at 1.5×.
        </p>
      </div>

      <div className="panel">
        <table className="grid rules">
          <thead>
            <tr><th>Rule</th><th className="r">Avg pickers</th><th>Lines picked late</th><th>Labour cost vs flat crew</th></tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.rule} className={r.rule === "Forecast P75" ? "mark" : ""}>
                <td>{r.rule}</td>
                <td className="r">{r.avg_pickers}</td>
                <td><Meter value={r.late_lines_pct} max={maxLate} label={`${r.late_lines_pct}%`} color="var(--wine)" /></td>
                <td><Meter value={r.cost_vs_flat_pct} max={maxCost} signed
                           label={`${r.cost_vs_flat_pct > 0 ? "+" : ""}${r.cost_vs_flat_pct}%`} color="var(--blue)" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel takeaways">
        <h3>What this says</h3>
        <ul>
          <li><b>Forecast P50</b> is 3% cheaper than a flat crew of 4 <i>and</i> cuts late lines from 6.4% to 2.1%.</li>
          <li><b>Forecast P75</b> gets late lines under 1% for 7.7% more labour. This is the default on the Plan page.</li>
          <li><b>Forecast P90</b> is nearly never late, but costs 22% more. The last 0.7% of service is expensive.</li>
          <li>The order of the rules stays the same for pick rates from 60 to 120 lines per hour.</li>
        </ul>
      </div>
    </div>
  );
}

function Meter({ value, max, label, color, signed }) {
  const w = Math.max(2, (Math.abs(value) / max) * 100);
  return (
    <div className="meter">
      <div className="track">
        <div className="fill" style={{ width: `${signed ? w / 2 : w}%`, background: color,
             marginLeft: signed ? (value < 0 ? `${50 - w / 2}%` : "50%") : 0 }} />
        {signed && <div className="zero" />}
      </div>
      <span>{label}</span>
    </div>
  );
}
