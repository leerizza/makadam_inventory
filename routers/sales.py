# routers/sales.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from typing import Optional

from db import get_db
import models, schemas
from routers.auth import get_current_user

router = APIRouter(prefix="/sales", tags=["Sales"])


@router.post("/", response_model=schemas.SalesOut, status_code=201)
def create_sale(
    payload: schemas.SalesCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Create new sales order with customer tracking and automatic stock deduction.
    Supports both final products (INTERNAL) and raw material consumption via recipes.
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="No items in sale")

    # =========================
    # Handle Customer: Auto-create or use existing
    # =========================
    customer_id = payload.customer_id
    
    if customer_id:
        # Validasi customer yang sudah ada
        customer = db.query(models.Customer).filter(
            models.Customer.id == customer_id
        ).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        customer_name = customer.name
    else:
        # Auto-create customer baru jika belum ada
        if not payload.customer_name:
            raise HTTPException(
                status_code=400, 
                detail="customer_name is required when customer_id is not provided"
            )
        
        # Cek apakah customer dengan nama ini sudah ada
        existing_customer = db.query(models.Customer).filter(
            models.Customer.name == payload.customer_name
        ).first()
        
        if existing_customer:
            customer = existing_customer
            customer_id = existing_customer.id
        else:
            # Buat customer baru
            customer = models.Customer(
                name=payload.customer_name,
                phone=payload.customer_phone,
                email=payload.customer_email,
            )
            db.add(customer)
            db.flush()
            customer_id = customer.id
        
        customer_name = customer.name

    # =========================
    # Hitung total penjualan (pakai Decimal)
    # =========================
    total_amount = Decimal("0")
    for item in payload.items:
        qty = Decimal(str(item.qty))
        unit_price = Decimal(str(item.unit_price))
        discount = Decimal(str(item.discount))

        line_subtotal = (unit_price * qty) - discount
        total_amount += line_subtotal

    # =========================
    # Buat header SalesOrder dengan customer_id
    # =========================
    sale = models.SalesOrder(
        customer_id=customer_id,  # ✅ Selalu terisi
        customer_name=customer_name,
        payment_method=payload.payment_method,
        total_amount=total_amount,
        status="PAID",
        notes=payload.notes,
    )
    db.add(sale)
    db.flush()  # supaya sale.id terisi

    # =========================
    # Proses tiap item penjualan
    # =========================
    for item in payload.items:
        qty = Decimal(str(item.qty))
        unit_price = Decimal(str(item.unit_price))
        discount = Decimal(str(item.discount))

        # Lock product untuk update stok
        product = (
            db.query(models.Product)
            .filter(models.Product.id == item.product_id)
            .with_for_update()
            .first()
        )
        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product id {item.product_id} not found",
            )

        # Batasi hanya INTERNAL yang boleh dijual
        if product.product_type != "INTERNAL":
            raise HTTPException(
                status_code=400,
                detail=f"Product {product.name} is not for sale (type={product.product_type})",
            )

        # Validasi stok produk final
        stock_before = product.stock_qty or Decimal("0")
        if stock_before < qty:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {product.name}. "
                       f"Available: {stock_before}, requested: {qty}",
            )

        # Kurangi stok produk final
        product.stock_qty = stock_before - qty
        stock_after = product.stock_qty

        # Simpan detail item penjualan
        line_subtotal = (unit_price * qty) - discount
        line = models.SalesOrderItem(
            sales_order_id=sale.id,
            product_id=item.product_id,
            qty=qty,
            unit_price=unit_price,
            discount=discount,
            subtotal=line_subtotal,
        )
        db.add(line)

        # Catat pergerakan stok produk final
        movement = models.StockMovement(
            product_id=item.product_id,
            type="OUT",
            ref_type="SALE",
            ref_id=sale.id,
            qty_change=-qty,
            stock_before=stock_before,
            stock_after=stock_after,
            notes=f"Sale to customer: {customer_name}",
        )
        db.add(movement)

        # =========================
        # 🔥 KURANGI STOK BAHAN BAKU BERDASARKAN RECIPE
        # =========================
        recipe_rows = (
            db.query(models.ProductRecipe)
            .filter(models.ProductRecipe.product_id == product.id)
            .all()
        )

        for rc in recipe_rows:
            # Lock component product
            component = (
                db.query(models.Product)
                .filter(models.Product.id == rc.component_product_id)
                .with_for_update()
                .first()
            )
            if not component:
                raise HTTPException(
                    status_code=500,
                    detail=f"Component product id {rc.component_product_id} not found "
                           f"in recipe for {product.name}",
                )

            # Hitung kebutuhan bahan baku
            qty_per_unit = rc.qty_per_unit or Decimal("0")
            needed_qty = qty_per_unit * qty

            if needed_qty <= 0:
                continue

            # Validasi stok bahan baku
            component_stock_before = component.stock_qty or Decimal("0")
            if component_stock_before < needed_qty:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Insufficient raw material: {component.name}. "
                        f"Required: {needed_qty}, available: {component_stock_before}"
                    ),
                )

            # Kurangi stok bahan baku
            component.stock_qty = component_stock_before - needed_qty
            component_stock_after = component.stock_qty

            # Catat pergerakan stok bahan baku
            component_movement = models.StockMovement(
                product_id=component.id,
                type="OUT",
                ref_type="SALE",
                ref_id=sale.id,
                qty_change=-needed_qty,
                stock_before=component_stock_before,
                stock_after=component_stock_after,
                notes=f"Raw material consumption for {product.name} (customer: {customer_name})",
            )
            db.add(component_movement)

    # =========================
    # Buku kas (cash ledger)
    # =========================
    ledger = models.CashLedger(
        type="IN",
        source="SALE",
        ref_id=sale.id,
        amount=total_amount,
        notes=f"Sales payment from {customer_name} via {payload.payment_method}",
    )
    db.add(ledger)

    db.commit()
    db.refresh(sale)
    return sale


@router.get("/", response_model=list[schemas.SalesOut])
def list_sales(
    skip: int = 0,
    limit: int = 100,
    customer_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get all sales orders with optional customer filter"""
    query = db.query(models.SalesOrder)
    
    if customer_id:
        query = query.filter(models.SalesOrder.customer_id == customer_id)
    
    sales = query.order_by(models.SalesOrder.order_date.desc()).offset(skip).limit(limit).all()
    return sales


@router.get("/{sale_id}", response_model=schemas.SalesOut)
def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get sale order by ID with items"""
    sale = db.query(models.SalesOrder).filter(models.SalesOrder.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale