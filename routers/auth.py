# routers/auth.py
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from db import get_db
import models, schemas
from security import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES


from jose import JWTError, jwt
from security import SECRET_KEY, ALGORITHM
from schemas import TokenData


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=schemas.UserOut)
def register_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")

    user = models.User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        is_admin=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    try:
        user = (
            db.query(models.User)
            .filter(models.User.username == form_data.username)
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )

        # kalau hash di DB aneh (bukan bcrypt yang valid), ini bisa lempar error
        try:
            is_valid = verify_password(form_data.password, user.password_hash)
        except Exception as e:
            # tulis ke logs Railway biar keliatan
            print("Error verifying password:", repr(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=access_token_expires,
        )

        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException:
        # lempar ulang biar status code & pesan tetap
        raise
    except Exception as e:
        # kalau ada error lain, keliatan di log Railway
        print("LOGIN ERROR:", repr(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal auth error",
        )



def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user