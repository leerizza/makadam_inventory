# security.py
import os
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "changeme-super-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 480))  # 8 jam default

# Configure password context with bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__default_rounds=12,
)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Verify a plain password against hashed password.
    Handles bcrypt 72-byte limitation automatically.
    """
    try:
        # bcrypt has 72 byte limit, passlib handles this automatically
        return pwd_context.verify(plain_password, password_hash)
    except ValueError as e:
        # Log the error for debugging
        print(f"Password verification error: {e}")
        # If it's the 72-byte error, truncate and try again
        if "72 bytes" in str(e):
            return pwd_context.verify(plain_password[:72], password_hash)
        raise


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    Automatically truncates to 72 bytes if needed.
    """
    try:
        # bcrypt has 72 byte limit
        if len(password.encode('utf-8')) > 72:
            print(f"⚠️ Password truncated to 72 bytes for bcrypt")
            password = password[:72]
        
        return pwd_context.hash(password)
    except Exception as e:
        print(f"Error hashing password: {e}")
        raise


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt