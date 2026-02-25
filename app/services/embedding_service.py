import numpy as np
import logging
import os
from typing import List, Union, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default embedding dimension
DEFAULT_EMBEDDING_DIM = 128

# Try to load config from environment
try:
    EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", DEFAULT_EMBEDDING_DIM))
except (ValueError, TypeError):
    logger.warning(f"Invalid EMBEDDING_DIM environment variable, using default: {DEFAULT_EMBEDDING_DIM}")
    EMBEDDING_DIM = DEFAULT_EMBEDDING_DIM

# Flag to use external embedding service if available
USE_EXTERNAL_EMBEDDINGS = os.environ.get("USE_EXTERNAL_EMBEDDINGS", "false").lower() == "true"

def get_embeddings(texts: List[str], embedding_dim: Optional[int] = None) -> List[np.ndarray]:
    """
    Generate embeddings for a list of texts.
    
    Args:
        texts: List of text strings to embed
        embedding_dim: Optional dimension override for the embeddings
        
    Returns:
        List of embedding vectors as numpy arrays
    """
    dim = embedding_dim or EMBEDDING_DIM
    logger.info(f"Generating embeddings for {len(texts)} texts with dimension {dim}")
    
    # Try to use better embedding models if configured
    if USE_EXTERNAL_EMBEDDINGS:
        try:
            return get_external_embeddings(texts, dim)
        except Exception as e:
            logger.error(f"Error using external embeddings: {str(e)}, falling back to simple embeddings")
    
    # Fall back to simple embeddings
    return get_simple_embeddings(texts, dim)

def get_simple_embeddings(texts: List[str], embedding_dim: int = EMBEDDING_DIM) -> List[np.ndarray]:
    """
    Generate simple deterministic embeddings based on text content.
    This is not a real embedding model, but provides consistent results for testing.
    """
    embeddings = []
    for text in texts:
        # Create a deterministic embedding based on the text content
        embedding = np.zeros(embedding_dim, dtype=np.float32)
        
        # Use character values to populate the embedding
        for i, char in enumerate(text):
            idx = i % embedding_dim
            embedding[idx] += ord(char) / 1000.0
        
        # Normalize the embedding
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        embeddings.append(embedding)
    
    logger.info(f"Generated {len(embeddings)} simple embeddings")
    return embeddings

def get_external_embeddings(texts: List[str], embedding_dim: int = EMBEDDING_DIM) -> List[np.ndarray]:
    """
    Placeholder for getting embeddings from an external service or better model.
    This would be implemented with actual embedding models in production.
    """
    logger.info("External embedding service not implemented, using simple embeddings")
    return get_simple_embeddings(texts, embedding_dim)

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors"""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return np.dot(a, b) / (norm_a * norm_b)
