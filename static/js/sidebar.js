/* Helpers shared by the sidebar *********************************************/
const $   = id  => document.getElementById(id);
const api = (path, body) =>
  fetch(path, { method:"POST",
                headers:{ "Content-Type":"application/json" },
                body: JSON.stringify(body) });

/* ----------  PANEL TOGGLE ------------------- */
function switchPanel(panel) {
  const e  = $("#emergencyPanel"), a = $("#adminPanel");
  const be = $("#btnEmergency"),   ba = $("#btnAdmin");
  const show = (on, off, bon, boff) => {
    on.style.display  = "block"; off.style.display = "none";
    bon.classList.add("btn-success","active");
    bon.classList.remove("btn-outline-success");
    boff.classList.add("btn-outline-success");
    boff.classList.remove("btn-success","active");
  };
  panel === "emergency" ? show(e, a, be, ba) : show(a, e, ba, be);
}

/* ----------  EMERGENCY ACTIONS ------------- */
async function addFireLocation() {
  const lat = parseFloat($("#latInput").value);
  const lng = parseFloat($("#lngInput").value);
  if (isNaN(lat) || isNaN(lng)) return alert("Pick a valid location.");

  const res = await api("/api/add_fire", {
    latitude: lat, longitude: lng,
    description: $("#fireDesc").value || "Wildfire Alert",
    reason:      $("#fireCause").value || "Unknown"
  });
  res.ok ? alert("Wildfire reported!") : alert("Failed to add wildfire.");
}

async function addRoadClosure() {
  const lat = parseFloat($("#latInput").value);
  const lng = parseFloat($("#lngInput").value);
  if (isNaN(lat) || isNaN(lng)) return alert("Pick a valid location.");
  const res = await api("/api/report_road_closure", {
    latitude: lat, longitude: lng,
    reason: $("#roadReason").value || "Unknown"
  });
  res.ok ? alert("Road closure added!") : alert("Failed to add closure.");
}

async function setUserLocation() {
  const lat = parseFloat($("#latInput").value);
  const lng = parseFloat($("#lngInput").value);
  if (isNaN(lat) || isNaN(lng)) return alert("Pick a valid location.");
  const r = await api("/api/set_user_location", { latitude:lat, longitude:lng });
  if (r.ok) { alert("Location saved!"); updateUserMarker(lat, lng); }
}

async function addVehicle() {
  const lat = parseFloat($("#vehicleLat").value);
  const lng = parseFloat($("#vehicleLng").value);
  const cap = parseInt($("#vehicleCapacity").value);
  if (isNaN(lat)||isNaN(lng)||isNaN(cap)||cap<=0) return alert("Fill vehicle data.");
  const res = await api("/api/add_vehicle", {
    latitude:lat, longitude:lng, capacity:cap, vehicle_type: $("#vehicleType").value
  });
  res.ok ? alert("Vehicle added!") : alert("Failed to add vehicle.");
}

function reloadMap()  { location.reload(); }

async function logoutApp() {
  try { await api("/api/logout_user", { username: CURRENT_USER }); } catch(_) {}
  window.location.href = "/logout";
}

window.switchPanel      = switchPanel;
window.setUserLocation  = setUserLocation;
window.addFireLocation  = addFireLocation;
window.addRoadClosure   = addRoadClosure;
window.addVehicle       = addVehicle;
window.reloadMap        = reloadMap;
window.logoutApp        = logoutApp;
/* --- nothing else needed; everything is global now --- */
