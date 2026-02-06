import eventlet
eventlet.monkey_patch()
from sqlalchemy.pool import NullPool

import os
import requests
import time
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import create_engine, text

# -------------------------------------------------
# APP SETUP
# -------------------------------------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get(
    'FLASK_SECRET_KEY', 'dev_secret_key'
)

# Detect if running locally or on Render
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set. Run '$env:DATABASE_URL = \"sqlite:///signals.db\"' for local testing.")

# Configure Engine based on DB type
if "sqlite" in DATABASE_URL:
    # Local SQLite Configuration
    engine = create_engine(DATABASE_URL, poolclass=NullPool)
else:
    # Render PostgreSQL Configuration
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        connect_args={
            "sslmode": "require"
        }
    )

# -------------------------------------------------
# AUTO DB INIT
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
    # Adjust SERIAL for SQLite compatibility if necessary
    if "sqlite" in DATABASE_URL:
        CREATE_SQL = CREATE_SQL.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        CREATE_SQL = CREATE_SQL.replace("TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP")

    for attempt in range(1, 4):
        try:
            with engine.begin() as conn:
                conn.execute(text(CREATE_SQL))
            print("DB tables verified OK")
            return
        except Exception as e:
            print(f"DB init attempt {attempt} failed: {e}")
            if attempt < 3:
                time.sleep(2 * attempt)
    raise RuntimeError("Could not initialise database after 3 attempts")

ensure_tables_exist()

socketio = SocketIO(app, cors_allowed_origins="*")

# Limiter can be disabled for local ESP32 testing if it causes issues
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["50000 per day", "5000 per hour"]
)

# -------------------------------------------------
# CAMPUS GEOFENCE (AUTHORITATIVE)
# -------------------------------------------------

# --- CAMPUS POLYGON ---
VIT_POLYGON = [
    (12.8455, 80.1532), (12.8447, 80.1587), (12.8435, 80.1589),
    (12.8395, 80.1560), (12.8387, 80.1545), (12.8419, 80.1515),
    (12.8425, 80.1510), (12.8456, 80.1518)
]

def is_within_bounds(lat, lng):
    """Checks if a coordinate is inside the VIT Chennai campus polygon."""
    n = len(VIT_POLYGON)
    inside = False
    p1x, p1y = VIT_POLYGON[0]
    for i in range(n + 1):
        p2x, p2y = VIT_POLYGON[i % n]
        if lat > min(p1x, p2x):
            if lat <= max(p1x, p2x):
                if lng <= max(p1y, p2y):
                    if p1x != p2x:
                        xints = (lat - p1x) * (p2y - p1y) / (p2x - p1x) + p1y
                    if p1y == p2y or lng <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside
# -------------------------------------------------
# FRONTEND ROUTES
# -------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    """Serves the main heatmap page."""
    return render_template("index.html")

@app.route("/upload", methods=["GET"])
def upload_page():
    """Serves the data contribution page."""
    return render_template("upload.html")

# -------------------------------------------------
# API ENDPOINTS
# -------------------------------------------------

@app.route('/api/samples')
def get_samples():
    carrier = request.args.get('carrier')
    network = request.args.get('network_type')

    sql = "SELECT lat, lng, signal_strength, download_speed FROM signal_data"
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

@app.route('/api/submit', methods=['POST'])
@limiter.limit("5 per second")
def submit_data():
    """Endpoint for web users and ESP32 nodes."""
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
            "message": "Data point is outside campus bounds"
        }), 403

    payload = {
        "lat": lat,
        "lng": lng,
        "carrier": data.get("carrier", "Unknown"),
        "network_type": data.get("network_type", "Unknown"),
        "signal_strength": data.get("signal_strength"),
        "download_speed": data.get("download_speed"),
    }

    sql = """
        INSERT INTO signal_data (lat, lng, carrier, network_type, signal_strength, download_speed)
        VALUES (:lat, :lng, :carrier, :network_type, :signal_strength, :download_speed)
    """

    with engine.begin() as conn:
        conn.execute(text(sql), payload)

    socketio.emit("new_data_point", payload)
    return jsonify({"success": True}), 201

@app.route('/api/speed-test-payload')
def speed_test_payload():
    """
    Serves a 512KB text response for the frontend to download
    and measure throughput.
    """
    # 512 KB of data (approx 4Mb). 
    # Adjust size: 512 * 1024 bytes
    data_size = 512 * 1024
    return "0" * data_size

@app.route('/api/get-carrier')
def get_carrier():
    # 1. Extract the primary IP from the X-Forwarded-For chain
    raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    # 2. Clean the IP: Take only the first one if it's a list
    ip = raw_ip.split(',')[0].strip()
    
    # 3. Skip detection for local/private IPs
    if ip.startswith(('127.', '192.', '10.', '172.')) or ip == '::1':
        return jsonify({"carrier": "Unknown (Local IP)"})

    try:
        # 4. Increased timeout to 10s to handle Render's DNS resolution issues
        r = requests.get(f"https://ipinfo.io/{ip}/org", timeout=10)
        
        if r.status_code == 200:
            org = r.text.lower()
            if "jio" in org: carrier = "Jio"
            elif "airtel" in org: carrier = "Airtel"
            elif "vodafone" in org or "idea" in org or "vi" in org: carrier = "VI"
            elif "bsnl" in org: carrier = "BSNL"
            else: carrier = "Other"
            return jsonify({"carrier": carrier})
        
        return jsonify({"carrier": "Other", "reason": f"API status {r.status_code}"})

    except requests.exceptions.RequestException as e:
        # Log error but return a safe fallback to "Other"
        print(f"Carrier detection error: {e}")
        return jsonify({"carrier": "Other", "error": "Detection timed out"}), 200
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
    port = int(os.environ.get("PORT", 5000))
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=True,
        allow_unsafe_werkzeug=True
    )