"""Simple script to POST random-ish samples to the server for testing."""
import requests
import time
import random


URL = 'http://localhost:5000/api/submit'


carriers = ['Airtel', 'Jio', 'VI', 'BSNL']


# Center on VIT Chennai campus lat/lon
center_lat, center_lon = 12.8406, 80.1534


for i in range(100):
    # Reduced spread to be more focused on the campus
    lat = center_lat + random.uniform(-0.003, 0.003)
    lon = center_lon + random.uniform(-0.003, 0.003)
    sample = {
    'device_id': f'device_{random.randint(1,30)}',
    'timestamp': int(time.time()),
    'latitude': lat,
    'longitude': lon,
    'carrier': random.choice(carriers),
    'dbm': random.randint(-115, -55),
    'network_type': random.choice(['3G','4G','5G']),
    'download_mbps': random.uniform(5.0, 150.0), # Add random speed
    'upload_mbps': random.uniform(1.0, 50.0)      # Add random speed
    }
    
    try:
        r = requests.post(URL, json=sample)
        print(r.json())
    except requests.exceptions.ConnectionError:
        print({'status': 'error', 'message': 'Connection refused. Is the server running?'})
        break
    time.sleep(0.05)