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
<<<<<<< ours
from flask import Flask, request, jsonify, render_template, session, redirect, send_file
=======
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
>>>>>>> theirs
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import create_engine, text

# -------------------------------------------------
# APP SETUP
# -------------------------------------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key')

<<<<<<< ours
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'vitcadmin2024')

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL not set.\n"
        "  Local:  $env:DATABASE_URL = 'sqlite:///signals.db'\n"
        "  Linux:  export DATABASE_URL='sqlite:///signals.db'"
    )
=======
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///signals.db')
if not os.environ.get('DATABASE_URL'):
    print("ℹ️ DATABASE_URL not set; defaulting to sqlite:///signals.db")
>>>>>>> theirs

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
# NOTE: Coordinates are approximate. Update with precise survey data.
# -------------------------------------------------

VIT_BUILDINGS = [
    {
        "id": "TT",
        "name": "Technology Tower",
        "name_ta": "தொழில்நுட்ப கோபுரம்",
        "lat": 12.8448, "lng": 80.1558, "radius_m": 90,
        "floors": 8,
    },
    {
        "id": "SJT",
        "name": "SJT Block",
        "name_ta": "SJT தொகுதி",
        "lat": 12.8425, "lng": 80.1540, "radius_m": 80,
        "floors": 6,
    },
    {
        "id": "SMV",
        "name": "SMV Block",
        "name_ta": "SMV தொகுதி",
        "lat": 12.8440, "lng": 80.1528, "radius_m": 75,
        "floors": 5,
    },
    {
        "id": "GDN",
        "name": "GDN Block",
        "name_ta": "GDN தொகுதி",
        "lat": 12.8415, "lng": 80.1570, "radius_m": 70,
        "floors": 5,
    },
    {
        "id": "CDMM",
        "name": "CDMM Building",
        "name_ta": "CDMM கட்டிடம்",
        "lat": 12.8432, "lng": 80.1560, "radius_m": 65,
        "floors": 4,
    },
    {
        "id": "LIBRARY",
        "name": "Central Library",
        "name_ta": "மத்திய நூலகம்",
        "lat": 12.8435, "lng": 80.1548, "radius_m": 55,
        "floors": 3,
    },
    {
        "id": "ANNA",
        "name": "Anna Auditorium",
        "name_ta": "அண்ணா அரங்கம்",
        "lat": 12.8420, "lng": 80.1553, "radius_m": 60,
        "floors": 2,
    },
    {
        "id": "HOSTEL",
        "name": "Hostel Zone",
        "name_ta": "விடுதி மண்டலம்",
        "lat": 12.8400, "lng": 80.1545, "radius_m": 110,
        "floors": 7,
    },
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
                # Migration: add contributor_id if it doesn't exist
                try:
                    conn.execute(text(
                        "ALTER TABLE signal_data ADD COLUMN contributor_id TEXT DEFAULT 'anon'"
                    ))
                except Exception:
                    pass  # column already exists — safe to ignore
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

_VIT_LAT_MIN = min(p[0] for p in VIT_POLYGON)
_VIT_LAT_MAX = max(p[0] for p in VIT_POLYGON)
_VIT_LNG_MIN = min(p[1] for p in VIT_POLYGON)
_VIT_LNG_MAX = max(p[1] for p in VIT_POLYGON)
_VIT_CENTER_LAT = (_VIT_LAT_MIN + _VIT_LAT_MAX) / 2
_VIT_CENTER_LNG = (_VIT_LNG_MIN + _VIT_LNG_MAX) / 2
_VIT_MAX_RADIUS_KM = 1.5


def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _haversine_m(lat1, lng1, lat2, lng2):
    return _haversine_km(lat1, lng1, lat2, lng2) * 1000


def _ray_cast_inside(lat, lng, poly):
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
    if not (_VIT_LAT_MIN <= lat <= _VIT_LAT_MAX and
            _VIT_LNG_MIN <= lng <= _VIT_LNG_MAX):
        return False, "Outside bounding box"
    dist_km = _haversine_km(lat, lng, _VIT_CENTER_LAT, _VIT_CENTER_LNG)
    if dist_km > _VIT_MAX_RADIUS_KM:
        return False, f"Too far from campus centre ({dist_km:.2f} km)"
    if not _ray_cast_inside(lat, lng, VIT_POLYGON):
        return False, "Outside campus polygon"
    return True, "OK"

# -------------------------------------------------
# CAMPUS COVERAGE GRID
# -------------------------------------------------

_GRID_CELL_M = 30  # 30m × 30m cells

def _compute_campus_coverage_pct(recent_points):
    """
    Compute what % of campus grid cells (30m × 30m) have at least one reading.
    recent_points: list of (lat, lng) tuples.
    """
    # Degree deltas for 30 m
    lat_delta = _GRID_CELL_M / 111_000
    lng_delta = _GRID_CELL_M / (111_000 * math.cos(math.radians(_VIT_CENTER_LAT)))

    # Generate all campus grid cells
    total_cells = set()
    covered_cells = set()

    lat = _VIT_LAT_MIN
    while lat <= _VIT_LAT_MAX:
        lng = _VIT_LNG_MIN
        while lng <= _VIT_LNG_MAX:
            cell_lat = lat + lat_delta / 2
            cell_lng = lng + lng_delta / 2
            if _ray_cast_inside(cell_lat, cell_lng, VIT_POLYGON):
                cell_key = (round(lat / lat_delta), round(lng / lng_delta))
                total_cells.add(cell_key)
            lng += lng_delta
        lat += lat_delta

    if not total_cells:
        return 0.0

    for (pt_lat, pt_lng) in recent_points:
        cell_key = (
            round(pt_lat / lat_delta),
            round(pt_lng / lng_delta)
        )
        if cell_key in total_cells:
            covered_cells.add(cell_key)

    return round(len(covered_cells) / len(total_cells) * 100, 1)

# -------------------------------------------------
# VALIDATION HELPERS
# -------------------------------------------------

VALID_CARRIERS = {"Airtel", "Jio", "VI", "BSNL", "Other", "Unknown"}
VALID_NETWORKS = {"2G", "3G", "4G", "5G", "Unknown"}
_UUID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")


def _clean_contributor_id(raw):
    if not raw or not isinstance(raw, str):
        return "anon"
    cleaned = raw.strip().lower()
    if len(cleaned) > 40 or not all(c in _UUID_CHARS for c in cleaned):
        return "anon"
    return cleaned


def _clean_signal(value):
    if value is None:
        return None
    try:
        v = float(value)
        if not (-140 <= v <= -20):
            return None
        return v
    except (TypeError, ValueError):
        return None


def _clean_speed(value):
    if value is None:
        return None
    try:
        v = float(value)
        if not (0 < v <= 10_000):
            return None
        return round(v, 3)
    except (TypeError, ValueError):
        return None


def _signal_quality(avg_dbm):
    """Return (label, color_class) for a signal dBm value."""
    if avg_dbm is None:
        return "No Data", "none"
    if avg_dbm >= -70:
        return "Excellent", "excellent"
    if avg_dbm >= -85:
        return "Good", "good"
    if avg_dbm >= -100:
        return "Fair", "fair"
    return "Poor", "poor"

# -------------------------------------------------
# CARRIER DETECTION CACHE
# -------------------------------------------------

_carrier_cache: dict[str, tuple[str, float]] = {}
_CARRIER_CACHE_TTL = 3600


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
# ADMIN AUTH
# -------------------------------------------------

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated

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


<<<<<<< ours
=======
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

>>>>>>> theirs
from flask import send_from_directory

@app.route("/sw.js")
def serve_sw():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

@app.route("/manifest.json")
def serve_manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")

# -------------------------------------------------
# ADMIN ROUTES
# -------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = False
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect("/admin")
        error = True
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect("/admin/login")


@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html")


@app.route("/admin/delete/<int:record_id>", methods=["POST"])
@admin_required
def admin_delete(record_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM signal_data WHERE id = :id"), {"id": record_id})
    return jsonify({"success": True})


@app.route("/admin/delete-all", methods=["POST"])
@admin_required
def admin_delete_all():
    """Wipe all rows (admin only). Requires confirmation token in body."""
    data = request.get_json(silent=True) or {}
    if data.get("confirm") != "DELETE_ALL":
        return jsonify({"error": "Confirmation required"}), 400
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM signal_data"))
    return jsonify({"success": True})


@app.route("/admin/export")
@admin_required
def admin_export():
    """Export all data as CSV."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, lat, lng, carrier, network_type, signal_strength, "
            "download_speed, contributor_id, created_at FROM signal_data ORDER BY created_at DESC"
        ))
        data = [dict(r._mapping) for r in rows]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "id", "lat", "lng", "carrier", "network_type",
        "signal_strength", "download_speed", "contributor_id", "created_at"
    ])
    writer.writeheader()
    for row in data:
        if hasattr(row.get("created_at"), "isoformat"):
            row["created_at"] = row["created_at"].isoformat()
        writer.writerow(row)

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="vit_signal_data.csv"
    )


@app.route("/api/admin/recent")
@admin_required
def admin_recent():
    limit = min(int(request.args.get("limit", 100)), 500)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, lat, lng, carrier, network_type, signal_strength, "
            "download_speed, contributor_id, created_at "
            "FROM signal_data ORDER BY created_at DESC LIMIT :limit"
        ), {"limit": limit})
        results = [dict(r._mapping) for r in rows]
    for r in results:
        if hasattr(r.get("created_at"), "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
    return jsonify(results)

# -------------------------------------------------
# API ENDPOINTS
# -------------------------------------------------

@app.route("/api/samples")
def get_samples():
    carrier = request.args.get("carrier", "").strip()
    network = request.args.get("network_type", "").strip()
    limit = min(int(request.args.get("limit", 5000)), 10_000)

    sql = (
        "SELECT lat, lng, signal_strength, download_speed, "
        "carrier, network_type, created_at FROM signal_data"
    )
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

    for r in results:
        if "created_at" in r and hasattr(r["created_at"], "isoformat"):
            r["created_at"] = r["created_at"].isoformat()

    return jsonify(results)


@app.route("/api/stats")
def get_stats():
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

    try:
        lat = float(data["lat"])
        lng = float(data["lng"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Missing or invalid lat/lng"}), 400

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({"error": "Coordinates out of valid range"}), 400

    valid, reason = is_within_bounds(lat, lng)
    if not valid:
        return jsonify({
            "error": "OUT_OF_CAMPUS",
            "message": f"Location rejected: {reason}"
        }), 403

    raw_carrier = str(data.get("carrier", "Unknown")).strip()
    carrier = raw_carrier if raw_carrier in VALID_CARRIERS else "Other"

    raw_network = str(data.get("network_type", "Unknown")).strip().upper()
    network_type = raw_network if raw_network in VALID_NETWORKS else "Unknown"

    signal_strength = _clean_signal(data.get("signal_strength"))
    download_speed  = _clean_speed(data.get("download_speed"))
    contributor_id  = _clean_contributor_id(data.get("contributor_id"))

    payload = {
        "lat":             lat,
        "lng":             lng,
        "carrier":         carrier,
        "network_type":    network_type,
        "signal_strength": signal_strength,
        "download_speed":  download_speed,
        "contributor_id":  contributor_id,
    }

    sql = """
        INSERT INTO signal_data
            (lat, lng, carrier, network_type, signal_strength, download_speed, contributor_id)
        VALUES
            (:lat, :lng, :carrier, :network_type, :signal_strength, :download_speed, :contributor_id)
    """
    with engine.begin() as conn:
        conn.execute(text(sql), payload)

    socketio.emit("new_data_point", {k: v for k, v in payload.items() if k != "contributor_id"})
    return jsonify({"success": True}), 201


@app.route("/api/leaderboard")
def get_leaderboard():
    """Top contributors by submission count (privacy: first 8 chars of ID shown)."""
    limit = min(int(request.args.get("limit", 20)), 50)
    sql = """
        SELECT
            contributor_id,
            COUNT(*)                 AS submissions,
            AVG(signal_strength)     AS avg_signal,
            AVG(download_speed)      AS avg_speed,
            MAX(created_at)          AS last_active,
            COUNT(DISTINCT carrier)  AS carriers_used
        FROM signal_data
        WHERE contributor_id != 'anon' AND contributor_id IS NOT NULL
        GROUP BY contributor_id
        ORDER BY submissions DESC
        LIMIT :limit
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"limit": limit})
        results = [dict(r._mapping) for r in rows]

    output = []
    for i, r in enumerate(results):
        last_active = r.get("last_active")
        if hasattr(last_active, "isoformat"):
            last_active = last_active.isoformat()
        elif isinstance(last_active, str):
            pass
        else:
            last_active = None

        cid = r["contributor_id"] or "anon"
        # Anonymise: show only first 8 chars
        display_id = f"VIT-{cid[:8].upper()}"

        output.append({
            "rank":         i + 1,
            "display_id":   display_id,
            "submissions":  r["submissions"],
            "avg_signal":   round(r["avg_signal"], 1) if r["avg_signal"] else None,
            "avg_speed":    round(r["avg_speed"], 2)  if r["avg_speed"]  else None,
            "last_active":  last_active,
            "carriers_used": r["carriers_used"],
        })

    return jsonify(output)


