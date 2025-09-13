# app/models.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    brand = Column(String(255), nullable=False)
    model = Column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint("brand", "model", name="uq_products_brand_model"),)

    documents = relationship("Document", back_populates="product")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    source_url = Column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("product_id", "source_url", name="uq_documents_product_url"),)

    product = relationship("Product", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document")

class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    # NOTE: The embedding column (vector(1536)) exists in the DB already.
    # We will access it later via raw SQL for similarity search.
    document = relationship("Document", back_populates="chunks")

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True)
    rating = Column(Integer, nullable=False)  # 1..5
    comments = Column(Text)
    product_id = Column(Integer, ForeignKey("products.id"))
    document_id = Column(Integer, ForeignKey("documents.id"))

class Request(Base):
    __tablename__ = "requests"
    id = Column(Integer, primary_key=True)
    brand = Column(String(255), nullable=False)
    model = Column(String(255), nullable=False)
    email = Column(String(255))
    notes = Column(Text)
    status = Column(String(50), default="open")
