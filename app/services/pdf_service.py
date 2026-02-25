import json
import numpy as np
import re
import logging
import os
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Tuple, Union


from app.models.models import PDF, PDFContent, PDFChunk
from app.services.embedding_service import get_embeddings


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Maximum chunk size for splitting PDF text
MAX_CHUNK_SIZE = 3000
MIN_CHUNK_SIZE = 300
CHUNK_OVERLAP = 300

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file using PyPDF2.
    """
    try:
        logger.info(f"Opening file: {file_path}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return "File not found"
        
        # Check file size
        file_size = os.path.getsize(file_path)
        logger.info(f"File size: {file_size} bytes")
        
        if file_size == 0:
            logger.error(f"File is empty: {file_path}")
            return "Empty file"
        
        try:
            # Try to use PyPDF2 to extract text
            import PyPDF2
            text = ""
            
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                num_pages = len(reader.pages)
                
                logger.info(f"PDF has {num_pages} pages")
                
                if num_pages == 0:
                    logger.warning(f"PDF has no pages: {file_path}")
                    return "PDF has no pages."
                
                # Extract text from each page
                for page_num in range(num_pages):
                    logger.info(f"Extracting text from page {page_num+1}/{num_pages}")
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    
                    # Check if we got valid text
                    if page_text and page_text.strip():
                        # Process text to better preserve code blocks and formatting
                        # Look for potential code blocks (indented text or text with special characters)
                        lines = page_text.split('\n')
                        processed_lines = []
                        in_code_block = False
                        
                        for line in lines:
                            # Detecting potential code blocks based on indentation or code characters
                            if line.startswith('    ') or line.startswith('\t') or any(c in line for c in '{}[]()<>;:='):
                                if not in_code_block:
                                    # Mark the start of a code block
                                    processed_lines.append("```")
                                    in_code_block = True
                            elif in_code_block and line.strip() == "":
                                # End of code block
                                processed_lines.append("```")
                                in_code_block = False
                            
                            processed_lines.append(line)
                        
                        # Close any open code block
                        if in_code_block:
                            processed_lines.append("```")
                        
                        text += '\n'.join(processed_lines) + "\n\n"
                    else:
                        logger.warning(f"No text extracted from page {page_num+1}")
            
            if not text.strip():
                logger.warning(f"No text could be extracted from PDF: {file_path}")
                
                # Try another method (pdfplumber or pdfminer) if available
                try:
                    import pdfplumber
                    logger.info("Attempting extraction with pdfplumber")
                    
                    with pdfplumber.open(file_path) as pdf:
                        all_text = ""
                        for page in pdf.pages:
                            all_text += page.extract_text() or ""
                        
                        if all_text.strip():
                            return all_text
                except ImportError:
                    logger.info("pdfplumber not available")
                
                return f"No extractable text found in {os.path.basename(file_path)}"
            
            logger.info(f"Successfully extracted {len(text)} characters from PDF")
            return text
            
        except ImportError:
            logger.error("PyPDF2 not installed. Install with 'pip install PyPDF2'")
            return f"Cannot extract text: PyPDF2 not installed. This is a PDF document: {os.path.basename(file_path)}."
        except Exception as pdf_error:
            logger.error(f"Error extracting text with PyPDF2: {str(pdf_error)}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Error extracting text with PyPDF2: {str(pdf_error)}"
        
    except Exception as e:
        logger.error(f"Error extracting text from file {file_path}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Error processing file: {str(e)}"

def clean_text(text: str) -> str:
    """Clean and normalize text from PDF"""
    # Replace multiple newlines with a single one
    text = re.sub(r'\n{2,}', '\n', text)
    
    # Replace multiple spaces with a single one
    text = re.sub(r' {2,}', ' ', text)
    
    # Remove non-printable characters
    text = ''.join(c for c in text if c.isprintable() or c == '\n')
    
    return text.strip()

def split_text_into_chunks(text: str) -> List[str]:
    """Split text into smaller chunks while preserving structure"""
    # Clean the text first
    text = clean_text(text)
    
    # If text is small enough, return as a single chunk
    if len(text) <= MAX_CHUNK_SIZE:
        return [text]
    
    # Special handling for code blocks
    chunks = []
    current_chunk = ""
    code_block_marker = "```"
    in_code_block = False
    
    # Split by paragraphs
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    # Ensure we're processing all paragraphs
    logger.info(f"Splitting text into chunks from {len(paragraphs)} paragraphs")
    
    for paragraph in paragraphs:
        # Check if this paragraph contains code block markers
        if code_block_marker in paragraph:
            # Count occurrences to determine if block is opening, closing, or both
            markers = paragraph.count(code_block_marker)
            
            if not in_code_block and markers % 2 == 1:
                # Opening a code block
                in_code_block = True
            elif in_code_block and markers % 2 == 1:
                # Closing a code block
                in_code_block = False
        
        # If in code block or paragraph contains code markers, try to keep it intact
        if in_code_block or code_block_marker in paragraph:
            # If adding this code block would exceed max size and we already have content
            if len(current_chunk) + len(paragraph) > MAX_CHUNK_SIZE and len(current_chunk) >= MIN_CHUNK_SIZE:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph
        else:
            # Regular paragraph processing
            if len(current_chunk) + len(paragraph) > MAX_CHUNK_SIZE and len(current_chunk) >= MIN_CHUNK_SIZE:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # Ensure we have at least one chunk
    if not chunks:
        # If we couldn't create proper chunks, fall back to simple character-based chunking
        logger.warning("Falling back to simple character-based chunking")
        chunks = []
        for i in range(0, len(text), MAX_CHUNK_SIZE - CHUNK_OVERLAP):
            if i > 0:
                i = i - CHUNK_OVERLAP
            chunks.append(text[i:min(i + MAX_CHUNK_SIZE, len(text))])
    
    logger.info(f"Created {len(chunks)} chunks from text")
    return chunks

def save_pdf_to_db(db: Session, original_filename: str, stored_filename: str, text_content: str) -> int:
    """Save PDF information and content to the database"""
    try:
        logger.info(f"Saving PDF '{original_filename}' to database")
        
        # Create PDF record
        pdf = PDF(
            original_filename=original_filename,
            stored_filename=stored_filename
        )
        db.add(pdf)
        db.flush()  # Flush to get the ID
        
        logger.info(f"Created PDF record with ID {pdf.id}")
        
        # Create PDF content record
        if not text_content or text_content.strip() == "":
            text_content = f"No text could be extracted from this file: {original_filename}"
            logger.warning(f"No text content for PDF '{original_filename}', using placeholder")
        
        pdf_content = PDFContent(
            pdf_id=pdf.id,
            text_content=text_content
        )
        db.add(pdf_content)
        db.flush()
        
        logger.info(f"Added PDF content, splitting into chunks")
        
        # Split text into chunks and save
        try:
            # Always create at least one chunk
            chunks = split_text_into_chunks(text_content)
            logger.info(f"Split PDF '{original_filename}' into {len(chunks)} chunks")
            
            # Get embeddings for chunks
            try:
                logger.info(f"Generating embeddings for {len(chunks)} chunks")
                embeddings = get_embeddings(chunks)
                
                # Save chunks with embeddings
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    pdf_chunk = PDFChunk(
                        pdf_id=pdf.id,
                        chunk_text=chunk,
                        chunk_index=i,
                        embedding=json.dumps(embedding.tolist() if isinstance(embedding, np.ndarray) else embedding)
                    )
                    db.add(pdf_chunk)
                
                logger.info(f"Added {len(chunks)} chunks with embeddings to database")
            except Exception as emb_error:
                logger.error(f"Error generating embeddings: {str(emb_error)}")
                # Still save the chunks without embeddings
                for i, chunk in enumerate(chunks):
                    pdf_chunk = PDFChunk(
                        pdf_id=pdf.id,
                        chunk_text=chunk,
                        chunk_index=i,
                        embedding=json.dumps([0.0] * 10)  # Simple placeholder embedding
                    )
                    db.add(pdf_chunk)
                logger.info(f"Added {len(chunks)} chunks with placeholder embeddings to database")
        except Exception as chunk_error:
            logger.error(f"Error processing chunks: {str(chunk_error)}")
            import traceback
            logger.error(traceback.format_exc())
            # Create at least one chunk with the full text
            pdf_chunk = PDFChunk(
                pdf_id=pdf.id,
                chunk_text=text_content[:1000] if len(text_content) > 1000 else text_content,  # Limit size if too large
                chunk_index=0,
                embedding=json.dumps([0.0] * 10)  # Simple placeholder embedding
            )
            db.add(pdf_chunk)
            logger.info(f"Added single chunk with full text content due to error")
        
        # Commit all changes
        db.commit()
        logger.info(f"Successfully saved PDF '{original_filename}' with ID {pdf.id}")
        
        # Verify the PDF was saved correctly
        pdf_check = db.query(PDF).filter(PDF.id == pdf.id).first()
        if not pdf_check:
            logger.error(f"PDF with ID {pdf.id} not found after saving")
            raise Exception(f"PDF with ID {pdf.id} not found after saving")
        
        return pdf.id
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving PDF to database: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise

def get_all_pdfs(db: Session) -> List[PDF]:
    """Get all PDFs from the database"""
    return db.query(PDF).all()

def get_pdf_by_id(db: Session, pdf_id: int) -> Optional[PDF]:
    """Get a PDF by ID"""
    return db.query(PDF).filter(PDF.id == pdf_id).first()

def get_pdf_chunks(db: Session, pdf_id: int) -> List[PDFChunk]:
    """Get all chunks for a specific PDF"""
    return db.query(PDFChunk).filter(PDFChunk.pdf_id == pdf_id).order_by(PDFChunk.chunk_index).all()

def generate_summary(db: Session, pdf_id: int) -> Dict[str, any]:
    """
    Generate a summary of a PDF document.
    Returns a dictionary with summary information.
    """
    logger.info(f"Generating summary for PDF {pdf_id}")
    
    # Get PDF information
    pdf = db.query(PDF).filter(PDF.id == pdf_id).first()
    if not pdf:
        logger.error(f"PDF with ID {pdf_id} not found")
        return {
            "success": False,
            "message": "PDF not found"
        }
    
    # Get PDF content
    pdf_content = db.query(PDFContent).filter(PDFContent.pdf_id == pdf_id).first()
    if not pdf_content:
        logger.error(f"Content for PDF {pdf_id} not found")
        return {
            "success": False,
            "message": "PDF content not found"
        }
    
    # Get chunks
    chunks = db.query(PDFChunk).filter(PDFChunk.pdf_id == pdf_id).order_by(PDFChunk.chunk_index).all()
    
    # Basic metadata
    summary = {
        "success": True,
        "pdf_id": pdf_id,
        "filename": pdf.original_filename,
        "upload_date": pdf.upload_time.isoformat() if pdf.upload_time else None,
        "total_chunks": len(chunks),
    }
    
    # If there's no chunks, we can't generate a good summary
    if not chunks:
        summary["text_summary"] = "No content available for summarization"
        return summary
    
    # Extract key sentences for the summary
    try:
        text = pdf_content.text_content
        
        # Process the text to extract potential summary sentences
        sentences = []
        
        # Split text into sentences (simple implementation)
        for chunk in chunks:
            chunk_sentences = chunk.chunk_text.split('. ')
            chunk_sentences = [s.strip() + '.' for s in chunk_sentences if len(s.strip()) > 10]
            sentences.extend(chunk_sentences[:2])  # Take first couple of sentences from each chunk
        
        # Remove duplicates
        unique_sentences = []
        seen = set()
        for sentence in sentences:
            # Create a simplified version for comparison to avoid similar sentences
            simplified = re.sub(r'\W+', '', sentence.lower())
            if simplified not in seen and len(simplified) > 20:
                seen.add(simplified)
                unique_sentences.append(sentence)
        
        # Take the most representative sentences (up to 5)
        summary_sentences = unique_sentences[:5]
        
        if summary_sentences:
            summary["text_summary"] = " ".join(summary_sentences)
        else:
            # Fallback if no good sentences found
            summary["text_summary"] = chunks[0].chunk_text[:300] + "..."
        
        # Add content length
        summary["content_length"] = len(text)
        
        # Try to extract potential keywords
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        word_freq = {}
        for word in words:
            if word not in ['this', 'that', 'with', 'from', 'have', 'were', 'they', 'what', 'when', 'where', 'their']:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top keywords
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        summary["keywords"] = [word for word, freq in sorted_words[:10]]
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Provide a basic summary if there's an error
        summary["text_summary"] = f"Error generating detailed summary: {str(e)}"
        summary["error"] = str(e)
        return summary 