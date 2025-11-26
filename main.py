from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import Base, engine
import models
from routers import auth, products, sales, purchases, expenses, suppliers, recipes, reports, customers, admin_restore, stock_movements, purchase_plan, accounts

# Create tables (development only)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="POS & Finance API")


# # ✅ PENTING: Tambahkan ini SEBELUM app.include_router
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:3000"],  # React dev server
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    # kalau kamu akses dari IP lain / domain lain, tambahkan di sini
    # "http://10.121.1.62:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(sales.router)
app.include_router(purchases.router)   # ← baru
app.include_router(expenses.router)    # ← baru
app.include_router(suppliers.router)
app.include_router(recipes.router)
app.include_router(reports.router)
app.include_router(customers.router)
app.include_router(admin_restore.router)
app.include_router(stock_movements.router)
app.include_router(purchase_plan.router)
app.include_router(accounts.router) 

@app.get("/")
def read_root():
    return {"message": "POS API is running"}
