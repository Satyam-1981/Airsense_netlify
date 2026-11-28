import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export default function MapView({
  center,
  markers = [],
  zoom = 11,
  routeCoordinates = [],
  className = "",
}) {
  const element = useRef(null);

  useEffect(() => {
    if (!element.current) return undefined;
    const fallback = [22.5, 79];
    const initialCenter =
      Array.isArray(center) && center.length === 2 ? center : fallback;
    const map = L.map(element.current, { scrollWheelZoom: false }).setView(
      initialCenter,
      zoom,
    );
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const validMarkers = markers.filter(
      (item) =>
        item.latitude !== null &&
        item.latitude !== undefined &&
        item.latitude !== "" &&
        item.longitude !== null &&
        item.longitude !== undefined &&
        item.longitude !== "" &&
        Number.isFinite(Number(item.latitude)) &&
        Number.isFinite(Number(item.longitude)) &&
        Math.abs(Number(item.latitude)) <= 90 &&
        Math.abs(Number(item.longitude)) <= 180,
    );
    const points = [];
    validMarkers.forEach((item) => {
      const statusClass =
        item.status === "verified"
          ? "is-verified"
          : item.status === "pending"
            ? "is-pending"
            : "is-station";
      const icon = L.divIcon({
        className: "airsense-pin-shell",
        html: `<span class="airsense-pin ${statusClass}"></span>`,
        iconSize: [26, 26],
        iconAnchor: [13, 13],
      });
      const marker = L.marker([Number(item.latitude), Number(item.longitude)], {
        icon,
      }).addTo(map);
      const popup = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = item.title || "AtmoIQ location";
      popup.appendChild(title);
      if (item.subtitle) {
        const subtitle = document.createElement("p");
        subtitle.textContent = item.subtitle;
        popup.appendChild(subtitle);
      }
      marker.bindPopup(popup);
      points.push([Number(item.latitude), Number(item.longitude)]);
    });
    if (Array.isArray(routeCoordinates) && routeCoordinates.length > 1) {
      const routeLine = L.polyline(
        routeCoordinates.map(([lon, lat]) => [lat, lon]),
        { color: "#247d70", weight: 5, opacity: 0.82 },
      ).addTo(map);
      map.fitBounds(routeLine.getBounds(), { padding: [28, 28] });
    }
    if (points.length > 1 && !(routeCoordinates?.length > 1))
      map.fitBounds(L.latLngBounds(points), { padding: [28, 28], maxZoom: 13 });
    else if (points.length === 1) map.setView(points[0], 13);

    return () => map.remove();
  }, [
    center?.[0],
    center?.[1],
    zoom,
    JSON.stringify(markers),
    JSON.stringify(routeCoordinates),
  ]);

  return (
    <div
      className={`map-view ${className}`}
      ref={element}
      role="application"
      aria-label="Map showing air-quality locations"
    />
  );
}
