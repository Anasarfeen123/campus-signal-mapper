"""Simple script to POST random-ish samples to the server for testing."""
import requests
import time
import random

# *** Use your deployed Render URL or http://localhost:5000 for local testing ***
URL = 'https://vitc-signal-mapper.onrender.com/api/submit'
# URL = 'http://localhost:5000/api/submit'

carriers = ['Airtel', 'Jio', 'VI', 'BSNL']

# Center on VIT Chennai campus lat/lon
center_lat, center_lon = 12.8406, 80.1534

print(f"Sending 100 test samples to {URL}...")

for i in range(100):
    lat = center_lat + random.uniform(-0.003, 0.003)
    lon = center_lon + random.uniform(-0.003, 0.003)
    
    # --- FIX: Update keys to match app.py ---
    sample = {
        'lat': lat,
        'lng': lon,
        'carrier': random.choice(carriers),
        'signal_strength': random.randint(-115, -55), # Was 'dbm'
        'network_type': random.choice(['3G','4G','5G']),
        'download_speed': random.uniform(5.0, 150.0), # Was 'download_mbps'
    }
    # --- END FIX ---
    
    try:
        r = requests.post(URL, json=sample)
        if r.status_code != 201:
            print(f"Error: {r.status_code}", r.json())
        else:
            print(f"Sent sample {i+1}/100...")
            
    except requests.exceptions.ConnectionError:
        print({'status': 'error', 'message': 'Connection refused. Is the server running?'})
        break
    time.sleep(0.1) # Slowed down slightly

print("Test script finished.")