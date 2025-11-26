# routers/accounts.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import get_db
import models, schemas

router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"],
)

@router.get("/", response_model=list[schemas.AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    """
    List semua rekening (accounts) yang aktif.
    """
    accounts = (
        db.query(models.Account)
        .filter(models.Account.is_active == True)
        .order_by(models.Account.name.asc())
        .all()
    )
    return accounts


@router.post("/", response_model=schemas.AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(payload: schemas.AccountCreate, db: Session = Depends(get_db)):
    """
    Tambah rekening baru.
    """
    acc = models.Account(
        name=payload.name,
        type=payload.type,
        number=payload.number,
        current_balance=payload.current_balance or 0,
        is_active=True,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc
