# models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Numeric,
    DateTime,
    ForeignKey,
    Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import Base
from decimal import Decimal

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# class Product(Base):
#     __tablename__ = "products"

#     id = Column(Integer, primary_key=True, index=True)
#     sku = Column(String(100), unique=True, nullable=False, index=True)
#     name = Column(String(255), nullable=False)
#     category = Column(String(100))
#     unit = Column(String(50))
#     base_cost = Column(Numeric(18, 2), default=0)
#     sell_price = Column(Numeric(18, 2), default=0)
#     stock_qty = Column(Numeric(18, 2), default=0)
#     min_stock = Column(Numeric(18, 2), default=0)
#     is_active = Column(Boolean, default=True)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    number = Column(String, nullable=True)
    current_balance = Column(Numeric(18, 2), nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),   # <-- otomatis di-set tiap UPDATE lewat SQLAlchemy
        nullable=False,
    )
    expenses = relationship("Expense", back_populates="source_account")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100))
    unit = Column(String(50))
    product_type = Column(String(20), nullable=False, default="INTERNAL")  
    # pilihan: INTERNAL, RAW, SERVICE, dll

    base_cost = Column(Numeric(18, 2), default=0)
    sell_price = Column(Numeric(18, 2), default=0)
    stock_qty = Column(Numeric(18, 2), default=0)
    min_stock = Column(Numeric(18, 2), default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(255), nullable=True)
    order_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default="PAID")   # DRAFT, PAID, CANCELLED
    total_amount = Column(Numeric(18, 2), default=0)
    payment_method = Column(String(50), default="CASH")
    notes = Column(String)
    payment_method = Column(String, nullable=True)

    source_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    source_account = relationship("Account")     # ⬅️ relasi ke Account

    items = relationship("SalesOrderItem", back_populates="sale", cascade="all, delete-orphan")
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer = relationship("Customer", backref="sales_orders")



class SalesOrderItem(Base):
    __tablename__ = "sales_order_items"

    id = Column(Integer, primary_key=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    qty = Column(Numeric(18, 2), nullable=False)
    unit_price = Column(Numeric(18, 2), nullable=False)
    discount = Column(Numeric(18, 2), default=0)
    subtotal = Column(Numeric(18, 2), nullable=False)

    sale = relationship("SalesOrder", back_populates="items")
    product = relationship("Product")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    movement_date = Column(DateTime(timezone=True), server_default=func.now())
    type = Column(String(10), nullable=False)       # IN, OUT, ADJUST
    ref_type = Column(String(50))                   # SALE, PURCHASE, ADJUSTMENT, ...
    ref_id = Column(Integer)
    qty_change = Column(Numeric(18, 2), nullable=False)
    stock_before = Column(Numeric(18, 2))
    stock_after = Column(Numeric(18, 2))
    notes = Column(String)

    product = relationship("Product")


class CashLedger(Base):
    __tablename__ = "cash_ledger"

    id = Column(Integer, primary_key=True, index=True)
    entry_date = Column(DateTime(timezone=True), server_default=func.now())
    type = Column(String(10), nullable=False)        # IN, OUT
    source = Column(String(50), nullable=False)      # SALE, PURCHASE, EXPENSE
    ref_id = Column(Integer)
    amount = Column(Numeric(18, 2), nullable=False)
    notes = Column(String)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    source_channel = Column(String(50), nullable=True)  # contoh: "instagram", "tiktok", "website", "offline"

    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    contact = Column(String(255))
    phone = Column(String(50))
    address = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # relasi ke purchase orders
    purchases = relationship("PurchaseOrder", back_populates="supplier")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier_name = Column(String(255))  # boleh tetap diisi untuk display
    invoice_number = Column(String(100))
    purchase_date = Column(DateTime(timezone=True), server_default=func.now())
    total_amount = Column(Numeric(18, 2), default=0)
    payment_method = Column(String(50), default="CASH")
    notes = Column(String)

    payment_method = Column(String, nullable=True)
    source_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    source_account = relationship("Account")

    supplier = relationship("Supplier", back_populates="purchases")
    items = relationship(
        "PurchaseOrderItem",
        back_populates="purchase",
        cascade="all, delete-orphan",
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    qty = Column(Numeric(18, 2), nullable=False)
    unit_cost = Column(Numeric(18, 2), nullable=False)
    discount = Column(Numeric(18, 2), default=0)
    subtotal = Column(Numeric(18, 2), nullable=False)

    purchase = relationship("PurchaseOrder", back_populates="items")
    product = relationship("Product")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    expense_date = Column(DateTime(timezone=True), server_default=func.now())
    category = Column(String(100), nullable=False)   # misal: ONGKIR, LISTRIK, OPERASIONAL
    description = Column(String(255))
    amount = Column(Numeric(18, 2), nullable=False)
    payment_method = Column(String(50), default="CASH")
    notes = Column(String)
    payment_method = Column(String, nullable=True)
    
    source_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    source_account = relationship("Account")


class ProductRecipe(Base):
    __tablename__ = "product_recipes"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    component_product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    qty_per_unit = Column(Numeric(18, 2), nullable=False)  # berapa banyak RAW per 1 unit INTERNAL

    product = relationship(
        "Product",
        foreign_keys=[product_id],
        backref="recipe_components"
    )
    component = relationship(
        "Product",
        foreign_keys=[component_product_id]
    )


# models.py

class PurchasePlan(Base):
    __tablename__ = "purchase_plans"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier_name = Column(String(255), nullable=True)
    target_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(String, nullable=True)
    status = Column(String(20), default="OPEN")  # OPEN, PARTIAL, COMPLETED, CANCELLED
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    items = relationship("PurchasePlanItem", back_populates="plan")


class PurchasePlanItem(Base):
    __tablename__ = "purchase_plan_items"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("purchase_plans.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    planned_qty = Column(Numeric(18, 2), nullable=False)  # contoh 50
    received_qty = Column(Numeric(18, 2), default=0)      # accumulator dari semua purchase
    # remaining_qty = planned_qty - received_qty (boleh dihitung di schema / property)

    plan = relationship("PurchasePlan", back_populates="items")
    product = relationship("Product")


# class Account(Base):
#     __tablename__ = "accounts"

#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, nullable=False)             # contoh: "BCA"
#     bank_name = Column(String, nullable=True)         # contoh: "BCA"
#     account_number = Column(String, nullable=True)    # contoh: "2330171191"
#     current_balance = Column(Numeric, default=0)
#     is_active = Column(Boolean, default=True)