@app.route("/api/buildings")
def get_buildings():
    """Per-building signal aggregation."""
    carrier = request.args.get("carrier", "").strip()
    network = request.args.get("network_type", "").strip()

    # Fetch all relevant points
    sql = "SELECT lat, lng, signal_strength, download_speed FROM signal_data"
    filters, params = [], {}
    if carrier and carrier in VALID_CARRIERS:
        filters.append("carrier = :carrier")
        params["carrier"] = carrier
    if network and network in VALID_NETWORKS:
        filters.append("network_type = :network")
        params["network"] = network
    if filters:
        sql += " WHERE " + " AND ".join(filters)

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params)
        all_points = [dict(r._mapping) for r in rows]

    result = []
    for b in VIT_BUILDINGS:
        b_lat, b_lng, b_r = b["lat"], b["lng"], b["radius_m"]
        nearby = [
            p for p in all_points
            if _haversine_m(p["lat"], p["lng"], b_lat, b_lng) <= b_r
        ]

        signals = [p["signal_strength"] for p in nearby if p["signal_strength"] is not None]
        speeds  = [p["download_speed"]   for p in nearby if p["download_speed"]  is not None]

        avg_signal = round(sum(signals) / len(signals), 1) if signals else None
        avg_speed  = round(sum(speeds)  / len(speeds),  2) if speeds  else None
        label, quality = _signal_quality(avg_signal)

        result.append({
            "id":         b["id"],
            "name":       b["name"],
            "name_ta":    b["name_ta"],
            "lat":        b_lat,
            "lng":        b_lng,
            "samples":    len(nearby),
            "avg_signal": avg_signal,
            "avg_speed":  avg_speed,
            "quality":    quality,
            "quality_label": label,
        })

    return jsonify(result)


