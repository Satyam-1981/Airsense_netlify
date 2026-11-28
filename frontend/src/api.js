

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  "https://atmoiq-aqi-server.onrender.com"
).replace(/\/+$/, "");

/**
 * Read a cookie by name.
 */
function readCookie(name) {
  const prefix = `${name}=`;

  const item = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix));

  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

/**
 * Ensure a CSRF token exists before sending unsafe requests.
 */
async function ensureCsrfToken() {
  if (readCookie("csrftoken")) return;

  const response = await fetch(`${API_BASE_URL}/api/csrf/`, {
    credentials: "include",
  });

  if (!response.ok || !readCookie("csrftoken")) {
    throw new Error(
      "Could not establish a secure session with the API. " +
        "Refresh the page and try again."
    );
  }
}

/**
 * Make an API request to the Django backend.
 */
async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();

  const headers =
    options.body instanceof FormData
      ? { ...(options.headers || {}) }
      : {
          "Content-Type": "application/json",
          ...(options.headers || {}),
        };

  // CSRF protection for unsafe HTTP methods.
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    await ensureCsrfToken();

    headers["X-CSRFToken"] = readCookie("csrftoken");
  }

  const response = await fetch(
    `${API_BASE_URL}/api/${path.replace(/^\/+/, "")}`,
    {
      ...options,
      method,
      headers,
      credentials: "include",
    }
  );

  // Handle JSON responses and non-JSON error responses.
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      payload.error || `Request failed (${response.status}).`
    );
  }

  return payload;
}

/**
 * AtmoIQ API methods.
 */
export const api = {
  // Current air quality for a city.
  city: (city) =>
    request(`city/?city=${encodeURIComponent(city)}`),

  // Air quality forecast.
  forecast: (city) =>
    request(`forecast/?city=${encodeURIComponent(city)}`),

  // India monitoring station network.
  indiaNetwork: () =>
    request("network/india/"),

  // Detected pollution hotspots.
  detectedHotspots: (city = "") =>
    request(
      `hotspots/detected/?city=${encodeURIComponent(city)}`
    ),

  // Compare air quality along a route.
  route: (start, end) =>
    request(
      `route/?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
    ),

  // Health advice based on AQI.
  advice: (aqi) =>
    request(`advice/?aqi=${encodeURIComponent(aqi)}`),

  // Monitoring stations near a city or coordinates.
  stations: ({ city, lat, lon } = {}) => {
    const params = new URLSearchParams();

    if (city) {
      params.set("city", city);
    }

    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      params.set("lat", String(lat));
      params.set("lon", String(lon));
    }

    return request(`stations/?${params.toString()}`);
  },

  // Predict AQI from pollutant values.
  predict: (pollutants) =>
    request("predict/", {
      method: "POST",
      body: JSON.stringify({ pollutants }),
    }),

  // Pollutant sensitivity analysis.
  sensitivity: (pollutants) =>
    request("sensitivity/", {
      method: "POST",
      body: JSON.stringify({ pollutants }),
    }),

  // Machine learning model metrics.
  metrics: () =>
    request("ml/metrics/"),

  // Historical air quality data.
  history: (city, days = 30) =>
    request(
      `history/?city=${encodeURIComponent(city || "")}&days=${encodeURIComponent(days)}`
    ),

  // Air quality anomalies.
  anomalies: (city) =>
    request(
      `anomalies/?city=${encodeURIComponent(city || "")}`
    ),

  // All pollution hotspots.
  hotspots: () =>
    request("hotspots/"),

  // Submit a pollution hotspot report.
  submitHotspot: (formData) =>
    request("hotspots/", {
      method: "POST",
      body: formData,
    }),

  // Retrieve an exposure record.
  exposure: (clientId) =>
    request(
      `exposure/?client_id=${encodeURIComponent(clientId)}`
    ),

  // Save an exposure record.
  saveExposure: (record) =>
    request("exposure/", {
      method: "POST",
      body: JSON.stringify(record),
    }),

  // Delete an exposure record.
  deleteExposure: (clientId) =>
    request(
      `exposure/?client_id=${encodeURIComponent(clientId)}`,
      {
        method: "DELETE",
      }
    ),
};
