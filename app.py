import eventlet
eventlet.monkey_patch()
from sqlalchemy.pool import NullPool

import os
import math
import requests
import time
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import create_engine, text

# -------------------------------------------------
# APP SETUP
# -------------------------------------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key')

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
# DB INIT
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
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
    if "sqlite" in DATABASE_URL:
        CREATE_SQL = CREATE_SQL.replace(
            "SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT"
        ).replace(
            "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "DATETIME DEFAULT CURRENT_TIMESTAMP"
        )

    for attempt in range(1, 4):
        try:
            with engine.begin() as conn:
                conn.execute(text(CREATE_SQL))
            print("✅ DB tables verified")
            return
        except Exception as e:
            print(f"⚠️  DB init attempt {attempt} failed: {e}")
            if attempt < 3:
                time.sleep(2 * attempt)
    raise RuntimeError("Could not initialise database after 3 attempts")

ensure_tables_exist()

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["50000 per day", "5000 per hour"]
)

# -------------------------------------------------
# GEOFENCING — VIT Chennai Campus
# -------------------------------------------------

# Precise campus boundary polygon (lat, lng)
VIT_POLYGON = [
    (12.8455, 80.1532),
    (12.8447, 80.1587),
    (12.8435, 80.1589),
    (12.8395, 80.1560),
    (12.8387, 80.1545),
    (12.8419, 80.1515),
    (12.8425, 80.1510),
    (12.8456, 80.1518),
]

# Pre-computed bounding box for fast rejection
_VIT_LAT_MIN = min(p[0] for p in VIT_POLYGON)
_VIT_LAT_MAX = max(p[0] for p in VIT_POLYGON)
_VIT_LNG_MIN = min(p[1] for p in VIT_POLYGON)
_VIT_LNG_MAX = max(p[1] for p in VIT_POLYGON)

# Campus centroid (used for distance sanity check)
_VIT_CENTER_LAT = (_VIT_LAT_MIN + _VIT_LAT_MAX) / 2
_VIT_CENTER_LNG = (_VIT_LNG_MIN + _VIT_LNG_MAX) / 2
_VIT_MAX_RADIUS_KM = 1.5  # generous outer bound

