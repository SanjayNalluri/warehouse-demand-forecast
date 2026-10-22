export const num = (n) => Math.round(n).toLocaleString("en-GB");
export const day = (d) => new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
export const weekday = (d) => new Date(d).toLocaleDateString("en-GB", { weekday: "long" });

// shared chart styling
export const axis = { tick: { fill: "var(--muted)", fontSize: 12 }, stroke: "var(--line)" };
export const tip = {
  contentStyle: { background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 6, fontSize: 13 },
  formatter: (v) => (Array.isArray(v) ? `${num(v[0])} – ${num(v[1])}` : num(v)),
  labelFormatter: day,
};
