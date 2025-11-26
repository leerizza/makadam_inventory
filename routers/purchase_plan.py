# routers/purchase_plans.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from decimal import Decimal

import models, schemas
from db import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/purchase-plans", tags=["Purchase Plans"])


@router.post("/", response_model=schemas.PurchasePlanOut, status_code=201)
def create_purchase_plan(
    payload: schemas.PurchasePlanCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Plan items cannot be empty")

    plan = models.PurchasePlan(
        supplier_id=payload.supplier_id,
        supplier_name=payload.supplier_name,
        target_date=payload.target_date,
        notes=payload.notes,
        status="OPEN",
    )
    db.add(plan)
    db.flush()

    for item in payload.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product id {item.product_id} not found")

        plan_item = models.PurchasePlanItem(
            plan_id=plan.id,
            product_id=item.product_id,
            planned_qty=item.planned_qty,
            received_qty=Decimal("0"),
        )
        db.add(plan_item)

    db.commit()
    db.refresh(plan)
    return plan


@router.get("/", response_model=list[schemas.PurchasePlanOut])
def list_purchase_plans(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    plans = (
        db.query(models.PurchasePlan)
        .order_by(models.PurchasePlan.created_at.desc())
        .all()
    )
    return plans


@router.get("/{plan_id}", response_model=schemas.PurchasePlanOut)
def get_purchase_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    plan = db.query(models.PurchasePlan).filter(models.PurchasePlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Purchase plan not found")
    return plan
