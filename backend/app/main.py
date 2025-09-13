from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, constr

from .db import SessionLocal          # SQLAlchemy session factory
from .db_check import check_db        # existing DB health helper
from .models import Product           # ORM model for products

# Create the FastAPI application object
app = FastAPI()

# --- Per-request database session dependency ---
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

# --- Pydantic schemas for Product (validation/typing) ---
class ProductIn(BaseModel):
    # Incoming payload when creating a product
    brand: constr(strip_whitespace=True, min_length=1, max_length=255)
    model: constr(strip_whitespace=True, min_length=1, max_length=255)

class ProductOut(BaseModel):
    # Outgoing shape when returning a product
    id: int
    brand: str
    model: str

    class Config:
        # Allow returning SQLAlchemy ORM objects directly
        from_attributes = True

# ----- Existing health routes -----
@app.get("/ping")
def ping():
    return {"message": "pong"}

@app.get("/health/db")
def health_db():
    return check_db()

# ----- NEW: Create (insert) a product -----
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

# ----- NEW: List all products -----
@app.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    """
    Return all products ordered by id.
    """
    return db.query(Product).order_by(Product.id.asc()).all()
