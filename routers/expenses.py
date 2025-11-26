# routers/expenses.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from decimal import Decimal
from typing import Optional
from datetime import date

import models, schemas
from db import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/expenses", tags=["Expenses"])


# =====================================================
# CREATE EXPENSE (OUT)
# =====================================================
@router.post("/", response_model=schemas.ExpenseOut, status_code=201)
def create_expense(
    payload: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    amount = Decimal(str(payload.amount))

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be > 0")

    # -----------------------------
    # VALIDATE / GET ACCOUNT (OUT)
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

        if (account.current_balance or Decimal("0")) < amount:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient account balance. Needed {amount}, "
                    f"available {account.current_balance}"
                ),
            )

    # -----------------------------
    # CREATE EXPENSE ROW
    # -----------------------------
    expense = models.Expense(
        expense_date=payload.expense_date or date.today(),
        category=payload.category,
        description=payload.description,
        amount=amount,
        payment_method=payload.payment_method,
        notes=payload.notes,
        source_account_id=payload.source_account_id,
    )
    db.add(expense)
    db.flush()

    # -----------------------------
    # UPDATE ACCOUNT BALANCE (OUT)
    # -----------------------------
    if account:
        account.current_balance = (account.current_balance or Decimal("0")) - amount

    # -----------------------------
    # CASH LEDGER (OUT)
    # -----------------------------
    if payload.payment_method in ("CASH", "TRANSFER"):
        db.add(
            models.CashLedger(
                type="OUT",
                source="EXPENSE",
                ref_id=expense.id,
                amount=amount,
                notes=f"Expense {payload.category or ''} {payload.description or ''}".strip(),
            )
        )

    db.commit()
    db.refresh(expense)
    return expense


# =====================================================
# LIST EXPENSES
# =====================================================
@router.get("/", response_model=list[schemas.ExpenseOut])
def list_expenses(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
):
    # base query + load relasi akun
    q = (
        db.query(models.Expense)
        .options(joinedload(models.Expense.source_account))  # ⬅️ load account
    )

    if category:
        q = q.filter(models.Expense.category.ilike(f"%{category}%"))

    expenses = (
        q.order_by(models.Expense.expense_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return expenses



# =====================================================
# GET SINGLE EXPENSE
# =====================================================
@router.get("/{expense_id}", response_model=schemas.ExpenseOut)
def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    expense = (
        db.query(models.Expense)
        .filter(models.Expense.id == expense_id)
        .first()
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense
