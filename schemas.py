# schemas.py
from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from enum import Enum

# ===== Auth =====
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    is_active: bool
    is_admin: bool

    class Config:
        from_attributes = True


# ===== Products =====


class ProductType(str, Enum):
    INTERNAL = "INTERNAL"   # Produk jadi untuk dijual
    RAW = "RAW"             # Bahan baku / material
    SERVICE = "SERVICE"     # Layanan (jika perlu)


class ProductBase(BaseModel):
    sku: str
    name: str
    category: Optional[str] = None
    unit: Optional[str] = None
    base_cost: float = 0
    sell_price: float = 0
    stock_qty: float = 0
    min_stock: float = 0
    is_active: bool = True


class ProductCreate(BaseModel):
    sku: str
    name: str
    category: Optional[str] = None
    unit: Optional[str] = None
    product_type: ProductType = ProductType.INTERNAL   # ← di sini
    base_cost: Decimal = Decimal("0")
    sell_price: Decimal = Decimal("0")
    stock_qty: Decimal = Decimal("0")
    min_stock: Decimal = Decimal("0")
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    base_cost: Optional[float] = None
    sell_price: Optional[float] = None
    stock_qty: Optional[float] = None
    min_stock: Optional[float] = None
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    category: Optional[str]
    unit: Optional[str]
    product_type: ProductType       # ← di sini
    base_cost: Decimal
    sell_price: Decimal
    stock_qty: Decimal
    min_stock: Decimal
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    # class Config:
    #     from_attributes = True


# ===== Sales =====
class SalesItemIn(BaseModel):
    product_id: int
    qty: float
    unit_price: float
    discount: float = 0

# class SalesItemCreate(BaseModel):
#     product_id: int
#     qty: int
#     unit_price: Decimal
#     discount: Decimal = Decimal("0")

class SalesCreate(BaseModel):
    customer_id: Optional[int] = None  # Optional, akan auto-create jika None
    customer_name: Optional[str] = None  # Wajib jika customer_id None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    payment_method: str = "CASH"
    notes: Optional[str] = None
    items: list[SalesItemIn]

class SalesOut(BaseModel):
    id: int
    customer_id: Optional[int]  # ✅ Sekarang selalu terisi
    customer_name: str
    order_date: datetime
    status: str
    total_amount: Decimal
    payment_method: str
    notes: Optional[str]
    
    class Config:
        from_attributes = True

class PurchaseItemCreate(BaseModel):
    product_id: int
    qty: Decimal
    unit_cost: Decimal
    discount: Decimal = Decimal("0")

class PurchaseCreate(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None   # kalau belum pakai master supplier
    invoice_number: Optional[str] = None
    purchase_date: Optional[datetime] = None
    payment_method: str = "CASH"
    notes: Optional[str] = None
    items: List[PurchaseItemCreate]


class PurchaseItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    qty: Decimal
    unit_cost: Decimal
    discount: Decimal
    subtotal: Decimal


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    invoice_number: Optional[str] = None
    purchase_date: datetime
    total_amount: Decimal
    payment_method: str
    notes: Optional[str] = None
    items: List[PurchaseItemOut]


# --- EXPENSES ---

class ExpenseCreate(BaseModel):
    expense_date: Optional[datetime] = None
    category: str
    description: Optional[str] = None
    amount: Decimal
    payment_method: str = "CASH"
    notes: Optional[str] = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    expense_date: datetime
    category: str
    description: Optional[str]
    amount: Decimal
    payment_method: str
    notes: Optional[str]

# --- Customers ---

class CustomerBase(BaseModel):
    name: str
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    source_channel: str | None = None   # 👈 tambah ini
    notes: str | None = None
    is_active: bool = True



class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    source_channel: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class CustomerOut(CustomerBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Suppliers ---
class SupplierCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    contact: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    contact: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    is_active: bool
    created_at: datetime



class RecipeComponentCreate(BaseModel):
    product_id: int              # ID produk INTERNAL / paket
    component_product_id: int    # ID produk RAW
    qty_per_unit: Decimal        # contoh: 1.5, 0.25, dll


class RecipeComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    component_product_id: int
    qty_per_unit: Decimal

