from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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
