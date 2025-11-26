from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from decimal import Decimal

import models, schemas
from db import get_db
from routers.auth import get_current_user

router = APIRouter(
    prefix="/recipes",
    tags=["recipes"],
)

@router.post("/", response_model=schemas.RecipeComponentOut, status_code=status.HTTP_201_CREATED)
def add_recipe_component(
    payload: schemas.RecipeComponentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # cek product & component exist
    product = db.query(models.Product).filter(models.Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    component = db.query(models.Product).filter(models.Product.id == payload.component_product_id).first()
    if not component:
        raise HTTPException(status_code=404, detail="Component product not found")

    # optional: batasi product INTERNAL, component RAW
    if product.product_type != "INTERNAL":
        raise HTTPException(status_code=400, detail="Recipe hanya untuk product_type INTERNAL")
    
    # bikin recipe row
    rc = models.ProductRecipe(
        product_id=payload.product_id,
        component_product_id=payload.component_product_id,
        qty_per_unit=payload.qty_per_unit,
    )
    db.add(rc)
    db.commit()
    db.refresh(rc)
    return rc


@router.get("/{product_id}", response_model=list[schemas.RecipeComponentOut])
def get_recipe(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.ProductRecipe)
        .filter(models.ProductRecipe.product_id == product_id)
        .all()
    )
    return rows



@router.post("/build", response_model=schemas.BuildFromRecipeOut, status_code=status.HTTP_201_CREATED)
def build_from_recipe(
    payload: schemas.BuildFromRecipeIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1. Ambil product INTERNAL yang mau diproduksi
    product = db.query(models.Product).filter(models.Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if product.product_type != "INTERNAL":
        raise HTTPException(status_code=400, detail="Build hanya untuk product_type INTERNAL")

    if payload.qty_to_build <= 0:
        raise HTTPException(status_code=400, detail="qty_to_build harus > 0")

    # 2. Ambil recipe (komponen RAW)
    recipe_rows = (
        db.query(models.ProductRecipe)
        .filter(models.ProductRecipe.product_id == product.id)
        .all()
    )

    if not recipe_rows:
        raise HTTPException(status_code=400, detail="Produk ini belum punya recipe/BOM")

    # 3. Hitung kebutuhan masing-masing komponen
    required_components = []  # list dict
    for rc in recipe_rows:
        component = db.query(models.Product).filter(models.Product.id == rc.component_product_id).first()
        if not component:
            raise HTTPException(status_code=404, detail=f"Component product id {rc.component_product_id} not found")

        needed_qty = (rc.qty_per_unit * payload.qty_to_build)

        stock_before = component.stock_qty or Decimal("0")

        if stock_before < needed_qty:
            raise HTTPException(
                status_code=400,
                detail=f"Stok tidak cukup untuk komponen {component.name}: butuh {needed_qty}, stok {stock_before}",
            )

        required_components.append({
            "component": component,
            "needed_qty": needed_qty,
            "stock_before": stock_before,
        })

    # 4. Kalau semua cukup → eksekusi konsumsi komponen + tambah stok produk jadi
    component_usages = []

    for row in required_components:
        component = row["component"]
        needed_qty = row["needed_qty"]
        stock_before = row["stock_before"]
        stock_after = stock_before - needed_qty

        # update stok komponen
        component.stock_qty = stock_after

        # catat stock movement OUT
        mv = models.StockMovement(
            product_id=component.id,
            type="OUT",
            ref_type="PRODUCTION",
            ref_id=None,  # kalau nanti punya tabel ProductionOrder, bisa diisi
            qty_change=needed_qty,
            stock_before=stock_before,
            stock_after=stock_after,
            notes=f"Build {payload.qty_to_build} {product.name} (BOM)",
        )
        db.add(mv)

        component_usages.append(
            schemas.BuildFromRecipeComponentUsage(
                product_id=component.id,
                product_name=component.name,
                qty_used=needed_qty,
                stock_before=stock_before,
                stock_after=stock_after,
            )
        )

    # 5. Tambah stok produk jadi
    prod_stock_before = product.stock_qty or Decimal("0")
    prod_stock_after = prod_stock_before + payload.qty_to_build
    product.stock_qty = prod_stock_after

    mv_prod = models.StockMovement(
        product_id=product.id,
        type="IN",
        ref_type="PRODUCTION",
        ref_id=None,
        qty_change=payload.qty_to_build,
        stock_before=prod_stock_before,
        stock_after=prod_stock_after,
        notes="Build from recipe",
    )
    db.add(mv_prod)

    db.commit()
    db.refresh(product)

    return schemas.BuildFromRecipeOut(
        product_id=product.id,
        product_name=product.name,
        qty_built=payload.qty_to_build,
        stock_before=prod_stock_before,
        stock_after=prod_stock_after,
        components=component_usages,
    )
