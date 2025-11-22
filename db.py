# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import quote_plus, urlparse, urlunparse
import os
from dotenv import load_dotenv

load_dotenv()

raw_url = os.getenv("DATABASE_URL")

if not raw_url:
    raise RuntimeError("❌ DATABASE_URL tidak ditemukan di .env")

# --- Safety check: URL encoding password otomatis ---
parsed = urlparse(raw_url)

# extract password
password = parsed.password
if password is None:
    raise RuntimeError("❌ DATABASE_URL tidak memiliki password!")

# encode password (supaya ! @ : tidak bikin error)
encoded_password = quote_plus(password)

# rebuild URL dengan password yang sudah encoded
safe_netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}:{parsed.port}"
safe_url = urlunparse((
    parsed.scheme,
    safe_netloc,
    parsed.path,
    parsed.params,
    parsed.query,
    parsed.fragment
))

# Engine ke Supabase
engine = create_engine(
    safe_url,
    pool_pre_ping=True,        # menjaga koneksi tetap hidup
    pool_size=5,
    max_overflow=10
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency untuk FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
