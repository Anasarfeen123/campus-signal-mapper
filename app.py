import eventlet
eventlet.monkey_patch()
import os
import requests
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import create_engine, text

# --- App and Database Setup ---

app = Flask(__name__)

# Load config from environment variables
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_very_secret_dev_key_fallback')
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("Warning: DATABASE_URL not set. App may not connect to DB.")

# Initialize SQLAlchemy engine
# We use "isolation_level="AUTOCOMMIT"" for INSERTs to be visible immediately
# This is simpler than managing sessions for this app's use case.
try:
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
except Exception as e:
    print(f"Error creating database engine: {e}")
    engine = None

# Initialize SocketIO
socketio = SocketIO(app)

# Initialize Rate Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour", "10 per minute"]
)

# --- Geofencing (VIT Chennai Bounds) ---
# (No changes to this section)
VIT_BOUNDS = {
    "min_lat": 12.839,
    "max_lat": 12.844,
    "min_lng": 80.151,
    "max_lng": 80.157
}

def is_within_bounds(lat, lng):
    return (VIT_BOUNDS["min_lat"] <= lat <= VIT_BOUNDS["max_lat"] and
            VIT_BOUNDS["min_lng"] <= lng <= VIT_BOUNDS["max_lng"])


# --- API Endpoints (Modified for SQLAlchemy) ---

@app.route('/api/samples')
def get_samples():
    if not engine:
        return jsonify({"error": "Database not configured"}), 500

    # Get query parameters
    carrier = request.args.get('carrier')
    network_type = request.args.get('network_type')

    # Build the query dynamically
    sql_query = "SELECT lat, lng, signal_strength, download_speed FROM signal_data"
    filters = []
    params = {}

    if carrier:
        filters.append("carrier = :carrier")
        params["carrier"] = carrier
    if network_type:
        filters.append("network_type = :network_type")
        params["network_type"] = network_type

    if filters:
        sql_query += " WHERE " + " AND ".join(filters)

    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql_query), params)
            # Fetchall and convert to list of dicts
            samples = [dict(row._mapping) for row in result]
        return jsonify(samples)
    except Exception as e:
        print(f"Error fetching samples: {e}")
        return jsonify({"error": f"Database query failed: {e}"}), 500


@app.route('/api/submit', methods=['POST'])
@limiter.limit("5 per minute") # Stricter limit for submission
def submit_data():
    if not engine:
        return jsonify({"error": "Database not configured"}), 500

    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    # Use 'data.get' for safe dictionary access
    lat = data.get('lat')
    lng = data.get('lng')
    
    # --- Validation ---
    if not all([lat, lng, data.get('carrier'), data.get('network_type')]):
        return jsonify({"error": "Missing required fields (lat, lng, carrier, or network_type)"}), 400
    
    if not is_within_bounds(lat, lng):
        return jsonify({"error": "Data is outside campus bounds"}), 403

    # --- Database Insertion ---
    sql_insert = """
    INSERT INTO signal_data (lat, lng, carrier, network_type, signal_strength, download_speed)
    VALUES (:lat, :lng, :carrier, :network_type, :signal_strength, :download_speed)
    """
    
    # Create a dictionary with the exact parameters for the query
    data_point = {
        "lat": lat,
        "lng": lng,
        "carrier": data.get('carrier'),
        "network_type": data.get('network_type'),
        "signal_strength": data.get('signal_strength'),
        "download_speed": data.get('download_speed')
    }

    try:
        with engine.connect() as connection:
            connection.execute(text(sql_insert), data_point)
            # Autocommit is handled by the engine config
            
        # Emit to all connected clients
        socketio.emit('new_data_point', data_point)
        return jsonify({"success": True, "message": "Data submitted"}), 201

    except Exception as e:
        print(f"Error inserting data: {e}")
        return jsonify({"error": f"Database insert failed: {e}"}), 500


# --- Carrier Detection API (No changes) ---

@app.route('/api/get-carrier')
def get_carrier():
    # Use 'X-Forwarded-For' if behind a proxy, else fallback to remote_addr
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    # Handle localhost/private IPs for development
    if ip_address.startswith(('127.', '192.', '10.', '172.')):
        return jsonify({"carrier": "Unknown (Local IP)"})
        
    try:
        response = requests.get(f'https://ipinfo.io/{ip_address}/org')
        if response.status_code == 200:
            # The response is just the org string, e.g., "AS55836 Reliance Jio Infocomm Limited"
            org_name = response.text.lower()
            if "airtel" in org_name:
                carrier = "Airtel"
            elif "jio" in org_name:
                carrier = "Jio"
            elif "vodafone" in org_name or "idea" in org_name or "vi" in org_name:
                carrier = "VI"
            elif "bsnl" in org_name:
                carrier = "BSNL"
            else:
                carrier = "Other"
            return jsonify({"carrier": carrier})
        else:
            return jsonify({"error": "Failed to detect carrier"}), 500
    except requests.RequestException:
        return jsonify({"error": "Carrier detection service failed"}), 503


# --- Frontend Routes (No changes) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload')
def upload_page():
    return render_template('upload.html')


# --- SocketIO Events (No changes) ---

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', {'message': 'Connected to real-time server'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


# --- Main Runner ---

if __name__ == '__main__':
    print("Starting Flask-SocketIO server in development mode...")
    # This runs the app in development
    # For production, you will use:
    # gunicorn --worker-class eventlet -w 1 app:app
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)