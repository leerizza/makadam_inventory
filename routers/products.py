# routers/products.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db
import models, schemas
from routers.auth import get_current_user

router = APIRouter(prefix="/products", tags=["Products"])


# ✅ Route spesifik HARUS di atas sebelum route dengan parameter dinamis
@router.get("/low-stock", response_model=List[schemas.ProductOut])
def get_low_stock_products(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Ambil list produk yang stoknya <= min_stock dan masih aktif.
    Cocok untuk notifikasi stok menipis di dashboard.
    """
    rows = (
        db.query(models.Product)
        .filter(
            models.Product.is_active == True,
            models.Product.min_stock.isnot(None),
            models.Product.stock_qty <= models.Product.min_stock,
        )
        .order_by(models.Product.stock_qty.asc())
        .all()
    )
    return rows


@router.get("/", response_model=List[schemas.ProductOut])
def list_products(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db), 
    user=Depends(get_current_user)
):
    """Get all products with pagination"""
    products = (
        db.query(models.Product)
        .order_by(models.Product.name)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return products


@router.post("/", response_model=schemas.ProductOut, status_code=201)
def create_product(
    payload: schemas.ProductCreate, 
    db: Session = Depends(get_db), 
    user=Depends(get_current_user)
):
    """Create new product"""
    existing = db.query(models.Product).filter(models.Product.sku == payload.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")

    product = models.Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


# ✅ Route dengan parameter dinamis HARUS di bawah setelah route spesifik
@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(
    product_id: int, 
    db: Session = Depends(get_db), 
    user=Depends(get_current_user)
):
    """Get product by ID"""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int, 
    payload: schemas.ProductUpdate, 
    db: Session = Depends(get_db), 
    user=Depends(get_current_user)
):
    """Update product by ID"""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Only update fields that are provided
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(product, k, v)

    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int, 
    db: Session = Depends(get_db), 
    user=Depends(get_current_user)
):
    """Delete product by ID"""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(product)
    db.commit()
    return None  # 204 No Content