# app/main.py
from __future__ import annotations

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, constr

# --- Local imports ---
from .db import SessionLocal            # SQLAlchemy session factory
from .db_check import check_db          # existing DB health helper
from .models import Product             # ORM model for products

# Routers
from app.routers import chunks as chunks_router         # /admin/chunks/...
from app.routers import documents as documents_router   # /admin/documents/...
from app.routers import search as search_router         # /search

# ---------------------------
# Create FastAPI app FIRST
# ---------------------------
app = FastAPI(title="APP Backend", version="0.1.0")

# ---------------------------
# CORS for local dev (frontend on :3000)
# ---------------------------
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],   # GET/POST/OPTIONS/etc.
    allow_headers=["*"],   # Content-Type, Authorization, etc.
)

# ---------------------------
# Register routers
# ---------------------------
app.include_router(chunks_router.router)       # /admin/chunks/...
app.include_router(documents_router.router)    # /admin/documents/...
app.include_router(search_router.router)       # /search

# ---------------------------
# Per-request DB session dep
# ---------------------------
def get_db():
    """
    Open a SQLAlchemy session for this request and close it afterward.
    Prevents connection leaks and centralizes DB handling.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------
# Pydantic schemas for Product
# ---------------------------
class ProductIn(BaseModel):
    brand: constr(strip_whitespace=True, min_length=1, max_length=255)
    model: constr(strip_whitespace=True, min_length=1, max_length=255)

class ProductOut(BaseModel):
    id: int
    brand: str
    model: str

    class Config:
        from_attributes = True  # allows returning ORM objects directly

# ---------------------------
# Health routes
# ---------------------------
@app.get("/ping")
def ping():
    return {"message": "pong"}

@app.get("/health/db")
def health_db():
    return check_db()

# ---------------------------
# Product CRUD (minimal)
# ---------------------------
@app.post("/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductIn, db: Session = Depends(get_db)):
    """
    Insert (brand, model). On duplicate (unique constraint), return HTTP 409.
    """
    prod = Product(brand=payload.brand, model=payload.model)
    db.add(prod)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Product already exists (brand, model)")
    db.refresh(prod)
    return prod

@app.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    """
    Return all products ordered by id.
    """
    return db.query(Product).order_by(Product.id.asc()).all()
