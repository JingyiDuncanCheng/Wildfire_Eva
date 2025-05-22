# service.py – wildfire helpers
# Contains helper functions that the Flask API calls.
from core import get_db_connection, haversine_distance, USER_DB, VEHICLE_DB

# User notification
# Return usernames within radius_km km of the fire location.
def notify_users_nearby(fire_lat, fire_lng, radius_km=30):
    conn = get_db_connection(USER_DB)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT username, latitude, longitude FROM users WHERE latitude IS NOT NULL AND longitude IS NOT NULL"""
    )
    users = cursor.fetchall()
    conn.close()

    nearby_users = []
    for user in users:
        distance = haversine_distance(fire_lat, fire_lng, user["latitude"], user["longitude"])
        if distance <= radius_km:
            nearby_users.append(user["username"])
    return nearby_users

# Vehicle allocation
# Pick nearest vehicles until requested capacity is reached.
def allocate_vehicles_for_fire(fire_lat, fire_lng, capacity=10):
    conn = get_db_connection(VEHICLE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, latitude, longitude, capacity, vehicle_type FROM vehicles")
    vehicles = cursor.fetchall()
    conn.close()

    vehicles_sorted = sorted(
        vehicles,
        key=lambda v: haversine_distance(fire_lat, fire_lng, v["latitude"], v["longitude"])
    )

    allocated_vehicles = []
    total_capacity_overall = 0

    for v in vehicles_sorted:
        dist_km = haversine_distance(fire_lat, fire_lng, v["latitude"], v["longitude"])
        if dist_km <= 50 and total_capacity_overall < capacity:
            allocated_vehicles.append({
                "id": v["id"],
                "latitude": v["latitude"],
                "longitude": v["longitude"],
                "capacity": v["capacity"],
                "vehicle_type": v["vehicle_type"]
            })
            total_capacity_overall += v["capacity"]
            if total_capacity_overall >= capacity:
                break

    # Summarize by vehicle type
    type_summary = {}
    for veh in allocated_vehicles:
        vt = veh["vehicle_type"]
        if vt not in type_summary:
            type_summary[vt] = {"count": 0, "total_capacity": 0}
        type_summary[vt]["count"] += 1
        type_summary[vt]["total_capacity"] += veh["capacity"]

    return {
        "allocated_vehicles": allocated_vehicles,
        "total_capacity_overall": total_capacity_overall,
        "type_summary": type_summary
    }