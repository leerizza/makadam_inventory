# routers/purchases.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from decimal import Decimal
from typing import Optional
from datetime import date

import models, schemas
from db import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/purchases", tags=["Purchases"])


# =========================================================
# CREATE PURCHASE (WITH ACCOUNTING LOGIC)
# =========================================================
@router.post("/", response_model=schemas.PurchaseOut, status_code=201)
def create_purchase(
    payload: schemas.PurchaseCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Purchase items cannot be empty")

    # ===========================
    # VALIDATE SOURCE ACCOUNT
    # ===========================
    account = None
    if payload.payment_method in ("CASH", "TRANSFER"):
        if not payload.source_account_id:
            raise HTTPException(
                status_code=400,
                detail="source_account_id is required for CASH / TRANSFER payments",
            )

        account = db.query(models.Account).get(payload.source_account_id)
        if not account:
            raise HTTPException(status_code=400, detail="Source account not found")

    # ===========================
    # CALCULATE TOTAL
    # ===========================
    total_amount = Decimal("0")
    item_rows = []

    for item in payload.items:
        product = (
            db.query(models.Product)
            .filter(models.Product.id == item.product_id)
            .first()
        )
        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product id {item.product_id} not found",
            )

        qty = Decimal(str(item.qty))
        unit_cost = Decimal(str(item.unit_cost))
        discount = Decimal(str(item.discount or 0))

        subtotal = (qty * unit_cost) - discount
        total_amount += subtotal

        item_rows.append(
            {
                "product": product,
                "qty": qty,
                "unit_cost": unit_cost,
                "discount": discount,
                "subtotal": subtotal,
                "plan_item_id": getattr(item, "plan_item_id", None),
            }
        )

    # ===========================
    # SAFETY: CHECK ACCOUNT BALANCE
    # ===========================
    if account:
        if (account.current_balance or Decimal("0")) < total_amount:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient account balance. Needed {total_amount}, "
                    f"available {account.current_balance}"
                ),
            )

    # ===========================
    # INSERT PURCHASE HEADER
    # ===========================
    purchase = models.PurchaseOrder(
        supplier_id=payload.supplier_id,
        supplier_name=payload.supplier_name,
        invoice_number=payload.invoice_number,
        purchase_date=payload.purchase_date,
        total_amount=total_amount,
        payment_method=payload.payment_method,
        notes=payload.notes,
        source_account_id=payload.source_account_id,
    )
    db.add(purchase)
    db.flush()  # supaya purchase.id terisi

    # ===========================
    # PROCESS ITEMS + STOCK UPDATE
    # ===========================
    affected_plans: set[int] = set()

    for row in item_rows:
        product = row["product"]
        qty = row["qty"]
        plan_item_id = row["plan_item_id"]

        # Detail purchase item
        item = models.PurchaseOrderItem(
            purchase_order_id=purchase.id,
            product_id=product.id,
            qty=qty,
            unit_cost=row["unit_cost"],
            discount=row["discount"],
            subtotal=row["subtotal"],
        )
        db.add(item)

        # Update stok produk (IN)
        stock_before = Decimal(str(product.stock_qty or 0))
        stock_after = stock_before + qty
        product.stock_qty = stock_after

        db.add(
            models.StockMovement(
                product_id=product.id,
                type="IN",
                ref_type="PURCHASE",
                ref_id=purchase.id,
                qty_change=qty,
                stock_before=stock_before,
                stock_after=stock_after,
                notes=f"Purchase #{purchase.id} {payload.invoice_number or ''}",
            )
        )

        # Kalau item ini terhubung dengan PurchasePlanItem, update received_qty
        if plan_item_id:
            plan_item = (
                db.query(models.PurchasePlanItem)
                .filter(models.PurchasePlanItem.id == plan_item_id)
                .with_for_update()
                .first()
            )
            if not plan_item:
                raise HTTPException(
                    status_code=404,
                    detail=f"Purchase plan item id {plan_item_id} not found",
                )

            current_received = Decimal(str(plan_item.received_qty or 0))
            new_received = current_received + qty
            planned = Decimal(str(plan_item.planned_qty))

            if new_received > planned:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Received qty for product {product.name} would exceed "
                        f"planned qty ({planned}). "
                        f"Current received: {plan_item.received_qty}, "
                        f"new receive: {qty}"
                    ),
                )

            plan_item.received_qty = new_received
            affected_plans.add(plan_item.plan_id)

    # ===========================
    # UPDATE STATUS PURCHASE PLANS
    # ===========================
    for plan_id in affected_plans:
        plan = (
            db.query(models.PurchasePlan)
            .filter(models.PurchasePlan.id == plan_id)
            .with_for_update()
            .first()
        )
        if not plan:
            continue

        all_items = plan.items
        if all((item.received_qty or 0) >= item.planned_qty for item in all_items):
            plan.status = "COMPLETED"
        elif any((item.received_qty or 0) > 0 for item in all_items):
            plan.status = "PARTIAL"
        else:
            plan.status = "OPEN"

    # ===========================
    # UPDATE ACCOUNT BALANCE (OUT)
    # ===========================
    if account:
        account.current_balance = (account.current_balance or Decimal("0")) - total_amount

    # ===========================
    # CASH LEDGER
    # ===========================
    if payload.payment_method in ("CASH", "TRANSFER"):
        ledger = models.CashLedger(
            type="OUT",
            source="PURCHASE",
            ref_id=purchase.id,
            amount=total_amount,
            notes=f"Purchase {payload.supplier_name or ''} {payload.invoice_number or ''}".strip(),
        )
        db.add(ledger)

    db.commit()
    db.refresh(purchase)

    # isi product_name untuk schema PurchaseItemOut
    for item in purchase.items:
        if item.product:
            item.product_name = item.product.name

    return purchase


