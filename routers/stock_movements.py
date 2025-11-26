from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

import models, schemas
from db import get_db
from routers.auth import get_current_user

router = APIRouter(
    prefix="/stock-movements",
    tags=["stock-movements"],
)

@router.get("/", response_model=list[schemas.StockMovementOut])
def list_stock_movements(
    product_id: Optional[int] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.StockMovement).order_by(models.StockMovement.movement_date.desc())

    if product_id:
        q = q.filter(models.StockMovement.product_id == product_id)

    rows = q.limit(limit).all()

    for row in rows:
        row.product_name = row.product.name if row.product else None

    return rows
