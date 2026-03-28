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

IS_SQLITE = "sqlite" in DATABASE_URL

if IS_SQLITE:
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
    {"id": "TT",      "name": "Technology Tower",  "name_ta": "தொழில்நுட்ப கோபுரம்", "lat": 12.8448, "lng": 80.1558, "radius_m": 90,  "floors": 8},
    {"id": "SJT",     "name": "SJT Block",          "name_ta": "SJT தொகுதி",           "lat": 12.8425, "lng": 80.1540, "radius_m": 80,  "floors": 6},
    {"id": "SMV",     "name": "SMV Block",          "name_ta": "SMV தொகுதி",           "lat": 12.8440, "lng": 80.1528, "radius_m": 75,  "floors": 5},
    {"id": "GDN",     "name": "GDN Block",          "name_ta": "GDN தொகுதி",           "lat": 12.8415, "lng": 80.1570, "radius_m": 70,  "floors": 5},
    {"id": "CDMM",    "name": "CDMM Building",      "name_ta": "CDMM கட்டிடம்",        "lat": 12.8432, "lng": 80.1560, "radius_m": 65,  "floors": 4},
    {"id": "LIBRARY", "name": "Central Library",    "name_ta": "மத்திய நூலகம்",        "lat": 12.8435, "lng": 80.1548, "radius_m": 55,  "floors": 3},
    {"id": "ANNA",    "name": "Anna Auditorium",    "name_ta": "அண்ணா அரங்கம்",        "lat": 12.8420, "lng": 80.1553, "radius_m": 60,  "floors": 2},
    {"id": "HOSTEL",  "name": "Hostel Zone",        "name_ta": "விடுதி மண்டலம்",       "lat": 12.8400, "lng": 80.1545, "radius_m": 110, "floors": 7},
]

# -------------------------------------------------
# DB INIT & MIGRATIONS
# -------------------------------------------------

def ensure_tables_exist():
    if IS_SQLITE:
        create_sql = """
        CREATE TABLE IF NOT EXISTS signal_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            carrier TEXT NOT NULL,
            network_type TEXT NOT NULL,
            signal_strength REAL,
            download_speed REAL,
            contributor_id TEXT DEFAULT 'anon',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    else:
        create_sql = """
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

    for attempt in range(1, 4):
        try:
            with engine.begin() as conn:
                conn.execute(text(create_sql))
                try:
                    conn.execute(text("ALTER TABLE signal_data ADD COLUMN contributor_id TEXT DEFAULT 'anon'"))
                except Exception:
                    pass
            print("✅ DB tables verified")
            return
        except Exception as e:
            print(f"⚠️ DB init attempt {attempt} failed: {e}")
            if attempt < 3:
                time.sleep(2 * attempt)
    raise RuntimeError("Could not initialise database")

ensure_tables_exist()

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
limiter = Limiter(get_remote_address, app=app, default_limits=["50000 per day", "5000 per hour"])

# -------------------------------------------------
# GEOFENCING & HELPERS
# -------------------------------------------------

VIT_POLYGON = [
    (12.8455, 80.1532), (12.8447, 80.1587), (12.8435, 80.1589),
    (12.8395, 80.1560), (12.8387, 80.1545), (12.8419, 80.1515),
    (12.8425, 80.1510), (12.8456, 80.1518)
]
_VIT_LAT_MIN = min(p[0] for p in VIT_POLYGON)
_VIT_LAT_MAX = max(p[0] for p in VIT_POLYGON)
_VIT_LNG_MIN = min(p[1] for p in VIT_POLYGON)
_VIT_LNG_MAX = max(p[1] for p in VIT_POLYGON)
_VIT_CENTER_LAT = (_VIT_LAT_MIN + _VIT_LAT_MAX) / 2
_VIT_CENTER_LNG = (_VIT_LNG_MIN + _VIT_LNG_MAX) / 2


def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _haversine_m(lat1, lng1, lat2, lng2):
    return _haversine_km(lat1, lng1, lat2, lng2) * 1000


def _ray_cast_inside(lat, lng, poly):
    """Point-in-polygon via ray casting. poly is list of (lat, lng) tuples."""
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        lat_i, lng_i = poly[i]
        lat_j, lng_j = poly[j]
        # Ray cast along longitude axis
        if ((lng_i > lng) != (lng_j > lng)) and \
                (lat < (lat_j - lat_i) * (lng - lng_i) / (lng_j - lng_i) + lat_i):
            inside = not inside
        j = i
    return inside


