export const AQI_COLORS = {
  Good: "#36a987",
  Satisfactory: "#8cbf58",
  Moderate: "#e2b14f",
  Poor: "#df8554",
  "Very Poor": "#ce625d",
  Severe: "#8d557c",
};

export function formatTime(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not available" : date.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

export function pollutantLabel(key) {
  return ({ pm25: "PM2.5", pm10: "PM10", no2: "NO₂", so2: "SO₂", co: "CO", o3: "O₃", nh3: "NH₃" })[key] || key;
}

export function pollutantUnit(key) {
  return key === "co" ? "mg/m³" : "µg/m³";
}

export function readFavourites() {
  try {
    const saved = JSON.parse(localStorage.getItem("airsense-favourites") || "[]");
    return Array.isArray(saved) ? saved.filter((item) => typeof item === "string").slice(0, 5) : [];
  } catch { return []; }
}

export function getClientId() {
  let value = localStorage.getItem("airsense-client-id");
  if (!value) {
    value = crypto.randomUUID();
    localStorage.setItem("airsense-client-id", value);
  }
  return value;
}

export function getHealthAdvice(category) {
  const advice = {
    Good: ["Air quality is generally satisfactory, with minimal expected health impact.", "Normal outdoor activities can continue."],
    Satisfactory: ["Sensitive people may experience minor breathing discomfort.", "Most people can continue normal activity; sensitive groups should reduce prolonged or strenuous outdoor exertion."],
    Moderate: ["People with lung or heart disease, children and older adults may experience breathing discomfort.", "Sensitive groups should avoid prolonged or strenuous outdoor exertion; others should limit extended heavy exertion."],
    Poor: ["Prolonged exposure may cause breathing discomfort, including among the wider population.", "Reduce the duration and intensity of outdoor exertion, especially for children, older adults and people with existing conditions."],
    "Very Poor": ["Prolonged exposure may increase the risk of respiratory illness.", "Reduce outdoor exposure and follow local health advisories; sensitive groups should take extra care."],
    Severe: ["Respiratory effects may occur even in healthy people, with greater risk for people with lung or heart disease.", "Avoid unnecessary outdoor exertion and follow official local advisories."],
  };
  return advice[category] || ["Air quality information is not available yet.", "Check official local advisories and refresh the latest readings."];
}
