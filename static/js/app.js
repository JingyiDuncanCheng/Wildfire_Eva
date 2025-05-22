/* global L, CURRENT_USER *****************************************************
   ONE SINGLE FILE – nothing can load in the wrong order any more
******************************************************************************/

/* -------------------  DOM ELEMENT SHORTCUT  ------------------------------- */
const $ = id => document.getElementById(id);

/* --------------------------------------------------------------------------
   MAP INITIALISATION
--------------------------------------------------------------------------- */
const map = L.map("map").setView([53.7267, -127.6476], 6);
L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  { attribution: "Map ©Carto · Data ©OpenStreetMap" }
).addTo(map);

/* ICONS */
const icon = (file, size = 32) => L.icon({
  iconUrl: `/static/img/${file}`,
  iconSize:[size,size], iconAnchor:[10,10], popupAnchor:[0,-10]
});
const fireIcon  = icon("fire.png");
const roadIcon  = icon("x.png", 30);
const userIcon  = icon("user.png");

/* --------------------------------------------------------------------------
   PANEL TOGGLE
--------------------------------------------------------------------------- */
function switchPanel(show) {
  const emergency = $("#emergencyPanel");
  const admin     = $("#adminPanel");
  const be        = $("#btnEmergency");
  const ba        = $("#btnAdmin");

  const on  = show === "emergency";
  emergency.style.display = on ? "block":"none";
  admin.style.display     = on ? "none":"block";

  be.classList.toggle("btn-success", on);
  be.classList.toggle("btn-outline-success", !on);
  be.classList.toggle("active", on);

  ba.classList.toggle("btn-success", !on);
  ba.classList.toggle("btn-outline-success", on);
  ba.classList.toggle("active", !on);
}

/* --------------------------------------------------------------------------
   EMERGENCY SIDE – helpers
--------------------------------------------------------------------------- */
async function addFireLocation() {
  const lat = parseFloat($("#latInput").value);
  const lng = parseFloat($("#lngInput").value);
  if (isNaN(lat)||isNaN(lng)) return alert("Pick a valid location.");

  const res = await fetch("/api/add_fire", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({
      latitude:lat, longitude:lng,
      description: $("#fireDesc").value || "Wildfire Alert",
      reason:      $("#fireCause").value || "Unknown"
    })
  });
  res.ok ? alert("Wildfire reported!") : alert("Failed.");
}

async function addRoadClosure() {
  const lat = parseFloat($("#latInput").value);
  const lng = parseFloat($("#lngInput").value);
  if (isNaN(lat)||isNaN(lng)) return alert("Pick a location.");

  const res = await fetch("/api/report_road_closure", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({
      latitude:lat, longitude:lng,
      reason: $("#roadReason").value || "Unknown"
    })
  });
  res.ok ? alert("Closure added!") : alert("Failed.");
}

async function setUserLocation() {
  const lat = parseFloat($("#latInput").value);
  const lng = parseFloat($("#lngInput").value);
  if (isNaN(lat)||isNaN(lng)) return alert("Pick a location.");

  const r = await fetch("/api/set_user_location",{
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ latitude:lat, longitude:lng })
  });
  if (r.ok) { alert("Location saved!"); updateUserMarker(lat,lng); }
}

function updateUserMarker(lat,lng){
  if (window.userMarker) map.removeLayer(window.userMarker);
  window.userMarker = L.marker([lat,lng],{icon:userIcon})
    .addTo(map).bindPopup("Your Location").openPopup();
}

async function addVehicle() {
  const lat = parseFloat($("#vehicleLat").value);
  const lng = parseFloat($("#vehicleLng").value);
  const cap = parseInt($("#vehicleCapacity").value);
  if (isNaN(lat)||isNaN(lng)||isNaN(cap)||cap<=0) return alert("Fill data.");

  const r = await fetch("/api/add_vehicle",{
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({
      latitude:lat, longitude:lng,
      capacity:cap, vehicle_type:$("#vehicleType").value
    })
  });
  r.ok ? alert("Vehicle added!") : alert("Failed.");
}

