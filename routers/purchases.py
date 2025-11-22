from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from decimal import Decimal

import models, schemas
from db import get_db
from routers.auth import get_current_user

router = APIRouter(
    prefix="/purchases",
    tags=["purchases"],
)


@router.post("/", response_model=schemas.PurchaseOut, status_code=201)
def create_purchase(
    payload: schemas.PurchaseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Purchase items cannot be empty")

    # Hitung subtotal & total
    total_amount = Decimal("0")
    item_rows = []

    for item in payload.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product id {item.product_id} not found")

        subtotal = (item.qty * item.unit_cost) - item.discount
        total_amount += subtotal

        item_rows.append({
            "product": product,
            "qty": item.qty,
            "unit_cost": item.unit_cost,
            "discount": item.discount,
            "subtotal": subtotal,
        })

    purchase = models.PurchaseOrder(
        supplier_id=payload.supplier_id,
        supplier_name=payload.supplier_name,
        invoice_number=payload.invoice_number,
        purchase_date=payload.purchase_date,
        total_amount=total_amount,
        payment_method=payload.payment_method,
        notes=payload.notes,
    )
    db.add(purchase)
    db.flush()  # supaya purchase.id terisi

    # Insert items + update stok + stock movements
    for row in item_rows:
        product = row["product"]
        qty = row["qty"]

        item = models.PurchaseOrderItem(
            purchase_order_id=purchase.id,
            product_id=product.id,
            qty=qty,
            unit_cost=row["unit_cost"],
            discount=row["discount"],
            subtotal=row["subtotal"],
        )
        db.add(item)

        # update stok
        stock_before = product.stock_qty or 0
        stock_after = stock_before + qty
        product.stock_qty = stock_after

        movement = models.StockMovement(
            product_id=product.id,
            type="IN",
            ref_type="PURCHASE",
            ref_id=purchase.id,
            qty_change=qty,
            stock_before=stock_before,
            stock_after=stock_after,
            notes=f"Purchase #{purchase.id} {payload.invoice_number or ''}",
        )
        db.add(movement)

    # catat ke cash ledger (OUT)
    ledger = models.CashLedger(
        type="OUT",
        source="PURCHASE",
        ref_id=purchase.id,
        amount=total_amount,
        notes=f"Purchase {payload.supplier_name or ''} {payload.invoice_number or ''}",
    )
    db.add(ledger)

    db.commit()
    db.refresh(purchase)
    
    for item in purchase.items:
        item.product_name = item.product.name
    
    return purchase


@router.get("/", response_model=list[schemas.PurchaseOut])
def list_purchases(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    purchases = db.query(models.PurchaseOrder).order_by(models.PurchaseOrder.purchase_date.desc()).all()
    
    for p in purchases:
        for item in p.items:
            item.product_name = item.product.name

    return purchases