def is_within_bounds(lat, lng):
    if not (_VIT_LAT_MIN <= lat <= _VIT_LAT_MAX and _VIT_LNG_MIN <= lng <= _VIT_LNG_MAX):
        return False, "Outside bounding box"
    if _haversine_km(lat, lng, _VIT_CENTER_LAT, _VIT_CENTER_LNG) > 1.5:
        return False, "Too far from centre"
    if not _ray_cast_inside(lat, lng, VIT_POLYGON):
        return False, "Outside campus polygon"
    return True, "OK"

# -------------------------------------------------
# VALIDATION & AUTH
# -------------------------------------------------

VALID_CARRIERS = {"Airtel", "Jio", "VI", "BSNL", "Other", "Unknown"}
VALID_NETWORKS = {"2G", "3G", "4G", "5G", "Unknown"}


def _clean_contributor_id(raw):
    if not raw or not isinstance(raw, str):
        return "anon"
    cleaned = raw.strip().lower()
    return cleaned if (len(cleaned) <= 40 and all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in cleaned)) else "anon"


def _clean_signal(value):
    try:
        v = float(value)
        return v if -140 <= v <= -20 else None
    except:
        return None


def _clean_speed(value):
    try:
        v = float(value)
        return round(v, 3) if 0 < v <= 10000 else None
    except:
        return None


def _signal_quality(avg_dbm):
    if avg_dbm is None:
        return "No Data", "none"
    if avg_dbm >= -70:
        return "Excellent", "excellent"
    if avg_dbm >= -85:
        return "Good", "good"
    if avg_dbm >= -100:
        return "Fair", "fair"
    return "Poor", "poor"


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# -------------------------------------------------
# ROUTES — Pages
# -------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload")
def upload_page():
    return render_template("upload.html")


@app.route("/leaderboard")
def leaderboard_page():
    return render_template("leaderboard.html")


@app.route("/buildings")
def buildings_page():
    return render_template("buildings.html")


@app.route("/sw.js")
def serve_sw():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


@app.route("/manifest.json")
def serve_manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")


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
def admin_dashboard():
    return render_template("admin.html")

# -------------------------------------------------
# ROUTES — Admin API
# -------------------------------------------------

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
        if hasattr(row.get("created_at"), "isoformat"):
            row["created_at"] = row["created_at"].isoformat()
        writer.writerow(row)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="vit_signal_data.csv"
    )