async function logoutApp(){
  await fetch("/api/logout_user",{
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ username: CURRENT_USER })
  }).catch(()=>{});
  location.href = "/logout";
}

/* --------------------------------------------------------------------------
   ADMIN SIDE
--------------------------------------------------------------------------- */
async function adminLogin() {
  const r = await fetch("/api/admin_login",{
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({
      username:$("#adminUsername").value,
      password:$("#adminPassword").value
    })
  });
  if (r.ok){
    alert("Admin logged in");
    $("#loginSection").style.display="none";
    $("#adminActions").style.display="block";
  } else alert("Bad credentials");
}
async function adminLogout(){ await fetch("/api/admin_logout",{method:"POST"});
  alert("Admin logged out"); location.reload(); }

const deleteUser        = () => fetch("/api/admin_delete_user",
  {method:"POST",headers:{ "Content-Type":"application/json" },
   body:JSON.stringify({username:$("#deleteUserInput").value})});

const deleteWildfire    = () => fetch("/api/admin_delete_fire",
  {method:"POST",headers:{ "Content-Type":"application/json" },
   body:JSON.stringify({id:$("#deleteFireInput").value})});

const deleteRoadClosure = () => fetch("/api/admin_delete_road_closure",
  {method:"POST",headers:{ "Content-Type":"application/json" },
   body:JSON.stringify({id:$("#deleteRoadInput").value})});

/* --------------------------------------------------------------------------
   MAP LOADERS
--------------------------------------------------------------------------- */
async function loadWildfires(){
  const r = await fetch("/api/get_fires"); const data = await r.json();
  data.forEach(f => L.marker([f.latitude,f.longitude],{icon:fireIcon})
    .addTo(map)
    .bindPopup(`<b>🔥 ${f.description}</b><br>${f.reason}<br>${f.latitude},${f.longitude}`));
}
async function loadRoadClosures(){
  const r = await fetch("/api/get_road_closures"); const data = await r.json();
  data.forEach(c => L.marker([c.latitude,c.longitude],{icon:roadIcon})
    .addTo(map)
    .bindPopup(`<b>❌ Road Closure</b><br>${c.reason}<br>${c.latitude},${c.longitude}`));
}

async function loadJasperRoads(){
  try{
    const r = await fetch("/api/jasper_roads");
    L.geoJSON(await r.json(),{style:()=>({weight:2,color:"gray"})}).addTo(map);
  }catch(e){console.error("roads",e);}
}

/* --------------------------------------------------------------------------
   BUTTON → FUNCTION WIRING   (no inline onclick="" anymore)
--------------------------------------------------------------------------- */
function hook(id, fn){ $(id).addEventListener("click",fn); }

hook("btnEmergency",   ()=>switchPanel("emergency"));
hook("btnAdmin",       ()=>switchPanel("admin"));
hook("setUser",        setUserLocation);     // (see below same IDs)
hook("addFire",        addFireLocation);
hook("addRoad",        addRoadClosure);
hook("addVehicle",     addVehicle);
hook("logoutUserBtn",  logoutApp);

hook("adminLoginBtn",  adminLogin);
hook("adminLogoutBtn", adminLogout);
hook("delUserBtn",     deleteUser);
hook("delFireBtn",     deleteWildfire);
hook("delRoadBtn",     deleteRoadClosure);

/* --------------------------------------------------------------------------
   INITIALISE EVERYTHING
--------------------------------------------------------------------------- */
map.on("click", e=>{
  $("#latInput").value = e.latlng.lat.toFixed(5);
  $("#lngInput").value = e.latlng.lng.toFixed(5);
});

loadWildfires();
loadRoadClosures();
loadJasperRoads();
switchPanel("emergency");  // default view
