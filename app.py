import eventlet
eventlet.monkey_patch()
from sqlalchemy.pool import NullPool

import os
import csv
import io
import math
import time
import requests
from functools import wraps
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file, send_from_directory
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import create_engine, text

# -------------------------------------------------
# APP SETUP
# -------------------------------------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key')

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'vitcadmin2024')

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///signals.db')
if not os.environ.get('DATABASE_URL'):
    print("ℹ️ DATABASE_URL not set; defaulting to sqlite:///signals.db")

if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, poolclass=NullPool)
else:
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"}
    )

# -------------------------------------------------
# BUILDINGS — VIT Chennai Campus
# -------------------------------------------------

VIT_BUILDINGS = [
    {"id": "TT", "name": "Technology Tower", "name_ta": "தொழில்நுட்ப கோபுரம்", "lat": 12.8448, "lng": 80.1558, "radius_m": 90, "floors": 8},
    {"id": "SJT", "name": "SJT Block", "name_ta": "SJT தொகுதி", "lat": 12.8425, "lng": 80.1540, "radius_m": 80, "floors": 6},
    {"id": "SMV", "name": "SMV Block", "name_ta": "SMV தொகுதி", "lat": 12.8440, "lng": 80.1528, "radius_m": 75, "floors": 5},
    {"id": "GDN", "name": "GDN Block", "name_ta": "GDN தொகுதி", "lat": 12.8415, "lng": 80.1570, "radius_m": 70, "floors": 5},
    {"id": "CDMM", "name": "CDMM Building", "name_ta": "CDMM கட்டிடம்", "lat": 12.8432, "lng": 80.1560, "radius_m": 65, "floors": 4},
    {"id": "LIBRARY", "name": "Central Library", "name_ta": "மத்திய நூலகம்", "lat": 12.8435, "lng": 80.1548, "radius_m": 55, "floors": 3},
    {"id": "ANNA", "name": "Anna Auditorium", "name_ta": "அண்ணா அரங்கம்", "lat": 12.8420, "lng": 80.1553, "radius_m": 60, "floors": 2},
    {"id": "HOSTEL", "name": "Hostel Zone", "name_ta": "விடுதி மண்டலம்", "lat": 12.8400, "lng": 80.1545, "radius_m": 110, "floors": 7},
]

# -------------------------------------------------
# DB INIT & MIGRATIONS
# -------------------------------------------------

def ensure_tables_exist():
    CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS signal_data (
        id SERIAL PRIMARY KEY,
        lat DOUBLE PRECISION NOT NULL,
        lng DOUBLE PRECISION NOT NULL,
        carrier TEXT NOT NULL,
        network_type TEXT NOT NULL,
        signal_strength REAL,
        download_speed REAL,
        contributor_id TEXT DEFAULT 'anon',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
    if "sqlite" in DATABASE_URL:
        CREATE_SQL = CREATE_SQL.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT").replace(
            "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP")

    for attempt in range(1, 4):
        try:
            with engine.begin() as conn:
                conn.execute(text(CREATE_SQL))
                try:
                    conn.execute(text("ALTER TABLE signal_data ADD COLUMN contributor_id TEXT DEFAULT 'anon'"))
                except Exception:
                    pass 
            print("✅ DB tables verified")
            return
        except Exception as e:
            print(f"⚠️ DB init attempt {attempt} failed: {e}")
            if attempt < 3: time.sleep(2 * attempt)
    raise RuntimeError("Could not initialise database")

ensure_tables_exist()

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
limiter = Limiter(get_remote_address, app=app, default_limits=["50000 per day", "5000 per hour"])

# -------------------------------------------------
# GEOFENCING & HELPERS
# -------------------------------------------------

VIT_POLYGON = [(12.8455, 80.1532), (12.8447, 80.1587), (12.8435, 80.1589), (12.8395, 80.1560), (12.8387, 80.1545), (12.8419, 80.1515), (12.8425, 80.1510), (12.8456, 80.1518)]
_VIT_LAT_MIN = min(p[0] for p in VIT_POLYGON); _VIT_LAT_MAX = max(p[0] for p in VIT_POLYGON)
_VIT_LNG_MIN = min(p[1] for p in VIT_POLYGON); _VIT_LNG_MAX = max(p[1] for p in VIT_POLYGON)
_VIT_CENTER_LAT = (_VIT_LAT_MIN + _VIT_LAT_MAX) / 2; _VIT_CENTER_LNG = (_VIT_LNG_MIN + _VIT_LNG_MAX) / 2

def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1); dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _haversine_m(lat1, lng1, lat2, lng2): return _haversine_km(lat1, lng1, lat2, lng2) * 1000

