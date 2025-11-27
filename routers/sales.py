from datetime import date
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from db import get_db
import models, schemas
from routers.auth import get_current_user

router = APIRouter(prefix="/sales", tags=["Sales"])


# =====================================================
# Helper: Auto-build INTERNAL product using its recipe
# =====================================================
def auto_build_from_recipe(db: Session, product: models.Product, qty_needed: Decimal) -> int:
    """
    Try building INTERNAL product using recipe (RAW components).
    Returns how many INTERNAL units were successfully built.
    """
    recipe_rows = (
        db.query(models.ProductRecipe)
        .filter(models.ProductRecipe.product_id == product.id)
        .all()
    )

    if not recipe_rows:
        return 0  # cannot build anything

    possible_counts = []
    for rc in recipe_rows:
        comp = (
            db.query(models.Product)
            .filter(models.Product.id == rc.component_product_id)
            .with_for_update()
            .first()
        )
        if not comp or comp.stock_qty is None or comp.stock_qty <= 0:
            return 0

        max_units = float(comp.stock_qty) / float(rc.qty_per_unit)
        possible_counts.append(max_units)

    max_can_build = int(min(possible_counts)) if possible_counts else 0
    if max_can_build <= 0:
        return 0

    build_qty = min(int(qty_needed), max_can_build)

    # Consume RAW
    for rc in recipe_rows:
        comp = (
            db.query(models.Product)
            .filter(models.Product.id == rc.component_product_id)
            .with_for_update()
            .first()
        )
        needed = float(rc.qty_per_unit) * float(build_qty)

        before = comp.stock_qty
        after = before - needed
        comp.stock_qty = after

        db.add(
            models.StockMovement(
                product_id=comp.id,
                type="OUT",
                ref_type="BUILD",
                qty_change=needed,
                stock_before=before,
                stock_after=after,
                notes=f"Auto-build {build_qty} {product.name}",
            )
        )

    # Add stock of INTERNAL product
    before = product.stock_qty or 0
    after = before + build_qty
    product.stock_qty = after

    db.add(
        models.StockMovement(
            product_id=product.id,
            type="IN",
            ref_type="BUILD",
            qty_change=build_qty,
            stock_before=before,
            stock_after=after,
            notes="Auto-build from recipe",
        )
    )

    return build_qty


# =====================================================
# CREATE SALE (stok, rekening, ledger)
# =====================================================
@router.post("/", response_model=schemas.SalesOut, status_code=status.HTTP_201_CREATED)
def create_sale(
    payload: schemas.SalesCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="No items in sale")

    # -----------------------------
    # CUSTOMER HANDLING
    # -----------------------------
    customer_id = payload.customer_id
    customer = None

    if customer_id:
        customer = (
            db.query(models.Customer)
            .filter(models.Customer.id == customer_id)
            .first()
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
    else:
        if not payload.customer_name:
            raise HTTPException(
                status_code=400,
                detail="customer_name required if customer_id not provided",
            )

        existing = (
            db.query(models.Customer)
            .filter(models.Customer.name == payload.customer_name)
            .first()
        )
        if existing:
            customer = existing
        else:
            customer = models.Customer(
                name=payload.customer_name,
                phone=payload.customer_phone,
                email=payload.customer_email,
            )
            db.add(customer)
            db.flush()

        customer_id = customer.id

    customer_name = customer.name if customer else payload.customer_name

    # -----------------------------
    # VALIDATE / GET ACCOUNT (IN)
    # -----------------------------
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

    # -----------------------------
    # CALCULATE TOTAL
    # -----------------------------
    total_amount = Decimal("0")
    for item in payload.items:
        qty = Decimal(str(item.qty))
        unit_price = Decimal(str(item.unit_price))
        discount = Decimal(str(item.discount or 0))
        total_amount += (qty * unit_price) - discount

    # -----------------------------
    # CREATE HEADER
    # -----------------------------
    sale = models.SalesOrder(
        customer_id=customer_id,
        customer_name=customer_name,
        order_date=payload.order_date or date.today(),
        payment_method=payload.payment_method,
        total_amount=total_amount,
        status="PAID",
        notes=payload.notes,
        source_account_id=payload.source_account_id,
    )
    db.add(sale)
    db.flush()

    # -----------------------------
    # PROCESS EACH ITEM (STOCK)
    # -----------------------------
    for item in payload.items:
        qty = Decimal(str(item.qty))

        product = (
            db.query(models.Product)
            .filter(models.Product.id == item.product_id)
            .with_for_update()
            .first()
        )
        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {item.product_id} not found",
            )

        stock_before = Decimal(str(product.stock_qty or 0))

        # INTERNAL: boleh auto-build
        if product.product_type == "INTERNAL":
            if stock_before < qty:
                needed = qty - stock_before
                built = auto_build_from_recipe(db, product, needed)
                db.flush()
                stock_before = Decimal(str(product.stock_qty or 0))

        # Cek stok akhir
        if stock_before < qty:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient stock for {product.name}: "
                    f"available {stock_before}, requested {qty}"
                ),
            )

        stock_after = stock_before - qty
        product.stock_qty = stock_after

        unit_price = Decimal(str(item.unit_price))
        discount = Decimal(str(item.discount or 0))
        subtotal = (qty * unit_price) - discount

        db.add(
            models.SalesOrderItem(
                sales_order_id=sale.id,
                product_id=product.id,
                qty=qty,
                unit_price=unit_price,
                discount=discount,
                subtotal=subtotal,
            )
        )

        db.add(
            models.StockMovement(
                product_id=product.id,
                type="OUT",
                ref_type="SALE",
                ref_id=sale.id,
                qty_change=qty,
                stock_before=stock_before,
                stock_after=stock_after,
                notes=f"Sale to {customer_name}",
            )
        )

    # -----------------------------
    # UPDATE ACCOUNT BALANCE (IN)
    # -----------------------------
    if account:
        account.current_balance = (account.current_balance or Decimal("0")) + total_amount

    # -----------------------------
    # CASH LEDGER (IN)
    # -----------------------------
    if payload.payment_method in ("CASH", "TRANSFER"):
        db.add(
            models.CashLedger(
                type="IN",
                source="SALE",
                ref_id=sale.id,
                amount=total_amount,
                notes=f"Payment from {customer_name}",
            )
        )

    db.commit()
    db.refresh(sale)
    return sale


# =====================================================
# GET LIST SALES
# =====================================================
@router.get("/", response_model=List[schemas.SalesOut])
def list_sales(
    skip: int = 0,
    limit: int = 100,
    customer_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    q = (
        db.query(models.SalesOrder)
        .options(
            joinedload(models.SalesOrder.items).joinedload(models.SalesOrderItem.product),
            joinedload(models.SalesOrder.source_account),
        )
    )

    if customer_id:
        q = q.filter(models.SalesOrder.customer_id == customer_id)

    sales = (
        q.order_by(models.SalesOrder.order_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # isi product_name agar terbaca di schema
    for sale in sales:
        for item in sale.items:
            if item.product:
                item.product_name = item.product.name

    return sales


# =====================================================
# GET SINGLE SALE (FIXED - No duplicate)
# =====================================================
@router.get("/{sale_id}", response_model=schemas.SalesOut)
def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get single sale by ID"""
    sale = (
        db.query(models.SalesOrder)
        .options(
            joinedload(models.SalesOrder.items).joinedload(models.SalesOrderItem.product),
            joinedload(models.SalesOrder.source_account),
        )
        .filter(models.SalesOrder.id == sale_id)
        .first()
    )
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    for item in sale.items:
        if item.product:
            item.product_name = item.product.name

    return sale