# db.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import quote_plus, urlparse, urlunparse
import os
from dotenv import load_dotenv
import sys

# Load .env hanya untuk development
load_dotenv()

# Get DATABASE_URL
raw_url = os.getenv("DATABASE_URL")

if not raw_url:
    print("❌ ERROR: DATABASE_URL tidak ditemukan di environment variables!")
    print("   Pastikan sudah set di Railway Dashboard → Variables")
    sys.exit(1)

print(f"🔍 Parsing DATABASE_URL...")

try:
    parsed = urlparse(raw_url)
    
    # Extract password
    password = parsed.password
    if password is None:
        print("❌ ERROR: DATABASE_URL tidak memiliki password!")
        sys.exit(1)
    
    # Encode password (supaya karakter khusus ! @ : tidak bikin error)
    encoded_password = quote_plus(password)
    
    # Rebuild URL dengan password yang sudah encoded
    safe_netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
    
    # Handle port (bisa None)
    if parsed.port:
        safe_netloc += f":{parsed.port}"
    
    safe_url = urlunparse((
        parsed.scheme,
        safe_netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment
    ))
    
    print(f"✅ Database URL parsed successfully")
    print(f"   Host: {parsed.hostname}")
    print(f"   Port: {parsed.port or 'default'}")
    print(f"   Database: {parsed.path.strip('/')}")

except Exception as e:
    print(f"❌ ERROR parsing DATABASE_URL: {e}")
    sys.exit(1)

# Create Engine
try:
    print(f"🔌 Connecting to database...")
    
    engine = create_engine(
        safe_url,
        pool_pre_ping=True,        # menjaga koneksi tetap hidup
        pool_size=5,
        max_overflow=10,
        echo=False,                 # Set True untuk debug SQL queries
        connect_args={
            "connect_timeout": 10,
        }
    )
    
    # Test connection dengan SQLAlchemy 2.0 syntax
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        result.fetchone()
        print(f"✅ Database connected successfully!")
    
except Exception as e:
    print(f"❌ ERROR: Database connection failed!")
    print(f"   Error: {e}")
    print(f"   ")
    print(f"   Troubleshooting:")
    print(f"   1. Pastikan DATABASE_URL benar di Railway Variables")
    print(f"   2. Cek Supabase pooler masih aktif")
    print(f"   3. Cek firewall/network rules")
    import traceback
    traceback.print_exc()
    sys.exit(1)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency untuk FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()