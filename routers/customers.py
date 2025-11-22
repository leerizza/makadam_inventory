# routers/customers.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from db import get_db
import models, schemas
from routers.auth import get_current_user

router = APIRouter(
    prefix="/customers",
    tags=["Customers"],
)


@router.post("/", response_model=schemas.CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: schemas.CustomerCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    customer = models.Customer(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        source_channel=payload.source_channel,
        notes=payload.notes,
        is_active=payload.is_active,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/", response_model=list[schemas.CustomerOut])
def list_customers(
    q: str | None = Query(None, description="Search by name/phone/email"),
    only_active: bool = Query(True, description="Hanya tampilkan yang aktif"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(models.Customer)

    if only_active:
        query = query.filter(models.Customer.is_active == True)

    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Customer.name.ilike(like))
            | (models.Customer.phone.ilike(like))
            | (models.Customer.email.ilike(like))
        )

    return query.order_by(models.Customer.name.asc()).all()


@router.get("/{customer_id}", response_model=schemas.CustomerOut)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=schemas.CustomerOut)
def update_customer(
    customer_id: int,
    payload: schemas.CustomerUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(customer, k, v)

    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int,
    soft_delete: bool = Query(True, description="Jika True: set is_active=False saja"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if soft_delete:
        customer.is_active = False
        db.commit()
    else:
        db.delete(customer)
        db.commit()
    return