@app.route("/api/admin/recent")
@admin_required
def admin_recent():
    limit = min(int(request.args.get("limit", 100)), 1000)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM signal_data ORDER BY created_at DESC LIMIT :limit"),
            {"limit": limit}
        )
        data = [dict(r._mapping) for r in rows]
    for r in data:
        if hasattr(r.get("created_at"), "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
    return jsonify(data)


@app.route("/admin/delete/<int:row_id>", methods=["POST"])
@admin_required
def admin_delete_row(row_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM signal_data WHERE id = :id"), {"id": row_id})
    return jsonify({"success": True})


@app.route("/admin/delete-all", methods=["POST"])
@admin_required
def admin_delete_all():
    data = request.get_json(silent=True) or {}
    if data.get("confirm") != "DELETE_ALL":
        return jsonify({"error": "Confirmation required"}), 400
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM signal_data"))
    return jsonify({"success": True})

# -------------------------------------------------
# ROUTES — Public API
# -------------------------------------------------

@app.route("/api/submit", methods=["POST"])
@limiter.limit("10 per second")
def submit_data():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    try:
        lat, lng = float(data["lat"]), float(data["lng"])
        valid, reason = is_within_bounds(lat, lng)
        if not valid:
            return jsonify({"error": "OUT_OF_CAMPUS", "message": reason}), 403

        payload = {
            "lat": lat,
            "lng": lng,
            "carrier": data.get("carrier") if data.get("carrier") in VALID_CARRIERS else "Other",
            "network_type": data.get("network_type", "Unknown").upper() if data.get("network_type") in VALID_NETWORKS else "Unknown",
            "signal_strength": _clean_signal(data.get("signal_strength")),
            "download_speed": _clean_speed(data.get("download_speed")),
            "contributor_id": _clean_contributor_id(data.get("contributor_id"))
        }
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO signal_data (lat, lng, carrier, network_type, signal_strength, download_speed, contributor_id) "
                     "VALUES (:lat, :lng, :carrier, :network_type, :signal_strength, :download_speed, :contributor_id)"),
                payload
            )

        socketio.emit("new_data_point", {k: v for k, v in payload.items() if k != "contributor_id"})
        return jsonify({"success": True}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/samples")
def get_samples():
    carrier = request.args.get("carrier")
    network_type = request.args.get("network_type")
    limit = min(int(request.args.get("limit", 5000)), 10000)

    filters = []
    params = {"limit": limit}
    if carrier:
        filters.append("carrier = :carrier")
        params["carrier"] = carrier
    if network_type:
        filters.append("network_type = :network_type")
        params["network_type"] = network_type

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = f"SELECT lat, lng, signal_strength, download_speed, carrier, network_type, created_at FROM signal_data {where} ORDER BY created_at DESC LIMIT :limit"

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params)
        results = [dict(r._mapping) for r in rows]
    for r in results:
        if hasattr(r.get("created_at"), "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
    return jsonify(results)


@app.route("/api/stats")
def get_stats():
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT
                COUNT(*)                          AS total_samples,
                ROUND(AVG(signal_strength), 1)    AS avg_signal_dbm,
                ROUND(AVG(download_speed), 2)     AS avg_speed_mbps,
                SUM(CASE WHEN network_type='5G' THEN 1 ELSE 0 END) AS five_g_count,
                COUNT(DISTINCT carrier)            AS unique_carriers
            FROM signal_data
        """)).fetchone()
    d = dict(row._mapping)
    return jsonify(d)


@app.route("/api/leaderboard")
def get_leaderboard():
    limit = min(int(request.args.get("limit", 20)), 100)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                contributor_id,
                COUNT(*)                       AS submissions,
                ROUND(AVG(signal_strength), 1) AS avg_signal,
                ROUND(AVG(download_speed), 2)  AS avg_speed,
                MAX(created_at)                AS last_active
            FROM signal_data
            WHERE contributor_id IS NOT NULL AND contributor_id != 'anon'
            GROUP BY contributor_id
            ORDER BY submissions DESC
            LIMIT :limit
        """), {"limit": limit})
        data = [dict(r._mapping) for r in rows]

    result = []
    for i, entry in enumerate(data):
        cid = entry["contributor_id"] or ""
        if hasattr(entry.get("last_active"), "isoformat"):
            entry["last_active"] = entry["last_active"].isoformat()
        result.append({
            "rank": i + 1,
            "display_id": f"VIT-{cid[:8].upper()}",
            "submissions": entry["submissions"],
            "avg_signal": entry["avg_signal"],
            "avg_speed": entry["avg_speed"],
            "last_active": entry["last_active"],
        })
    return jsonify(result)


@app.route("/api/buildings")
def get_buildings():
    carrier = request.args.get("carrier")
    network_type = request.args.get("network_type")

    filters = []
    params = {}
    if carrier:
        filters.append("carrier = :carrier")
        params["carrier"] = carrier
    if network_type:
        filters.append("network_type = :network_type")
        params["network_type"] = network_type
    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    sql = f"SELECT lat, lng, signal_strength, download_speed FROM signal_data {where}"

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params)
        all_points = [dict(r._mapping) for r in rows]

    results = []
    for bld in VIT_BUILDINGS:
        nearby = [
            p for p in all_points
            if _haversine_m(p["lat"], p["lng"], bld["lat"], bld["lng"]) <= bld["radius_m"]
        ]
        samples = len(nearby)
        signals = [p["signal_strength"] for p in nearby if p["signal_strength"] is not None]
        speeds  = [p["download_speed"]  for p in nearby if p["download_speed"]  is not None]

        avg_signal = round(sum(signals) / len(signals), 1) if signals else None
        avg_speed  = round(sum(speeds)  / len(speeds),  2) if speeds  else None
        _, quality = _signal_quality(avg_signal)

        results.append({
            "id":         bld["id"],
            "name":       bld["name"],
            "name_ta":    bld["name_ta"],
            "lat":        bld["lat"],
            "lng":        bld["lng"],
            "samples":    samples,
            "avg_signal": avg_signal,
            "avg_speed":  avg_speed,
            "quality":    quality,
        })

    return jsonify(results)


