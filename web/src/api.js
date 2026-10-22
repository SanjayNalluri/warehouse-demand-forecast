// Base URL of the FastAPI backend, set in Vercel as VITE_API_URL
export const API = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export async function get(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${API}${path}${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}
