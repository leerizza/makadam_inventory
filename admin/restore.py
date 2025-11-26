@router.post("/restore", status_code=status.HTTP_200_OK)
def restore_data(
    payload: BackupPayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Restore data dari file backup JSON.

    STRATEGI:
    - Hanya boleh diakses admin.
    - Di-wrap dalam transaction, kalau error → rollback.
    - Saat ini:
        - wipe & restore: products, customers, suppliers, expenses, recipes.
        - sales & purchases disiapkan placeholder (TODO).
    """
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya admin yang boleh melakukan restore.",
        )

    try:
        # Transaction scope
        # SQLAlchemy 1.4+: gunakan begin()
        with db.begin():
            # 1. Restore master data dulu
            if payload.products:
                _restore_products(db, payload.products)

            if payload.customers:
                _restore_customers(db, payload.customers)

            if payload.suppliers:
                _restore_suppliers(db, payload.suppliers)

            if payload.expenses:
                _restore_expenses(db, payload.expenses)

            # 2. Restore recipes (BOM)
            if payload.recipes:
                _restore_recipes(db, payload.recipes)

            # 3. Placeholder: sales & purchases
            #
            # Karena schema Sales & Purchase biasanya punya relasi
            # (misal SaleItem, PurchaseItem) & nested items di response,
            # restore-nya perlu penanganan khusus.
            # Di sini aku kasih skeleton-nya saja:
            #
            # if payload.sales:
            #     _restore_sales(db, payload.sales)
            #
            # if payload.purchases:
            #     _restore_purchases(db, payload.purchases)

            # NOTE:
            # Kalau kamu punya model Sales, SaleItem, Purchase, PurchaseItem,
            # nanti kita bisa tuliskan _restore_sales dan _restore_purchases khusus
            # yang:
            # - insert parent dulu (Sales/Purchase),
            # - lalu insert items-nya dengan FK ke parent.id.

        # Kalau semua ok, commit otomatis oleh context manager db.begin()
        return {
            "status": "ok",
            "message": "Restore berhasil dijalankan.",
            "meta": payload.meta.model_dump() if payload.meta else None,
        }

    except Exception as e:
        # Kalau ada exception, transaction otomatis di-rollback oleh db.begin()
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi error saat restore: {e}",
        )
