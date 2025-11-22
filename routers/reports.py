# routers/reports.py
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from db import get_db
import models
from routers.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])


def _parse_date_param(param: str | None, name: str) -> date | None:
    if not param:
        return None
    try:
        return date.fromisoformat(param)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {name} format, gunakan YYYY-MM-DD",
        )


@router.get("/daily")
def daily_report(
    target_date: str = Query(..., description="Tanggal laporan, format YYYY-MM-DD"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Laporan keuangan harian dari CashLedger:
    - total penjualan
    - total pembelian
    - total pengeluaran lain
    - net income hari itu
    """
    d = _parse_date_param(target_date, "target_date")

    # pakai func.date(entry_date) == d
    ledger = models.CashLedger
    day_filter = func.date(ledger.entry_date) == d

    def _sum_amount(_type: str | None = None, _source: str | None = None) -> Decimal:
        q = db.query(func.coalesce(func.sum(ledger.amount), 0)).filter(day_filter)
        if _type:
            q = q.filter(ledger.type == _type)
        if _source:
            q = q.filter(ledger.source == _source)
        return q.scalar() or Decimal("0")

    total_sales = _sum_amount("IN", "SALE")
    total_purchase = _sum_amount("OUT", "PURCHASE")
    total_expense = _sum_amount("OUT", "EXPENSE")
    total_other_income = _sum_amount("IN", "OTHER")
    total_other_out = _sum_amount("OUT", "OTHER")

    net_income = total_sales + total_other_income - total_purchase - total_expense - total_other_out

    return {
        "date": str(d),
        "summary": {
            "total_sales": float(total_sales),
            "total_purchase": float(total_purchase),
            "total_expense": float(total_expense),
            "total_other_income": float(total_other_income),
            "total_other_out": float(total_other_out),
            "net_income": float(net_income),
        },
    }


@router.get("/range")
def range_report(
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD (inclusive)"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Laporan keuangan untuk rentang tanggal (harian/mingguan/bulanan tergantung input).
    Hitung total per tipe, plus net income.
    """
    start = _parse_date_param(start_date, "start_date")
    end = _parse_date_param(end_date, "end_date")

    if start > end:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")

    ledger = models.CashLedger
    date_filter = func.date(ledger.entry_date).between(start, end)

    def _sum_amount(_type: str | None = None, _source: str | None = None) -> Decimal:
        q = db.query(func.coalesce(func.sum(ledger.amount), 0)).filter(date_filter)
        if _type:
            q = q.filter(ledger.type == _type)
        if _source:
            q = q.filter(ledger.source == _source)
        return q.scalar() or Decimal("0")

    total_sales = _sum_amount("IN", "SALE")
    total_purchase = _sum_amount("OUT", "PURCHASE")
    total_expense = _sum_amount("OUT", "EXPENSE")
    total_other_income = _sum_amount("IN", "OTHER")
    total_other_out = _sum_amount("OUT", "OTHER")

    net_income = total_sales + total_other_income - total_purchase - total_expense - total_other_out

    return {
        "start_date": str(start),
        "end_date": str(end),
        "summary": {
            "total_sales": float(total_sales),
            "total_purchase": float(total_purchase),
            "total_expense": float(total_expense),
            "total_other_income": float(total_other_income),
            "total_other_out": float(total_other_out),
            "net_income": float(net_income),
        },
    }

@router.get("/customers-by-channel")
def customers_by_channel(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Summary jumlah customer per source_channel.
    Bisa dipakai untuk lihat channel mana paling banyak bawa customer.
    """
    rows = (
        db.query(
            models.Customer.source_channel,
            func.count(models.Customer.id).label("total_customers"),
        )
        .filter(models.Customer.is_active == True)
        .group_by(models.Customer.source_channel)
        .order_by(func.count(models.Customer.id).desc())
        .all()
    )

    result = []
    for source_channel, total in rows:
        result.append(
            {
                "source_channel": source_channel or "UNKNOWN",
                "total_customers": int(total),
            }
        )

    return result

