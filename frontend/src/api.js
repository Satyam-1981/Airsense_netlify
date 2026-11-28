function readCookie(name) {
  const prefix = `${name}=`;
  const item = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

async function ensureCsrfToken() {
  if (readCookie("csrftoken")) return;
  const response = await fetch("/api/csrf/", { credentials: "same-origin" });
  if (!response.ok || !readCookie("csrftoken")) {
    throw new Error(
      "Could not establish a secure session with the API. Refresh the page and try again.",
    );
  }
}

async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers =
    options.body instanceof FormData
      ? { ...(options.headers || {}) }
      : { "Content-Type": "application/json", ...(options.headers || {}) };

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    await ensureCsrfToken();
    headers["X-CSRFToken"] = readCookie("csrftoken");
  }

  const response = await fetch(`/api/${path}`, {
    ...options,
    method,
    headers,
    credentials: "same-origin",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(payload.error || `Request failed (${response.status}).`);
  return payload;
}

export const api = {
  city: (city) => request(`city/?city=${encodeURIComponent(city)}`),
  forecast: (city) => request(`forecast/?city=${encodeURIComponent(city)}`),
  indiaNetwork: () => request("network/india/"),
  detectedHotspots: (city = "") =>
    request(`hotspots/detected/?city=${encodeURIComponent(city)}`),
  route: (start, end) =>
    request(
      `route/?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`,
    ),
  advice: (aqi) => request(`advice/?aqi=${encodeURIComponent(aqi)}`),
  stations: ({ city, lat, lon }) => {
    const params = new URLSearchParams();
    if (city) params.set("city", city);
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      params.set("lat", String(lat));
      params.set("lon", String(lon));
    }
    return request(`stations/?${params.toString()}`);
  },
  predict: (pollutants) =>
    request("predict/", {
      method: "POST",
      body: JSON.stringify({ pollutants }),
    }),
  sensitivity: (pollutants) =>
    request("sensitivity/", {
      method: "POST",
      body: JSON.stringify({ pollutants }),
    }),
  metrics: () => request("ml/metrics/"),
  history: (city, days = 30) =>
    request(`history/?city=${encodeURIComponent(city || "")}&days=${days}`),
  anomalies: (city) =>
    request(`anomalies/?city=${encodeURIComponent(city || "")}`),
  hotspots: () => request("hotspots/"),
  submitHotspot: (formData) =>
    request("hotspots/", { method: "POST", body: formData }),
  exposure: (clientId) =>
    request(`exposure/?client_id=${encodeURIComponent(clientId)}`),
  saveExposure: (record) =>
    request("exposure/", { method: "POST", body: JSON.stringify(record) }),
  deleteExposure: (clientId) =>
    request(`exposure/?client_id=${encodeURIComponent(clientId)}`, {
      method: "DELETE",
    }),
};
