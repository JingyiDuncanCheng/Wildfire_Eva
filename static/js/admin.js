/* Same helper we used in sidebar.js */
const $   = id  => document.getElementById(id);
const api = (path, body) => fetch(path, {
  method:"POST",
  headers:{ "Content-Type":"application/json" },
  body: JSON.stringify(body)
});

/* ----------  LOGIN / LOGOUT  --------------- */
async function adminLogin() {
  const res = await api("/api/admin_login", {
    username: $("#adminUsername").value,
    password: $("#adminPassword").value
  });
  if (res.ok) {
    alert("Admin logged in.");
    $("#loginSection").style.display  = "none";
    $("#adminActions").style.display = "block";
  } else { alert("Invalid credentials."); }
}

async function adminLogout() {
  await api("/api/admin_logout", {});
  alert("Admin logged out.");
  location.reload();
}

/* ----------  DELETE ACTIONS ---------------- */
const deleteUser        = () => api("/api/admin_delete_user",        { username: $("#deleteUserInput").value });
const deleteWildfire    = () => api("/api/admin_delete_fire",        { id: $("#deleteFireInput").value     });
const deleteRoadClosure = () => api("/api/admin_delete_road_closure",{ id: $("#deleteRoadInput").value    });

/* -- export helpers for admin buttons ---------------------------- */
window.adminLogin         = adminLogin;
window.adminLogout        = adminLogout;
window.deleteUser         = deleteUser;
window.deleteWildfire     = deleteWildfire;
window.deleteRoadClosure  = deleteRoadClosure;
