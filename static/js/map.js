/* global L, CURRENT_USER ****************************************************/
/*  This file is now plain script — everything you declare lives on window   */

/* ----------  MAP & LAYERS  ------------------ */
const map = L.map("map").setView([53.7267, -127.6476], 6);
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: "Map tiles © Carto · Data © OpenStreetMap"
}).addTo(map);

/* ----------  ICONS  ------------------------- */
function icon(file, size = 32) {
  return L.icon({
    iconUrl: `/static/img/${file}`,
    iconSize:   [size, size],
    iconAnchor: [10, 10],
    popupAnchor:[0, -10]
  });
}
const fireIcon        = icon("fire.png");
const roadClosureIcon = icon("x.png", 30);
const userIcon        = icon("user.png");

/* ----------  GEOJSON (Jasper demo) ---------- */
async function loadJasperRoads() {
  try {
    const r = await fetch("/api/jasper_roads");
    if (!r.ok) throw new Error("fetch failed");
    const data = await r.json();
    L.geoJSON(data, { style: () => ({ weight: 2, color: "gray" }) }).addTo(map);
  } catch (err) { console.error("Jasper roads:", err); }
}

/* ----------  DATA LOADERS ------------------- */
async function loadWildfires() {
  const res = await fetch("/api/get_fires");
  const fires = await res.json();
  fires.forEach(f =>
    L.marker([f.latitude, f.longitude], { icon: fireIcon })
      .addTo(map)
      .bindPopup(`<b>🔥 ${f.description}</b><br>Cause: ${f.reason}<br>📍 ${f.latitude}, ${f.longitude}`)
  );
}

async function loadRoadClosures() {
  const res = await fetch("/api/get_road_closures");
  const cls = await res.json();
  cls.forEach(c =>
    L.marker([c.latitude, c.longitude], { icon: roadClosureIcon })
      .addTo(map)
      .bindPopup(`<b>❌ Road Closure</b><br>Reason: ${c.reason}<br>📍 ${c.latitude}, ${c.longitude}`)
  );
}

/* ----------  USER MARKER HELPERS ------------ */
function updateUserMarker(lat, lng) {
  if (window.userMarker) map.removeLayer(window.userMarker);
  window.userMarker = L.marker([lat, lng], { icon: userIcon })
    .addTo(map)
    .bindPopup("Your Location")
    .openPopup();
}
function removeUserMarker() {
  if (window.userMarker) map.removeLayer(window.userMarker);
}

/* ----------  CLICK TO FILL INPUTS ----------- */
map.on("click", e => {
  document.getElementById("latInput").value = e.latlng.lat.toFixed(5);
  document.getElementById("lngInput").value = e.latlng.lng.toFixed(5);
});

/* ----------  INITIALISE --------------------- */
loadJasperRoads();
loadWildfires();
loadRoadClosures();
