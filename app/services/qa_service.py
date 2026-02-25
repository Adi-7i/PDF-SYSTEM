import json
import numpy as np
import logging
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.models.models import PDFChunk
from app.services.embedding_service import get_embeddings, cosine_similarity

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Number of top chunks to retrieve
TOP_K_CHUNKS = 3

def answer_question(db: Session, question: str) -> str:
    """Answer a question based on the content of uploaded PDFs"""
    logger.info(f"Processing question: {question}")
    
    # Get question embedding
    question_embedding = get_embeddings([question])[0]
    
    # Get all chunks from the database
    chunks = db.query(PDFChunk).all()
    
    if not chunks:
        logger.warning("No PDF chunks found in database")
        return "No PDF content available to answer questions. Please upload a PDF first."
    
    logger.info(f"Found {len(chunks)} chunks in database")
    
    # Calculate similarity scores
    chunk_scores = []
    for chunk in chunks:
        try:
            # Parse embedding from JSON
            chunk_embedding = np.array(json.loads(chunk.embedding))
            
            # Calculate similarity
            score = cosine_similarity(question_embedding, chunk_embedding)
            
            chunk_scores.append((chunk, score))
        except Exception as e:
            logger.error(f"Error processing chunk {chunk.id}: {str(e)}")
    
    # Sort by similarity score (descending)
    chunk_scores.sort(key=lambda x: x[1], reverse=True)
    
    # Get top K chunks
    top_chunks = chunk_scores[:TOP_K_CHUNKS]
    
    if not top_chunks:
        logger.warning("No relevant chunks found")
        return "I couldn't find any relevant information in the uploaded PDFs."
    
    # Generate answer based on top chunks
    answer = generate_answer(question, top_chunks)
    
    return answer

def generate_answer(question: str, top_chunks: List[tuple]) -> str:
    """Generate an answer based on the top chunks"""
    # Extract text from top chunks
    chunk_texts = [chunk[0].chunk_text for chunk in top_chunks]
    chunk_scores = [chunk[1] for chunk in top_chunks]
    
    # Get the best chunk and its score
    best_chunk = top_chunks[0][0]
    best_score = top_chunks[0][1]
    
    # Get PDF ID and find original filename
    pdf_id = best_chunk.pdf_id
    
    # Format confidence as percentage
    confidence = int(best_score * 100)
    
    # Simple answer generation
    if confidence >= 70:
        answer = f"Based on the PDF content, I found this information:\n\n{best_chunk.chunk_text}\n\nSource: PDF #{pdf_id}\nConfidence: {confidence}%"
    elif confidence >= 40:
        answer = f"I'm not entirely sure, but here's what I found in the PDF:\n\n{best_chunk.chunk_text}\n\nSource: PDF #{pdf_id}\nConfidence: {confidence}%"
    else:
        answer = f"I couldn't find a definitive answer, but this might be relevant:\n\n{best_chunk.chunk_text}\n\nSource: PDF #{pdf_id}\nConfidence: {confidence}%"
    
    return answer 