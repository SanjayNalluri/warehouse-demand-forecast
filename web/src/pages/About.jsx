import { API } from "../api.js";

const GITHUB = "https://github.com/SanjayNalluri/warehouse-demand-forecast";

export default function About() {
  return (
    <div className="stack narrow">
      <h2>About this project</h2>
      <p>
        A UK online wholesaler ships every order from one warehouse. Each product line on an order is one pick, so
        daily <b>pick lines</b> decide how many pickers are needed. This tool forecasts pick lines for the next 7 days
        and turns them into a staffing plan.
      </p>

      <h3>How it works</h3>
      <ol>
        <li><b>Data.</b> UCI Online Retail II: 1,067,371 order lines, Dec 2009 – Dec 2011. After removing
          cancellations, duplicates, postage and fee lines: 1,003,340 lines, 39,516 orders.</li>
        <li><b>Workload.</b> Pick lines per day. The warehouse is closed on Saturdays, UK bank holidays and over
          Christmas; that rule matches 737 of 738 days.</li>
        <li><b>Forecast.</b> LightGBM using weekday, season, last week, last year and recent growth. All inputs are
          at least 7 days old, so one model covers the whole week. 48 settings compared in MLflow; SHAP shows weekday
          and days-to-Christmas matter most.</li>
        <li><b>Staffing.</b> Pickers = forecast lines ÷ lines one picker does per shift, rounded up.</li>
      </ol>

      <h3>Assumptions</h3>
      <p className="muted">
        Pick rate 80 lines per picker-hour, 8-hour shifts, 85% of the shift spent picking, overtime up to 2 hours at
        1.5×. No public source gives one pick rate for this kind of warehouse, so it is adjustable on the Plan page and
        tested from 60 to 120.
      </p>

      <h3>Built with</h3>
      <p className="muted">Python, pandas, LightGBM, MLflow, SHAP · FastAPI, Docker, pytest, GitHub Actions · React, Recharts · Render, Vercel</p>

      <p><a href={GITHUB}>Code on GitHub</a> · <a href={`${API}/docs`}>API documentation</a></p>
    </div>
  );
}
