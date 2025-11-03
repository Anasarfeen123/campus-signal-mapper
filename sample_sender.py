"""Simple script to POST random-ish samples to the server for testing."""
import requests
import time
import random


URL = 'http://localhost:5000/api/submit'


carriers = ['Airtel', 'Jio', 'VI', 'BSNL']


# center on a campus lat/lon (example)
center_lat, center_lon = 12.9716, 80.2200


for i in range(100):
    lat = center_lat + random.uniform(-0.004, 0.004)
    lon = center_lon + random.uniform(-0.006, 0.006)
    sample = {
    'device_id': f'device_{random.randint(1,30)}',
    'timestamp': int(time.time()),
    'latitude': lat,
    'longitude': lon,
    'carrier': random.choice(carriers),
    'dbm': random.randint(-115, -55),
    'network_type': random.choice(['3G','4G','5G'])
    }
    r = requests.post(URL, json=sample)
    print(r.json())
    time.sleep(0.05)