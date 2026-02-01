import requests
import time
import random

# --- CONFIGURATION ---
# False -> send to the live server
USE_LOCALHOST = False

if USE_LOCALHOST:
    URL = 'http://localhost:5000/api/submit'
else:
    URL = 'https://vitc-signal-mapper.onrender.com/api/submit'

TOTAL_SAMPLES = 100

# --- GEOFENCE CONSTANTS---
VIT_BOUNDS = {
    "min_lat": 12.839,
    "max_lat": 12.844,
    "min_lng": 80.151,
    "max_lng": 80.157
}

CARRIERS = ['Airtel', 'Jio', 'VI', 'BSNL']
NETWORK_TYPES = ['4G', '5G']

def generate_safe_coordinate():
    """Generates a random coordinate strictly within campus bounds."""
    lat = random.uniform(VIT_BOUNDS["min_lat"], VIT_BOUNDS["max_lat"])
    lng = random.uniform(VIT_BOUNDS["min_lng"], VIT_BOUNDS["max_lng"])
    return lat, lng

print(f"--- Starting Test Submission ---")
print(f"Target: {URL}")
print(f"Count:  {TOTAL_SAMPLES} samples\n")

success_count = 0
fail_count = 0

try:
    for i in range(TOTAL_SAMPLES):
        lat, lng = generate_safe_coordinate()
        
        # Simulate realistic signal data
        # Signal strength usually ranges -50 (great) to -120 (dead zone)
        signal_strength = random.randint(-115, -60)
        
        # Higher signal strength often correlates with better speed, 
        # but we'll keep it random for simple testing.
        download_speed = random.uniform(2.0, 100.0) 

        payload = {
            'lat': lat,
            'lng': lng,
            'carrier': random.choice(CARRIERS),
            'network_type': random.choice(NETWORK_TYPES),
            'signal_strength': signal_strength,
            'download_speed': round(download_speed, 2)
        }

        try:
            r = requests.post(URL, json=payload, timeout=5)
            
            if r.status_code == 201:
                print(f"[{i+1}/{TOTAL_SAMPLES}] Success: {payload['carrier']} {payload['network_type']} at {lat:.4f}, {lng:.4f}")
                success_count += 1
            else:
                print(f"[{i+1}/{TOTAL_SAMPLES}] FAILED ({r.status_code}): {r.text}")
                fail_count += 1
                
        except requests.exceptions.ConnectionError:
            print(f"[{i+1}/{TOTAL_SAMPLES}] ERROR: Connection refused. Is the server running?")
            fail_count += 1
            # If server is down, stop trying
            break
        except Exception as e:
            print(f"[{i+1}/{TOTAL_SAMPLES}] ERROR: {e}")
            fail_count += 1

        # Small delay to prevent being rate-limited (app.py limits to 30/min, so we go slow)
        # Note: If testing locally with rate limits on, this might still be too fast.
        time.sleep(0.5) 

except KeyboardInterrupt:
    print("\nTest stopped by user.")

# --- SUMMARY REPORT ---
print("\n" + "="*30)
print(f"TEST COMPLETE")
print(f"Successful: {success_count}")
print(f"Failed:     {fail_count}")
print("="*30)