# routers/admin_restore.py
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
import models, schemas
from routers.auth import get_current_user


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


# ===============================
#   BACKUP PAYLOAD SCHEMA
# ===============================

class BackupMeta(BaseModel):
    generated_at: Optional[datetime] = None
    app: Optional[str] = None
    version: Optional[str] = None


class BackupPayload(BaseModel):
    meta: Optional[BackupMeta] = None

    products: List[schemas.ProductOut] = []
    customers: List[schemas.CustomerOut] = []
    suppliers: List[schemas.SupplierOut] = []
    expenses: List[schemas.ExpenseOut] = []

    sales: List[dict] = []
    purchases: List[dict] = []

    # recipes = { product_id: [RecipeComponentOut], ... }
    recipes: Dict[int, List[schemas.RecipeComponentOut]] = {}


# ===============================
#   HELPERS RESTORE
# ===============================

def _wipe_table(db: Session, model):
    db.query(model).delete()


def _restore_products(db: Session, products: List[schemas.ProductOut]):
    _wipe_table(db, models.Product)
    for p in products:
        obj = models.Product(**p.model_dump())
        db.add(obj)


def _restore_customers(db: Session, customers: List[schemas.CustomerOut]):
    _wipe_table(db, models.Customer)
    for c in customers:
        obj = models.Customer(**c.model_dump())
        db.add(obj)


def _restore_suppliers(db: Session, suppliers: List[schemas.SupplierOut]):
    _wipe_table(db, models.Supplier)
    for s in suppliers:
        obj = models.Supplier(**s.model_dump())
        db.add(obj)


def _restore_expenses(db: Session, expenses: List[schemas.ExpenseOut]):
    _wipe_table(db, models.Expense)
    for e in expenses:
        obj = models.Expense(**e.model_dump())
        db.add(obj)


def _restore_recipes(db: Session, recipes_by_product: Dict[int, List[schemas.RecipeComponentOut]]):
    _wipe_table(db, models.ProductRecipe)

    for product_id, components in recipes_by_product.items():
        for rc in components:
            data = rc.model_dump()
            obj = models.ProductRecipe(
                id=data.get("id"),
                product_id=data["product_id"],
                component_product_id=data["component_product_id"],
                qty_per_unit=data["qty_per_unit"],
            )
            db.add(obj)


# ===============================
#   ENDPOINT RESTORE
# ===============================

@router.post("/restore", status_code=status.HTTP_200_OK)
def restore_data(
    payload: BackupPayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Hanya admin yang boleh melakukan restore."
        )

    try:
        with db.begin():
            # MASTER
            if payload.products:
                _restore_products(db, payload.products)

            if payload.customers:
                _restore_customers(db, payload.customers)

            if payload.suppliers:
                _restore_suppliers(db, payload.suppliers)

            if payload.expenses:
                _restore_expenses(db, payload.expenses)

            # RECIPES (BOM)
            if payload.recipes:
                _restore_recipes(db, payload.recipes)

            # TRANSACTIONS (optional, belum diimplementasi)
            # TODO: restore sales & purchases kalau diperlukan
            # if payload.sales: ...
            # if payload.purchases: ...

        return {
            "status": "ok",
            "message": "Restore berhasil diproses.",
            "meta": payload.meta.model_dump() if payload.meta else None,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Restore gagal: {e}"
        )
