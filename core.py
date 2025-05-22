# core.py – shared utilities: DB helpers, GeoPandas caches, routing graph
import math
import os
import sqlite3
import geopandas as gpd
import numpy as np
import networkx as nx

from pathlib import Path
from scipy.spatial import cKDTree
from fire import get_fire_layers_geojson
from functools import lru_cache

# File paths / constants
MESH_FILE = Path("outputs/adaptive_mesh.geojson")
EDGES_FILE = Path("outputs_backup/mesh_edges.geojson")
NODES_FILE = Path("outputs_backup/mesh_nodes.geojson")

# Database filenames
P_DB = "data/p.db"  # For authentication
WILDFIRE_DB = "data/wildfires.db"
ROAD_CLOSURE_DB = "data/road_closures.db"
USER_DB = "data/user.db"
VEHICLE_DB = "data/vehicles.db"

# Change this for security
GOVERNMENT_USERS = {"admin": "password123"}

# Helper function for database connection
def get_db_connection(db_name):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database tables if they do not exist
def init_db():
    db_table_queries = [
        (
            P_DB,
            """CREATE TABLE IF NOT EXISTS users (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               username TEXT NOT NULL UNIQUE,
               password TEXT NOT NULL
            )"""
        ),
        (
            WILDFIRE_DB,
            """CREATE TABLE IF NOT EXISTS wildfires (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               latitude REAL NOT NULL,
               longitude REAL NOT NULL,
               description TEXT,
               reason TEXT
            )"""
        ),
        (
            ROAD_CLOSURE_DB,
            """CREATE TABLE IF NOT EXISTS road_closures (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               latitude REAL NOT NULL,
               longitude REAL NOT NULL,
               reason TEXT
            )"""
        ),
        (
            USER_DB,
            """CREATE TABLE IF NOT EXISTS users (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               username TEXT NOT NULL UNIQUE,
               latitude REAL,
               longitude REAL
            )"""
        ),
        (
            VEHICLE_DB,
            """CREATE TABLE IF NOT EXISTS vehicles (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               latitude REAL NOT NULL,
               longitude REAL NOT NULL,
               capacity INTEGER NOT NULL,
               vehicle_type TEXT NOT NULL
            )"""
        )
    ]

    for db_name, create_query in db_table_queries:
        if not os.path.exists(db_name):
            conn = get_db_connection(db_name)
            cursor = conn.cursor()
            cursor.execute(create_query)
            conn.commit()
            conn.close()

# Fire overlay cache
@lru_cache(maxsize=1)
def _fire_layers_cached():
    return get_fire_layers_geojson()

# Simple geodesic distance
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# GeoPandas cached layers
@lru_cache(maxsize=1)
def _mesh_gdf():
    return gpd.read_file(MESH_FILE).to_crs(epsg=4326)   # Ensure WGS84

@lru_cache(maxsize=1)
def _graph_edges():
    return gpd.read_file(EDGES_FILE).to_crs(epsg=4326)

@lru_cache(maxsize=1)
def _graph_nodes():
    return gpd.read_file(NODES_FILE).to_crs(epsg=4326)

# Routing graph (NetworkX + KD‑Tree)
G_ROUTE = nx.Graph()          # global graph instance
KD_IDX  = None                # KD‑Tree for nearest‑node lookup

# Build graph the first time any route query is made
def _init_route_graph():
    global G_ROUTE, KD_IDX, _nodes_latlng

    edges = _graph_edges().to_crs(epsg=4326)   # lon/lat

    G_ROUTE.clear()
    nodes_seen = {}          # (lon,lat) to id
    
    def _key(coord, ndigits=6):
    # round lon/lat to 6 digits (≈11 cm) so duplicates collapse
        return (round(coord[0], ndigits), round(coord[1], ndigits))

    def _get_node_id(coord):
        k = _key(coord)
        if k in nodes_seen:
            return nodes_seen[k]
        nid = len(nodes_seen)
        nodes_seen[k] = nid
        G_ROUTE.add_node(nid, pos=(coord[1], coord[0]))
        return nid

    # add edges
    for _, row in edges.iterrows():
        geom = row.geometry
        lon1, lat1 = geom.coords[0]
        lon2, lat2 = geom.coords[-1]

        u = _get_node_id((lon1, lat1))
        v = _get_node_id((lon2, lat2))

        # weight in metres: prefer existing column else fallback to geom length
        dist = row.get("length", geom.length * 111_139)
        G_ROUTE.add_edge(u, v, weight=float(dist), geometry=geom)

    # build KD‑Tree for nearest‑node lookup
    _nodes_latlng = np.array([[d[1], d[0]] for d in nodes_seen])  # lat,lon
    KD_IDX = cKDTree(_nodes_latlng)

# nearest‑node lookup
def _nearest_node(lat, lng):
    if KD_IDX is None:
        _init_route_graph()
    dist, idx = KD_IDX.query([lat, lng])
    nid = list(G_ROUTE.nodes())[idx]
    return nid

