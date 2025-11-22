from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models, schemas
from db import get_db
from routers.auth import get_current_user

router = APIRouter(
    prefix="/suppliers",
    tags=["suppliers"],
)

@router.post("/", response_model=schemas.SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: schemas.SupplierCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Cek nama unik
    existing = db.query(models.Supplier).filter(models.Supplier.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Supplier name already exists")

    supplier = models.Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/", response_model=list[schemas.SupplierOut])
def list_suppliers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    suppliers = db.query(models.Supplier).order_by(models.Supplier.name).all()
    return suppliers