@app.route("/api/signal-history")
def get_signal_history():
    """Hourly average signal/speed for the last 7 days."""
    carrier = request.args.get("carrier", "").strip()
    network = request.args.get("network_type", "").strip()

    filters = []
    params  = {}

    if carrier and carrier in VALID_CARRIERS:
        filters.append("carrier = :carrier")
        params["carrier"] = carrier
    if network and network in VALID_NETWORKS:
        filters.append("network_type = :network")
        params["network"] = network

    where = ("WHERE " + " AND ".join(filters) + " AND ") if filters else "WHERE "

    if "sqlite" in DATABASE_URL:
        time_filter = "created_at > datetime('now', '-7 days')"
        bucket_expr = "strftime('%Y-%m-%dT%H:00:00', created_at)"
    else:
        time_filter = "created_at > NOW() - INTERVAL '7 days'"
        bucket_expr = "DATE_TRUNC('hour', created_at AT TIME ZONE 'UTC')"

    sql = f"""
        SELECT
            {bucket_expr}      AS bucket,
            AVG(signal_strength) AS avg_signal,
            AVG(download_speed)  AS avg_speed,
            COUNT(*)             AS count
        FROM signal_data
        {where}{time_filter}
        GROUP BY bucket
        ORDER BY bucket ASC
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params)
        results = [dict(r._mapping) for r in rows]

    output = []
    for r in results:
        bucket = r["bucket"]
        if hasattr(bucket, "isoformat"):
            bucket = bucket.isoformat()
        output.append({
            "bucket":     str(bucket),
            "avg_signal": round(r["avg_signal"], 1) if r["avg_signal"] else None,
            "avg_speed":  round(r["avg_speed"],  2) if r["avg_speed"]  else None,
            "count":      r["count"],
        })

    return jsonify(output)


@app.route("/api/coverage")
def get_coverage():
    """Campus coverage percentage (% of 30m grid cells with at least 1 reading)."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT lat, lng FROM signal_data"))
        points = [(r[0], r[1]) for r in rows]

    pct = _compute_campus_coverage_pct(points)

    # Per-carrier coverage
    carrier_pcts = {}
    with engine.connect() as conn:
        for carrier in ["Airtel", "Jio", "VI", "BSNL"]:
            rows = conn.execute(text(
                "SELECT lat, lng FROM signal_data WHERE carrier = :c"
            ), {"c": carrier})
            c_points = [(r[0], r[1]) for r in rows]
            carrier_pcts[carrier] = _compute_campus_coverage_pct(c_points)

    return jsonify({
        "overall_pct": pct,
        "by_carrier":  carrier_pcts,
        "total_points": len(points),
    })


@app.route("/api/speed-test-payload")
def speed_test_payload():
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