@app.route("/api/coverage")
def get_coverage():
    """Compute % of 30m grid cells within campus that have at least one reading."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT lat, lng, carrier FROM signal_data"))
        all_points = [dict(r._mapping) for r in rows]

    # Build a set of occupied 30m grid cells
    GRID_M = 30
    LAT_DEG = GRID_M / 111_000
    LNG_DEG = GRID_M / (111_000 * math.cos(math.radians(_VIT_CENTER_LAT)))

    occupied: set = set()
    carrier_cells: dict = {}

    for p in all_points:
        cell = (int(p["lat"] / LAT_DEG), int(p["lng"] / LNG_DEG))
        occupied.add(cell)
        c = p.get("carrier", "Unknown")
        carrier_cells.setdefault(c, set()).add(cell)

    # Total campus cells
    total_campus_cells = 0
    lat = _VIT_LAT_MIN
    while lat <= _VIT_LAT_MAX:
        lng = _VIT_LNG_MIN
        while lng <= _VIT_LNG_MAX:
            if _ray_cast_inside(lat, lng, VIT_POLYGON):
                total_campus_cells += 1
            lng += LNG_DEG
        lat += LAT_DEG

    total_campus_cells = max(total_campus_cells, 1)
    overall_pct = round(len(occupied) / total_campus_cells * 100, 1)
    overall_pct = min(overall_pct, 100.0)

    by_carrier = {
        carrier: round(min(len(cells) / total_campus_cells * 100, 100.0), 1)
        for carrier, cells in carrier_cells.items()
        if carrier not in ("Unknown", "Other", "anon")
    }

    return jsonify({"overall_pct": overall_pct, "by_carrier": by_carrier})


@app.route("/api/signal-history")
def get_signal_history():
    """Return bucketed signal/speed averages over the last 7 days."""
    carrier = request.args.get("carrier")
    network_type = request.args.get("network_type")

    filters = []
    params = {}
    if carrier:
        filters.append("carrier = :carrier")
        params["carrier"] = carrier
    if network_type:
        filters.append("network_type = :network_type")
        params["network_type"] = network_type

    where = ("AND " + " AND ".join(filters)) if filters else ""

    if IS_SQLITE:
        sql = f"""
            SELECT
                strftime('%Y-%m-%dT%H:00:00', created_at) AS bucket,
                ROUND(AVG(signal_strength), 1)             AS avg_signal,
                ROUND(AVG(download_speed),  2)             AS avg_speed
            FROM signal_data
            WHERE created_at >= datetime('now', '-7 days') {where}
            GROUP BY bucket
            ORDER BY bucket ASC
        """
    else:
        sql = f"""
            SELECT
                date_trunc('hour', created_at)             AS bucket,
                ROUND(AVG(signal_strength)::numeric, 1)    AS avg_signal,
                ROUND(AVG(download_speed)::numeric,  2)    AS avg_speed
            FROM signal_data
            WHERE created_at >= NOW() - INTERVAL '7 days' {where}
            GROUP BY bucket
            ORDER BY bucket ASC
        """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params)
        data = [dict(r._mapping) for r in rows]

    for r in data:
        if hasattr(r.get("bucket"), "isoformat"):
            r["bucket"] = r["bucket"].isoformat()

    return jsonify(data)


@app.route("/api/speed-test-payload")
def speed_test_payload():
    """Return ~200 KB of random bytes for client-side speed testing."""
    size = 200 * 1024
    return app.response_class(
        response=os.urandom(size),
        status=200,
        mimetype="application/octet-stream",
        headers={"Cache-Control": "no-store"}
    )


@app.route("/api/get-carrier")
def get_carrier():
    """Best-effort carrier detection via IP geolocation."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip:
        ip = ip.split(",")[0].strip()

    # Local / private IPs can't be looked up
    private_prefixes = ("127.", "10.", "192.168.", "::1", "172.")
    if any(ip.startswith(p) for p in private_prefixes):
        return jsonify({"carrier": "Unknown (Local IP)", "ip": ip})

    try:
        res = requests.get(f"https://ipapi.co/{ip}/json/", timeout=4)
        if res.ok:
            d = res.json()
            org = d.get("org", "")
            # Map common Indian ISP strings to carrier names
            carrier_map = {
                "jio": "Jio", "reliance": "Jio",
                "airtel": "Airtel", "bharti": "Airtel",
                "vodafone": "VI", "idea": "VI", "vi ": "VI",
                "bsnl": "BSNL",
            }
            org_lower = org.lower()
            for keyword, name in carrier_map.items():
                if keyword in org_lower:
                    return jsonify({"carrier": name, "org": org})
            return jsonify({"carrier": org or "Unknown", "org": org})
    except Exception:
        pass

    return jsonify({"carrier": "Unknown"})


# -------------------------------------------------
# MAIN
# -------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)