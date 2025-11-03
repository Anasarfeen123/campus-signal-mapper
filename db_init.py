import os
from sqlalchemy import create_engine, text

# Get the database URL from the environment variable
# Example: "postgresql://user:password@hostname/dbname"
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("No DATABASE_URL environment variable set")

# Create the table schema
# Note: Using 'TEXT' for carrier and network_type is more flexible.
# Using 'REAL' for numeric types is standard.
CREATE_TABLE_QUERY = """
CREATE TABLE IF NOT EXISTS signal_data (
    id SERIAL PRIMARY KEY,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    carrier TEXT NOT NULL,
    network_type TEXT NOT NULL,
    signal_strength REAL, 
    download_speed REAL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""

def initialize_database():
    try:
        # Create a database engine
        engine = create_engine(DATABASE_URL)
        
        # Connect and execute the table creation query
        with engine.connect() as connection:
            connection.execute(text(CREATE_TABLE_QUERY))
            connection.commit() # Commit the transaction
            
        print("Database connection successful.")
        print("Table 'signal_data' is ready.")

    except Exception as e:
        print(f"Error connecting to database or initializing table: {e}")
        print("Please check your DATABASE_URL environment variable.")

if __name__ == "__main__":
    initialize_database()