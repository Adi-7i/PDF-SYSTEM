from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base

class PDF(Base):
    """Model for storing PDF information"""
    __tablename__ = "pdfs"

    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False, unique=True)
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    contents = relationship("PDFContent", back_populates="pdf", cascade="all, delete-orphan")
    chunks = relationship("PDFChunk", back_populates="pdf", cascade="all, delete-orphan")

class PDFContent(Base):
    """Model for storing the full text content of a PDF"""
    __tablename__ = "pdf_contents"

    id = Column(Integer, primary_key=True, index=True)
    pdf_id = Column(Integer, ForeignKey("pdfs.id", ondelete="CASCADE"), nullable=False)
    text_content = Column(Text, nullable=False)
    
    # Relationships
    pdf = relationship("PDF", back_populates="contents")

class PDFChunk(Base):
    """Model for storing chunks of PDF text with embeddings"""
    __tablename__ = "pdf_chunks"

    id = Column(Integer, primary_key=True, index=True)
    pdf_id = Column(Integer, ForeignKey("pdfs.id", ondelete="CASCADE"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(Text, nullable=False)  # JSON string of embedding vector
    
    # Relationships
    pdf = relationship("PDF", back_populates="chunks") 