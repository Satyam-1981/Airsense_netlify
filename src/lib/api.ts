import type { Pollutants } from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(init?.headers);
    if (init?.body && !headers.has("content-type")) headers.set("content-type", "application/json");
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new Error(`Cannot reach the AirSense Python API at ${API_BASE}. Start the FastAPI service or configure VITE_API_BASE_URL.`);
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    throw new Error(typeof detail === "string" ? detail : `AirSense API request failed (${response.status}).`);
  }
  return payload as T;
}

export const searchCity = (city: string) => request<any>(`/air-quality/${encodeURIComponent(city)}`);
export const predictAqi = (pollutants: Pollutants) => request<any>("/predict", { method: "POST", body: JSON.stringify(pollutants) });
export const getForecast = (city: string) => request<any>(`/forecast/${encodeURIComponent(city)}`);
export const getStations = (city?: string, state?: string) => {
  const params = new URLSearchParams();
  if (city) params.set("city", city);
  if (state) params.set("state", state);
  const query = params.toString();
  return request<any>(`/stations${query ? `?${query}` : ""}`);
};
export const getModelMetrics = () => request<any>("/metrics");
export const getHealth = () => request<any>("/health");
