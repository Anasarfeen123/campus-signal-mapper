import os
from sqlalchemy import create_engine, text

# Get the database URL from the environment variable
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("No DATABASE_URL environment variable set")

# --- NEW: Query to create a users table ---
CREATE_USERS_TABLE_QUERY = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""

# --- MODIFIED: Query to add user_id to signal_data ---
CREATE_SIGNAL_TABLE_QUERY = """
CREATE TABLE IF NOT EXISTS signal_data (
    id SERIAL PRIMARY KEY,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    carrier TEXT NOT NULL,
    network_type TEXT NOT NULL,
    signal_strength REAL, 
    download_speed REAL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- This links submissions to a user, but allows anonymous (NULL) submissions
    user_id INTEGER REFERENCES users(id) DEFAULT NULL 
);
"""

def initialize_database():
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # --- Run BOTH queries ---
            connection.execute(text(CREATE_USERS_TABLE_QUERY))
            connection.execute(text(CREATE_SIGNAL_TABLE_QUERY))
            connection.commit() 
            
        print("Database connection successful.")
        print("Tables 'users' and 'signal_data' are ready.")

    except Exception as e:
        print(f"Error connecting to database or initializing table: {e}")
        print("Please check your DATABASE_URL environment variable.")

if __name__ == "__main__":
    initialize_database()