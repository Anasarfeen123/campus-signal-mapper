import eventlet
eventlet.monkey_patch()
from sqlalchemy.pool import NullPool

import os
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import create_engine, text
db_initialized = False


# -------------------------------------------------
# APP SETUP
# -------------------------------------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get(
    'FLASK_SECRET_KEY', 'dev_secret_key'
)

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")

# Render's managed Postgres can drop idle SSL connections.
# pool_pre_ping issues a lightweight SELECT 1 before handing out a
# connection, so dead sockets are discarded silently.  We keep
# NullPool (no persistent pool) because the free tier has very few
# allowed connections, but the pre-ping still fires on the fresh
# connection attempt and gives us an automatic retry path.
engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"},
    poolclass=NullPool,
    pool_pre_ping=True,
)

# -------------------------------------------------
# AUTO DB INIT (FREE TIER SAFE)
# -------------------------------------------------

def ensure_tables_exist():
    import time

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

    last_exc = None
    for attempt in range(3):          # up to 3 attempts
        try:
            with engine.begin() as conn:
                conn.execute(text(CREATE_SQL))
            return                     # success – stop retrying
        except Exception as e:
            last_exc = e
            print(f"DB init attempt {attempt + 1} failed: {e}")
            time.sleep(1 * (attempt + 1))   # 1 s, 2 s back-off

    # All retries exhausted – re-raise so the caller knows
    raise last_exc

@app.before_request
def init_db_once():
    global db_initialized
    if not db_initialized:
        try:
            ensure_tables_exist()
            db_initialized = True
        except Exception as e:
            print("DB init failed, retrying next request:", e)


socketio = SocketIO(app, cors_allowed_origins="*")

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["50000 per day", "5000 per hour"]
)

# -------------------------------------------------
# CAMPUS GEOFENCE (AUTHORITATIVE)
# -------------------------------------------------

VIT_BOUNDS = {
    "min_lat": 12.839,
    "max_lat": 12.844,
    "min_lng": 80.151,
    "max_lng": 80.157
}

def is_within_bounds(lat, lng):
    return (
        VIT_BOUNDS["min_lat"] <= lat <= VIT_BOUNDS["max_lat"] and
        VIT_BOUNDS["min_lng"] <= lng <= VIT_BOUNDS["max_lng"]
    )

# -------------------------------------------------
# GET HEATMAP DATA
# -------------------------------------------------

@app.route('/api/samples')
def get_samples():
    carrier = request.args.get('carrier')
    network = request.args.get('network_type')

    sql = """
        SELECT lat, lng, signal_strength, download_speed
        FROM signal_data
    """

    filters = []
    params = {}

    if carrier:
        filters.append("carrier = :carrier")
        params["carrier"] = carrier
    if network:
        filters.append("network_type = :network")
        params["network"] = network

    if filters:
        sql += " WHERE " + " AND ".join(filters)

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params)
        return jsonify([dict(r._mapping) for r in rows])

# -------------------------------------------------
# SUBMIT DATA (OFFLINE SAFE)
# -------------------------------------------------
@app.route('/api/submit', methods=['POST'])
@limiter.limit("5 per second")
def submit_data():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        lat = float(data["lat"])
        lng = float(data["lng"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Invalid coordinates"}), 400

    if not is_within_bounds(lat, lng):
        return jsonify({
            "error": "OUT_OF_CAMPUS",
            "message": "You are outside the VIT Chennai campus"
        }), 403

    payload = {
        "lat": lat,
        "lng": lng,
        "carrier": data.get("carrier"),
        "network_type": data.get("network_type"),
        "signal_strength": data.get("signal_strength"),
        "download_speed": data.get("download_speed"),
    }

    sql = """
        INSERT INTO signal_data (
            lat, lng, carrier, network_type,
            signal_strength, download_speed
        )
        VALUES (
            :lat, :lng, :carrier, :network_type,
            :signal_strength, :download_speed
        )
    """

    with engine.begin() as conn:   # auto-commits on block exit
        conn.execute(text(sql), payload)

    socketio.emit("new_data_point", payload)
    return jsonify({"success": True}), 201


# -------------------------------------------------
# CARRIER DETECTION
# -------------------------------------------------

@app.route('/api/get-carrier')
def get_carrier():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if ip.startswith(('127.', '192.', '10.', '172.')):
        return jsonify({"carrier": "Unknown (Local IP)"})

    try:
        r = requests.get(f"https://ipinfo.io/{ip}/org", timeout=3)
        org = r.text.lower()

        if "jio" in org:
            carrier = "Jio"
        elif "airtel" in org:
            carrier = "Airtel"
        elif "vodafone" in org or "idea" in org or "vi" in org:
            carrier = "VI"
        elif "bsnl" in org:
            carrier = "BSNL"
        else:
            carrier = "Other"

        return jsonify({"carrier": carrier})
    except requests.RequestException:
        return jsonify({"error": "Carrier detection failed"}), 503

# -------------------------------------------------
# FRONTEND ROUTES
# -------------------------------------------------

@app.route("/", methods=["GET"])
def health():
    return {"status": "ok", "service": "vit-signal-mapper-api"}, 200



@app.route("/upload", methods=["GET"])
def upload_info():
    return {
        "message": "Upload handled via /api/submit",
        "method": "POST",
        "format": "JSON"
    }, 200


# -------------------------------------------------
# SOCKET EVENTS
# -------------------------------------------------

@socketio.on('connect')
def on_connect():
    print("Client connected")

@socketio.on('disconnect')
def on_disconnect():
    print("Client disconnected")

# -------------------------------------------------
# RUN
# -------------------------------------------------

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,
        allow_unsafe_werkzeug=True
    )