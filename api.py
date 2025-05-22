import math
from flask import Blueprint, request, jsonify, session
from core import (
    _graph_edges, _graph_nodes, _mesh_gdf, _nearest_node, _fire_layers_cached,
    G_ROUTE, P_DB, ROAD_CLOSURE_DB, WILDFIRE_DB,
    USER_DB, VEHICLE_DB, haversine_distance, get_db_connection
)
from service import notify_users_nearby, allocate_vehicles_for_fire
import networkx as nx
from shapely.geometry import box, LineString
from admin_api import admin_bp

api_bp = Blueprint("api", __name__)
api_bp.register_blueprint(admin_bp)

@api_bp.route("/api/fire_layers")
def api_fire_layers():
    return jsonify(_fire_layers_cached())

@api_bp.route("/api/add_fire", methods=["POST"])
def add_fire():
    data = request.json
    lat = data.get("latitude")
    lng = data.get("longitude")
    desc = data.get("description", "Wildfire Alert")
    reason = data.get("reason", "Unknown Cause")

    if lat is None or lng is None:
        return jsonify({"error": "Latitude and Longitude are required."}), 400

    # Insert wildfire into DB
    conn = get_db_connection(WILDFIRE_DB)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO wildfires (latitude, longitude, description, reason)
           VALUES (?, ?, ?, ?)""",
        (lat, lng, desc, reason)
    )
    conn.commit()
    conn.close()

    # Notify users
    notified_users = notify_users_nearby(lat, lng)

    # Allocate vehicles
    vehicle_info = allocate_vehicles_for_fire(lat, lng)

    return jsonify({
        "message": "Fire added successfully",
        "notified_users": notified_users,
        "allocated_vehicles": vehicle_info
    }), 201

# Returns all wildfires as JSON (latitude, longitude, description, reason).
@api_bp.route("/api/get_fires", methods=["GET"])
def get_fires():
    conn = get_db_connection(WILDFIRE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, latitude, longitude, description, reason FROM wildfires")
    fires = cursor.fetchall()
    conn.close()

    fire_list = [
        {
            "id": row["id"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "description": row["description"],
            "reason": row["reason"]
        }
        for row in fires
    ]
    return jsonify(fire_list)

@api_bp.route("/api/fire_detail/<int:fire_id>")
def fire_detail(fire_id: int):
    conn   = get_db_connection(WILDFIRE_DB)
    cursor = conn.execute(
        "SELECT id, latitude, longitude, description, reason "
        "FROM wildfires WHERE id=?", (fire_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "not found"}), 404

# Adaptive mesh
@api_bp.route("/api/adaptive_mesh", methods=["GET"])
def api_adaptive_mesh():
    try:
        lat  = float(request.args["lat"])
        lng  = float(request.args["lng"])
        half = float(request.args.get("km", 5))
    except (KeyError, ValueError):
        return jsonify({"error":"lat,lng query params required"}), 400
    
    # 1 lat ≈ 111 km
    d_lat =  half / 111.0
    d_lng =  half / (111.0 * math.cos(math.radians(lat)))
    bb = box(lng-d_lng, lat-d_lat, lng+d_lng, lat+d_lat)

    mesh = _mesh_gdf()
    clipped = mesh.loc[mesh.intersects(bb)]
    return jsonify(clipped.__geo_interface__)

@api_bp.route("/api/road_graph")
def api_road_graph():
    try:
        lat  = float(request.args["lat"])
        lng  = float(request.args["lng"])
        half = float(request.args.get("km", 5))
    except (KeyError, ValueError):
        return jsonify({"error": "lat,lng query params required"}), 400

    d_lat = half / 111.0
    d_lng = half / (111.0 * math.cos(math.radians(lat)))
    bb = box(lng - d_lng, lat - d_lat, lng + d_lng, lat + d_lat)

    edges_clip = _graph_edges().loc[_graph_edges().intersects(bb)]
    nodes_clip = _graph_nodes().loc[_graph_nodes().intersects(bb)]

    return jsonify({
        "edges": edges_clip.__geo_interface__,
        "nodes": nodes_clip.__geo_interface__
    })

# ROAD CLOSURE ROUTES
# Receives JSON with lat, lng, reason for a road closure, inserts into 'road_closures.db'.
@api_bp.route("/api/report_road_closure", methods=["POST"])
def report_road_closure():
    data = request.json
    lat = data.get("latitude")
    lng = data.get("longitude")
    reason = data.get("reason", "Unknown")

    if lat is None or lng is None:
        return jsonify({"error": "Latitude and Longitude are required."}), 400

    conn = get_db_connection(ROAD_CLOSURE_DB)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO road_closures (latitude, longitude, reason)
           VALUES (?, ?, ?)""",
        (lat, lng, reason)
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Road closure reported successfully"}), 201

