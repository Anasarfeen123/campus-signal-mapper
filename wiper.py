from sqlalchemy import create_engine, text

# Use your EXTERNAL DATABASE URL here
DB_URL = "postgresql://codecrusader07:SF9EymAJohScyYHAqGxa7YvvF0dlvRhv@dpg-d62mur4r85hc739npgh0-a.oregon-postgres.render.com/vitcsignal_8thr"

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text("TRUNCATE TABLE signal_data RESTART IDENTITY;"))
    print("Remote database wiped clean.")