def _haversine_km(lat1, lng1, lat2, lng2):
    """Returns distance in kilometres between two coordinates."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _ray_cast_inside(lat, lng, poly):
    """Standard ray-casting polygon membership test."""
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in range(1, n + 1):
        p2x, p2y = poly[i % n]
        if lng > min(p1y, p2y):
            if lng <= max(p1y, p2y):
                if lat <= max(p1x, p2x):
                    if p1y != p2y:
                        x_ints = (lng - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or lat <= x_ints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def is_within_bounds(lat, lng):
    """
    Three-stage geofence check (fast → medium → precise):
      1. Bounding-box rejection   — O(1)
      2. Radius sanity check      — O(1)
      3. Ray-casting polygon test — O(n)
    Returns (bool, str) — (is_valid, reason_if_invalid)
    """
    # Stage 1: bounding box
    if not (_VIT_LAT_MIN <= lat <= _VIT_LAT_MAX and
            _VIT_LNG_MIN <= lng <= _VIT_LNG_MAX):
        return False, "Outside bounding box"

    # Stage 2: crude radius (catches outliers that pass bbox)
    dist_km = _haversine_km(lat, lng, _VIT_CENTER_LAT, _VIT_CENTER_LNG)
    if dist_km > _VIT_MAX_RADIUS_KM:
        return False, f"Too far from campus centre ({dist_km:.2f} km)"

    # Stage 3: precise polygon
    if not _ray_cast_inside(lat, lng, VIT_POLYGON):
        return False, "Outside campus polygon"

    return True, "OK"


# -------------------------------------------------
# VALIDATION HELPERS
# -------------------------------------------------

VALID_CARRIERS = {"Airtel", "Jio", "VI", "BSNL", "Other", "Unknown"}
VALID_NETWORKS = {"2G", "3G", "4G", "5G", "Unknown"}


def _clean_signal(value):
    """Validate and clamp signal strength (dBm)."""
    if value is None:
        return None
    try:
        v = float(value)
        if not (-140 <= v <= -20):
            return None  # plausible dBm range
        return v
    except (TypeError, ValueError):
        return None


def _clean_speed(value):
    """Validate download speed (Mbps)."""
    if value is None:
        return None
    try:
        v = float(value)
        if not (0 < v <= 10_000):
            return None  # max ~10 Gbps, discard negatives/zeros
        return round(v, 3)
    except (TypeError, ValueError):
        return None


# -------------------------------------------------
# CARRIER DETECTION CACHE
# -------------------------------------------------

_carrier_cache: dict[str, tuple[str, float]] = {}
_CARRIER_CACHE_TTL = 3600  # 1 hour


def _detect_carrier_from_ip(ip: str) -> str:
    now = time.time()
    if ip in _carrier_cache:
        carrier, ts = _carrier_cache[ip]
        if now - ts < _CARRIER_CACHE_TTL:
            return carrier

    try:
        r = requests.get(f"https://ipinfo.io/{ip}/org", timeout=8)
        if r.status_code == 200:
            org = r.text.lower()
            if "jio" in org:
                carrier = "Jio"
            elif "airtel" in org:
                carrier = "Airtel"
            elif any(k in org for k in ("vodafone", "idea", " vi ")):
                carrier = "VI"
            elif "bsnl" in org:
                carrier = "BSNL"
            else:
                carrier = "Other"
            _carrier_cache[ip] = (carrier, now)
            return carrier
    except requests.exceptions.RequestException as e:
        print(f"Carrier detection error for {ip}: {e}")

    return "Other"


# -------------------------------------------------
# FRONTEND ROUTES
# -------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/upload", methods=["GET"])
def upload_page():
    return render_template("upload.html")


@app.route("/leaderboard", methods=["GET"])
def leaderboard_page():
    return render_template("leaderboard.html")


@app.route("/buildings", methods=["GET"])
def buildings_page():
    return render_template("buildings.html")


@app.route("/admin", methods=["GET"])
def admin_page():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login_page"))
    return render_template("admin.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login_page():
    if request.method == "GET":
        return render_template("admin_login.html", error=False)

    password = (request.form.get("password") or "").strip()
    expected_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    if password == expected_password:
        session["admin_logged_in"] = True
        return redirect(url_for("admin_page"))

    return render_template("admin_login.html", error=True), 401


@app.route("/admin/logout", methods=["GET"])
def admin_logout_page():
    session.pop("admin_logged_in", None)
    return redirect(url_for("index"))

from flask import send_from_directory

@app.route("/sw.js")
def serve_sw():
    # Serve the service worker from the root scope
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

@app.route("/manifest.json")
def serve_manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")

# -------------------------------------------------
# API ENDPOINTS
# -------------------------------------------------

@app.route("/api/samples")
def get_samples():
    carrier = request.args.get("carrier", "").strip()
    network = request.args.get("network_type", "").strip()
    limit = min(int(request.args.get("limit", 5000)), 10_000)

    sql = """
        SELECT lat, lng, signal_strength, download_speed,
               carrier, network_type, created_at
        FROM signal_data
    """
    filters, params = [], {}

    if carrier and carrier in VALID_CARRIERS:
        filters.append("carrier = :carrier")
        params["carrier"] = carrier
    if network and network in VALID_NETWORKS:
        filters.append("network_type = :network")
        params["network"] = network

    if filters:
        sql += " WHERE " + " AND ".join(filters)

    sql += " ORDER BY created_at DESC LIMIT :limit"
    params["limit"] = limit

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params)
        results = [dict(r._mapping) for r in rows]

    # Serialise datetime fields
    for r in results:
        if "created_at" in r and hasattr(r["created_at"], "isoformat"):
            r["created_at"] = r["created_at"].isoformat()

    return jsonify(results)


@app.route("/api/stats")
def get_stats():
    """Summary statistics for dashboard widgets."""
    sql = """
        SELECT
            COUNT(*)                                      AS total,
            AVG(signal_strength)                          AS avg_signal,
            AVG(download_speed)                           AS avg_speed,
            COUNT(DISTINCT carrier)                       AS unique_carriers,
            SUM(CASE WHEN network_type = '5G' THEN 1 ELSE 0 END) AS five_g_count
        FROM signal_data
    """
    with engine.connect() as conn:
        row = conn.execute(text(sql)).fetchone()

    return jsonify({
        "total_samples":    row[0] or 0,
        "avg_signal_dbm":   round(row[1], 1) if row[1] else None,
        "avg_speed_mbps":   round(row[2], 2) if row[2] else None,
        "unique_carriers":  row[3] or 0,
        "five_g_count":     row[4] or 0,
    })


@app.route("/api/submit", methods=["POST"])
@limiter.limit("10 per second")
def submit_data():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    # --- Coordinate validation ---
    try:
        lat = float(data["lat"])
        lng = float(data["lng"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Missing or invalid lat/lng"}), 400

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({"error": "Coordinates out of valid range"}), 400

    # --- Geofence ---
    valid, reason = is_within_bounds(lat, lng)
    if not valid:
        return jsonify({
            "error": "OUT_OF_CAMPUS",
            "message": f"Location rejected: {reason}"
        }), 403

    # --- Field sanitisation ---
    raw_carrier = str(data.get("carrier", "Unknown")).strip()
    carrier = raw_carrier if raw_carrier in VALID_CARRIERS else "Other"

    raw_network = str(data.get("network_type", "Unknown")).strip().upper()
    network_type = raw_network if raw_network in VALID_NETWORKS else "Unknown"

    signal_strength = _clean_signal(data.get("signal_strength"))
    download_speed  = _clean_speed(data.get("download_speed"))

    payload = {
        "lat":             lat,
        "lng":             lng,
        "carrier":         carrier,
        "network_type":    network_type,
        "signal_strength": signal_strength,
        "download_speed":  download_speed,
    }

    sql = """
        INSERT INTO signal_data
            (lat, lng, carrier, network_type, signal_strength, download_speed)
        VALUES
            (:lat, :lng, :carrier, :network_type, :signal_strength, :download_speed)
    """
    with engine.begin() as conn:
        conn.execute(text(sql), payload)

    socketio.emit("new_data_point", payload)
    return jsonify({"success": True}), 201


@app.route("/api/speed-test-payload")
def speed_test_payload():
    """512 KB payload for client-side throughput measurement."""
    return "0" * (512 * 1024), 200, {
        "Content-Type": "text/plain",
        "Cache-Control": "no-store",
    }


@app.route("/api/get-carrier")
def get_carrier():
    raw_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ip = raw_ip.split(",")[0].strip()

    private_prefixes = ("127.", "192.168.", "10.", "172.", "::1", "localhost")
    if any(ip.startswith(p) for p in private_prefixes):
        return jsonify({"carrier": "Unknown", "reason": "Local/private IP"})

    carrier = _detect_carrier_from_ip(ip)
    return jsonify({"carrier": carrier})


# -------------------------------------------------
# SOCKET EVENTS
# -------------------------------------------------

@socketio.on("connect")
def on_connect():
    print(f"[WS] Client connected: {request.sid}")


@socketio.on("disconnect")
def on_disconnect():
    print(f"[WS] Client disconnected: {request.sid}")


# -------------------------------------------------
# ERROR HANDLERS
# -------------------------------------------------

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "Rate limit exceeded", "message": str(e)}), 429


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# -------------------------------------------------
# RUN
# -------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
        allow_unsafe_werkzeug=True,
    )
