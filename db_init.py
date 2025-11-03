"""Create SQLite DB."""
import sqlite3


conn = sqlite3.connect('signals.db')
cur = conn.cursor()
cur.execute('''
CREATE TABLE IF NOT EXISTS samples (
id INTEGER PRIMARY KEY AUTOINCREMENT,
timestamp INTEGER,
latitude REAL,
longitude REAL,
carrier TEXT,
dbm INTEGER,
network_type TEXT,
device_id TEXT
)
''')
cur.execute('CREATE INDEX IF NOT EXISTS idx_ts ON samples(timestamp)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_loc ON samples(latitude, longitude)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_carrier ON samples(carrier)')
conn.commit()
conn.close()
print('DB ready')