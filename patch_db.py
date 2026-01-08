from sqlalchemy import create_engine, text
from config.secrets import DATABASE_URL

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    sql = text("ALTER TABLE problems ADD COLUMN premium BOOLEAN NOT NULL DEFAULT 0;")
    conn.execute(sql)
    conn.commit()
    print("Migration successful: Added 'premium' column.")
