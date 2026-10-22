import { useEffect, useState } from "react";
import { API, get } from "./api.js";
import Plan from "./pages/Plan.jsx";
import Accuracy from "./pages/Accuracy.jsx";
import Rules from "./pages/Rules.jsx";
import Shifts from "./pages/Shifts.jsx";
import About from "./pages/About.jsx";

const TABS = [
  { id: "plan", label: "Plan" },
  { id: "accuracy", label: "Accuracy" },
  { id: "rules", label: "Staffing rules" },
  { id: "shifts", label: "Shifts" },
  { id: "about", label: "About" },
];
const GITHUB = "https://github.com/SanjayNalluri/warehouse-demand-forecast";

// tab lives in the URL hash (#plan, #accuracy...) so the back button and links work
const readTab = () => {
  const h = window.location.hash.replace("#", "");
  return TABS.some((t) => t.id === h) ? h : "plan";
};

export default function App() {
  const [tab, setTab] = useState(readTab);
  const [shared, setShared] = useState(null); // history, model info, backtest
  const [error, setError] = useState("");

  useEffect(() => {
    const onHash = () => setTab(readTab());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    Promise.all([get("/history", { days: 63 }), get("/model-info"), get("/backtest"), get("/simulation")])
      .then(([history, info, backtest, simulation]) => setShared({ history, info, backtest, simulation }))
      .catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <nav className="topbar">
        <div className="wrap topbar-inner">
          <a href="#plan" className="brand">Warehouse Demand Planner</a>
          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <a key={t.id} href={`#${t.id}`} role="tab" aria-selected={tab === t.id}
                 className={tab === t.id ? "tab active" : "tab"}>{t.label}</a>
            ))}
          </div>
          <a className="gh" href={GITHUB}>GitHub ↗</a>
        </div>
      </nav>

      <main className="wrap">
        {error && (
          <div className="msg error">
            Couldn't reach the API ({error}). Refresh in a moment,
            or <a href={`${API}/health`}>check it directly</a>.
          </div>
        )}
        {!shared && !error && (
          <div className="msg">Loading data… the first load can take a few seconds while the API starts.</div>
        )}

        {tab === "plan" && <Plan shared={shared} />}
        {tab === "accuracy" && shared && <Accuracy {...shared} />}
        {tab === "rules" && shared && <Rules {...shared} />}
        {tab === "shifts" && shared && <Shifts {...shared} />}
        {tab === "about" && <About info={shared?.info} />}
      </main>

      <footer className="wrap foot">
        Nalluri Sanjay · Industrial &amp; Systems Engineering, IIT Kharagpur ·{" "}
        <a href={GITHUB}>Code</a> · <a href={`${API}/docs`}>API docs</a>
      </footer>
    </>
  );
}