def _ray_cast_inside(lat, lng, poly):
    n = len(poly); inside = False; p1x, p1y = poly[0]
    for i in range(1, n + 1):
        p2x, p2y = poly[i % n]
        if lng > min(p1y, p2y) and lng <= max(p1y, p2y) and lat <= max(p1x, p2x):
            if p1y != p2y: x_ints = (lng - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            if p1x == p2x or lat <= x_ints: inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def is_within_bounds(lat, lng):
    if not (_VIT_LAT_MIN <= lat <= _VIT_LAT_MAX and _VIT_LNG_MIN <= lng <= _VIT_LNG_MAX): return False, "Outside bounding box"
    if _haversine_km(lat, lng, _VIT_CENTER_LAT, _VIT_CENTER_LNG) > 1.5: return False, "Too far from centre"
    if not _ray_cast_inside(lat, lng, VIT_POLYGON): return False, "Outside campus polygon"
    return True, "OK"

# -------------------------------------------------
# VALIDATION & AUTH
# -------------------------------------------------

VALID_CARRIERS = {"Airtel", "Jio", "VI", "BSNL", "Other", "Unknown"}
VALID_NETWORKS = {"2G", "3G", "4G", "5G", "Unknown"}

def _clean_contributor_id(raw):
    if not raw or not isinstance(raw, str): return "anon"
    cleaned = raw.strip().lower()
    return cleaned if (len(cleaned) <= 40 and all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in cleaned)) else "anon"

def _clean_signal(value):
    try:
        v = float(value)
        return v if -140 <= v <= -20 else None
    except: return None

def _clean_speed(value):
    try:
        v = float(value)
        return round(v, 3) if 0 < v <= 10000 else None
    except: return None

def _signal_quality(avg_dbm):
    if avg_dbm is None: return "No Data", "none"
    if avg_dbm >= -70: return "Excellent", "excellent"
    if avg_dbm >= -85: return "Good", "good"
    if avg_dbm >= -100: return "Fair", "fair"
    return "Poor", "poor"

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'): return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# -------------------------------------------------
# ROUTES
# -------------------------------------------------

@app.route("/")
def index(): return render_template("index.html")

@app.route("/upload")
def upload_page(): return render_template("upload.html")

@app.route("/leaderboard")
def leaderboard_page(): return render_template("leaderboard.html")

@app.route("/buildings")
def buildings_page(): return render_template("buildings.html")

@app.route("/sw.js")
def serve_sw(): return send_from_directory("static", "sw.js", mimetype="application/javascript")

@app.route("/manifest.json")
def serve_manifest(): return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = False
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = True
    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin_dashboard(): return render_template("admin.html")

@app.route("/admin/export")
@admin_required
def admin_export():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM signal_data ORDER BY created_at DESC"))
        data = [dict(r._mapping) for r in rows]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "lat", "lng", "carrier", "network_type", "signal_strength", "download_speed", "contributor_id", "created_at"])
    writer.writeheader()
    for row in data:
        if hasattr(row.get("created_at"), "isoformat"): row["created_at"] = row["created_at"].isoformat()
        writer.writerow(row)
    return send_file(io.BytesIO(output.getvalue().encode("utf-8")), mimetype="text/csv", as_attachment=True, download_name="vit_signal_data.csv")

@app.route("/api/submit", methods=["POST"])
@limiter.limit("10 per second")
def submit_data():
    data = request.get_json(silent=True)
    if not data: return jsonify({"error": "Invalid JSON"}), 400
    try:
        lat, lng = float(data["lat"]), float(data["lng"])
        valid, reason = is_within_bounds(lat, lng)
        if not valid: return jsonify({"error": "OUT_OF_CAMPUS", "message": reason}), 403
        
        payload = {
            "lat": lat, "lng": lng,
            "carrier": data.get("carrier") if data.get("carrier") in VALID_CARRIERS else "Other",
            "network_type": data.get("network_type", "Unknown").upper() if data.get("network_type") in VALID_NETWORKS else "Unknown",
            "signal_strength": _clean_signal(data.get("signal_strength")),
            "download_speed": _clean_speed(data.get("download_speed")),
            "contributor_id": _clean_contributor_id(data.get("contributor_id"))
        }
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO signal_data (lat, lng, carrier, network_type, signal_strength, download_speed, contributor_id) VALUES (:lat, :lng, :carrier, :network_type, :signal_strength, :download_speed, :contributor_id)"), payload)
        
        socketio.emit("new_data_point", {k: v for k, v in payload.items() if k != "contributor_id"})
        return jsonify({"success": True}), 201
    except Exception as e: return jsonify({"error": str(e)}), 400

@app.route("/api/samples")
def get_samples():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT lat, lng, signal_strength, download_speed, carrier, network_type, created_at FROM signal_data ORDER BY created_at DESC LIMIT 5000"))
        results = [dict(r._mapping) for r in rows]
    for r in results:
        if hasattr(r.get("created_at"), "isoformat"): r["created_at"] = r["created_at"].isoformat()
    return jsonify(results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)