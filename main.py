from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import Base, engine
import models
from routers import auth, products, sales, purchases, expenses, suppliers, recipes, reports, customers

# Create tables (development only)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="POS & Finance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/")
def read_root():
    return {"message": "POS API is running"}