# =========================================================
# SIMPLE LIST (backward compatible)
# =========================================================
@router.get("/", response_model=list[schemas.PurchaseOut])
def list_purchases(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    purchases = (
        db.query(models.PurchaseOrder)
        .options(
            joinedload(models.PurchaseOrder.items).joinedload(models.PurchaseOrderItem.product),
            joinedload(models.PurchaseOrder.source_account),  # ⬅️ ini doang tambahan penting
        )
        .order_by(models.PurchaseOrder.purchase_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    for purchase in purchases:
        for item in purchase.items:
            if item.product:
                item.product_name = item.product.name

    return purchases


# =========================================================
# RECEIPTS ENDPOINTS (dipakai UI tab Penerimaan)
# =========================================================
@router.get("/receipts", response_model=list[schemas.PurchaseOut])
def get_purchase_receipts(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
    supplier_name: Optional[str] = None,
    invoice_number: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    """
    List purchase receipts dengan filter supplier, invoice, dan periode tanggal.
    Dipakai UI baru (tab Penerimaan).
    """
    query = db.query(models.PurchaseOrder)

    if supplier_name:
        query = query.filter(
            models.PurchaseOrder.supplier_name.ilike(f"%{supplier_name}%")
        )
    if invoice_number:
        query = query.filter(
            models.PurchaseOrder.invoice_number.ilike(f"%{invoice_number}%")
        )
    if date_from:
        query = query.filter(models.PurchaseOrder.purchase_date >= date_from)
    if date_to:
        query = query.filter(models.PurchaseOrder.purchase_date <= date_to)

    purchases = (
        query.order_by(models.PurchaseOrder.purchase_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    for purchase in purchases:
        for item in purchase.items:
            if item.product:
                item.product_name = item.product.name

    return purchases


@router.get("/receipts/{purchase_id}", response_model=schemas.PurchaseOut)
def get_purchase_receipt_by_id(
    purchase_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get single purchase receipt by ID
    """
    purchase = (
        db.query(models.PurchaseOrder)
        .filter(models.PurchaseOrder.id == purchase_id)
        .first()
    )

    if not purchase:
        raise HTTPException(
            status_code=404,
            detail=f"Purchase order #{purchase_id} not found",
        )

    for item in purchase.items:
        if item.product:
            item.product_name = item.product.name

    return purchase
