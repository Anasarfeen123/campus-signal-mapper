import requests
import time
import random

# --- CONFIGURATION ---
# False -> send to the live server
USE_LOCALHOST = True

if USE_LOCALHOST:
    URL = 'http://localhost:5000/api/submit'
else:
    URL = 'https://vitc-signal-mapper.onrender.com/api/submit'

TOTAL_SAMPLES = 100

VIT_POLYGON = [
    (12.8455, 80.1532), (12.8447, 80.1587), (12.8435, 80.1589),
    (12.8395, 80.1560), (12.8387, 80.1545), (12.8419, 80.1515),
    (12.8425, 80.1510), (12.8456, 80.1518)
]
CARRIERS = ['Airtel', 'Jio', 'VI', 'BSNL']
NETWORK_TYPES = ['4G', '5G']

# Copy the VIT_POLYGON and is_within_bounds function from app.py above
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

def generate_safe_coordinate():
    """Generates random points until one falls inside the campus polygon."""
    while True:
        # Bounding box covering the whole campus
        lat = random.uniform(12.838, 12.846)
        lng = random.uniform(80.150, 80.160)
        
        if is_within_bounds(lat, lng):
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