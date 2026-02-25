import logging
import uvicorn
from app.db.database import engine
from app.models.models import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create database tables if they don't exist
def setup_database():
    logger.info("Setting up database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database setup complete")

if __name__ == "__main__":
    logger.info("Starting PDF Q&A System")
    
    # Setup database
    setup_database()
    
    # Start FastAPI application
    logger.info("Starting FastAPI application")
    uvicorn.run(
        "app.main:app", 
        host="127.0.0.1", 
        port=8082,  # Changed port from 8081 to 8082
        reload=False  # Disable auto-reload to prevent constant restarts
    ) 