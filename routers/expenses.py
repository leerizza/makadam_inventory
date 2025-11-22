from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal

import models, schemas
from db import get_db
from routers.auth import get_current_user

router = APIRouter(
    prefix="/expenses",
    tags=["expenses"],
)


@router.post("/", response_model=schemas.ExpenseOut, status_code=201)
def create_expense(
    payload: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be > 0")

    expense = models.Expense(
        expense_date=payload.expense_date,
        category=payload.category,
        description=payload.description,
        amount=payload.amount,
        payment_method=payload.payment_method,
        notes=payload.notes,
    )
    db.add(expense)
    db.flush()

    # catat ke cash ledger (OUT)
    ledger = models.CashLedger(
        type="OUT",
        source="EXPENSE",
        ref_id=expense.id,
        amount=payload.amount,
        notes=f"Expense {payload.category}: {payload.description or ''}",
    )
    db.add(ledger)

    db.commit()
    db.refresh(expense)
    return expense


@router.get("/", response_model=list[schemas.ExpenseOut])
def list_expenses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    expenses = db.query(models.Expense).order_by(models.Expense.expense_date.desc()).all()
    return expenses
