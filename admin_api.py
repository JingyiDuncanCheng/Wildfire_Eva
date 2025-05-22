from flask import Blueprint, request, jsonify, session

# local helpers / constants
from core import (
    GOVERNMENT_USERS,
    USER_DB,
    WILDFIRE_DB,
    ROAD_CLOSURE_DB,
    get_db_connection,
)

# Blueprint for all administrator-only endpoints
admin_bp = Blueprint("admin", __name__)

# Admin login
@admin_bp.post("/api/admin_login")
def admin_login():
    data = request.get_json(force=True)
    username = data.get("username")
    password = data.get("password")

    if username in GOVERNMENT_USERS and GOVERNMENT_USERS[username] == password:
        session["admin"] = username
        return jsonify({"message": "Admin logged in"}), 200
    return jsonify({"error": "Invalid credentials"}), 401

# Admin logout
@admin_bp.post("/api/admin_logout")
def admin_logout():
    session.pop("admin", None)
    return jsonify({"message": "Logged out"}), 200

# Delete user by username
@admin_bp.post("/api/admin_delete_user")
def admin_delete_user():
    if "admin" not in session:
        return jsonify({"error": "Unauthorized"}), 403

    username = request.json.get("username")
    if not username:
        return jsonify({"error": "Username required"}), 400

    conn = get_db_connection(USER_DB)
    conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()

    return jsonify({"message": f"User {username} deleted"}), 200

# Delete wildfire record by ID
@admin_bp.post("/api/admin_delete_fire")
def admin_delete_fire():
    if "admin" not in session:
        return jsonify({"error": "Unauthorized"}), 403

    fid = request.json.get("id")
    if not fid:
        return jsonify({"error": "Fire ID required"}), 400

    conn = get_db_connection(WILDFIRE_DB)
    conn.execute("DELETE FROM wildfires WHERE id = ?", (fid,))
    conn.commit()
    conn.close()

    return jsonify({"message": f"Wildfire {fid} deleted"}), 200

# Delete road‑closure record by ID
@admin_bp.post("/api/admin_delete_road_closure")
def admin_delete_road_closure():
    if "admin" not in session:
        return jsonify({"error": "Unauthorized"}), 403

    cid = request.json.get("id")
    if not cid:
        return jsonify({"error": "Road closure ID required"}), 400

    conn = get_db_connection(ROAD_CLOSURE_DB)
    conn.execute("DELETE FROM road_closures WHERE id = ?", (cid,))
    conn.commit()
    conn.close()

    return jsonify({"message": f"Road closure {cid} deleted"}), 200

__all__ = [
    "admin_bp",
]