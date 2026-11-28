
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  "https://atmoiq-aqi-server.onrender.com"
).replace(/\/+$/, "");

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

  const response = await fetch(`${API_BASE_URL}/api/csrf/`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Could not establish a secure session with the API.");
  }

  // Cross-origin cookies must be accessible to the frontend.
  if (!readCookie("csrftoken")) {
    throw new Error(
      "Could not read the API CSRF token. Check backend cookie settings."
    );
  }
}

async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();

  const headers =
    options.body instanceof FormData
      ? { ...(options.headers || {}) }
      : {
          "Content-Type": "application/json",
          ...(options.headers || {}),
        };

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    await ensureCsrfToken();
    headers["X-CSRFToken"] = readCookie("csrftoken");
  }

  const response = await fetch(
    `${API_BASE_URL}/api/${path}`,
    {
      ...options,
      method,
      headers,
      credentials: "include",
    }
  );

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      payload.error || `Request failed (${response.status}).`
    );
  }

  return payload;
}