@api_bp.route("/api/get_road_closures", methods=["GET"])
def get_road_closures():
    """
    Returns all road closures as JSON (latitude, longitude, reason).
    """
    conn = get_db_connection(ROAD_CLOSURE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, latitude, longitude, reason FROM road_closures")
    closures = cursor.fetchall()
    conn.close()

    closure_list = [
        {
            "id": row["id"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "reason": row["reason"]
        }
        for row in closures
    ]
    return jsonify(closure_list)

# USER LOCATION ROUTES
@api_bp.route("/api/set_user_location", methods=["POST"])
def set_user_location():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    lat = data.get("latitude")
    lng = data.get("longitude")
    username = session["username"]

    if lat is None or lng is None:
        return jsonify({"error": "Latitude and Longitude are required."}), 400

    conn = get_db_connection(USER_DB)
    cursor = conn.cursor()
    # Upsert approach for user location
    cursor.execute(
        """
        INSERT INTO users (username, latitude, longitude) VALUES (?, ?, ?) ON CONFLICT(username)
        DO UPDATE SET latitude = excluded.latitude, longitude = excluded.longitude
        """,
        (username, lat, lng)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "User location set successfully"}), 201


@api_bp.route("/api/get_user_locations", methods=["GET"])
def get_user_locations():
    conn = get_db_connection(USER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT username, latitude, longitude FROM users")
    users = cursor.fetchall()
    conn.close()

    user_list = [
        {
            "username": row["username"],
            "latitude": row["latitude"],
            "longitude": row["longitude"]
        }
        for row in users
    ]
    return jsonify(user_list)

# VEHICLE ROUTES & ALLOCATION
@api_bp.route("/api/get_vehicles", methods=["GET"])
def get_vehicles():
    conn = get_db_connection(VEHICLE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, latitude, longitude, capacity, vehicle_type FROM vehicles")
    vehicles = cursor.fetchall()
    conn.close()

    vehicle_list = [
        {"id": row["id"], "latitude": row["latitude"], "longitude": row["longitude"], "capacity": row["capacity"], "vehicle_type": row["vehicle_type"]}
        for row in vehicles
    ]
    return jsonify(vehicle_list)


@api_bp.route("/api/add_vehicle", methods=["POST"])
def add_vehicle():
    data = request.json
    lat = data.get("latitude")
    lng = data.get("longitude")
    capacity = data.get("capacity")
    vehicle_type = data.get("vehicle_type", "car")

    if lat is None or lng is None or capacity is None:
        return jsonify({"error": "Latitude, longitude, and capacity are required."}), 400

    conn = get_db_connection(VEHICLE_DB)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO vehicles (latitude, longitude, capacity, vehicle_type)
        VALUES (?, ?, ?, ?)
        """,
        (lat, lng, capacity, vehicle_type)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Vehicle added successfully"}), 201


@api_bp.route("/api/allocate_vehicles", methods=["POST"])
def allocate_vehicles():
    data = request.json
    fire_lat = data.get("latitude")
    fire_lng = data.get("longitude")
    required_capacity = data.get("required_capacity", 10)  # default
    desired_type = data.get("vehicle_type")  # optional

    conn = get_db_connection(VEHICLE_DB)
    cursor = conn.cursor()

    if desired_type:
        cursor.execute(
            """SELECT id, latitude, longitude, capacity, vehicle_type FROM vehicles WHERE vehicle_type = ?""",
            (desired_type,)
        )
    else:
        cursor.execute("SELECT id, latitude, longitude, capacity, vehicle_type FROM vehicles")

    vehicles = cursor.fetchall()
    conn.close()

    # Sort by distance from the fire
    vehicles_sorted = sorted(
        vehicles,
        key=lambda v: haversine_distance(fire_lat, fire_lng, v["latitude"], v["longitude"])
    )

    allocated_vehicles = []
    total_capacity_overall = 0

    for v in vehicles_sorted:
        vid = v["id"]
        vlat = v["latitude"]
        vlng = v["longitude"]
        vcap = v["capacity"]
        vtype = v["vehicle_type"]

        dist_km = haversine_distance(fire_lat, fire_lng, vlat, vlng)
        # If within 50km and we still need more capacity
        if dist_km <= 50 and total_capacity_overall < required_capacity:
            allocated_vehicles.append({
                "id": vid,
                "latitude": vlat,
                "longitude": vlng,
                "capacity": vcap,
                "vehicle_type": vtype
            })
            total_capacity_overall += vcap
            if total_capacity_overall >= required_capacity:
                break

    # Summarize by vehicle type
    type_summary = {}
    for veh in allocated_vehicles:
        vt = veh["vehicle_type"]
        if vt not in type_summary:
            type_summary[vt] = {"count": 0, "total_capacity": 0}
        type_summary[vt]["count"] += 1
        type_summary[vt]["total_capacity"] += veh["capacity"]

    return jsonify({
        "allocated_vehicles": allocated_vehicles,
        "total_capacity_overall": total_capacity_overall,
        "type_summary": type_summary
    }), 200

@api_bp.route("/api/route_plan")
def api_route_plan():
    try:
        lat1, lng1 = float(request.args["lat1"]), float(request.args["lng1"])
        lat2, lng2 = float(request.args["lat2"]), float(request.args["lng2"])
    except (KeyError, ValueError):
        return {"error": "need lat1,lng1,lat2,lng2"}, 400
    s = _nearest_node(lat1, lng1)
    t = _nearest_node(lat2, lng2)

    # Dijkstra
    try:
        path = nx.shortest_path(G_ROUTE, s, t, weight="weight")
    except nx.NetworkXNoPath:
        return {"error": "no path"}, 404

    '''
    coords = []
    for u, v in zip(path[:-1], path[1:]):
        geom = G_ROUTE.edges[u, v]['geometry']
        coords.extend(list(geom.coords))

    unique = [coords[0]] + [c for i, c in enumerate(coords[1:]) if c != coords[i]]
    line = LineString(unique)

    return {"route": line.__geo_interface__}
    '''
    pts = [G_ROUTE.nodes[nid]['pos'] for nid in path]
    lonlat = [(p[1], p[0]) for p in pts]                  #  turn to (lon,lat)
    line = LineString(lonlat)
    dist_m = 0.0
    for u, v in zip(path[:-1], path[1:]):
        dist_m += G_ROUTE.edges[u, v]["weight"]                # weight (m)
    dist_km = round(dist_m / 1000.0, 2)                        # two decimal

    return {
        "route":       line.__geo_interface__,
        "distance_km": dist_km
    }

