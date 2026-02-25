import os
import logging
from app.db.database import engine, Base
from app.models.models import PDF, PDFContent, PDFChunk

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def reset_database():
    """Reset the database by dropping and recreating all tables"""
    try:
        logger.info("Resetting database...")
        
        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        logger.info("Existing tables dropped")
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        logger.info("New tables created")
        
        # Create uploads directory if it doesn't exist
        os.makedirs("app/static/uploads", exist_ok=True)
        logger.info("Uploads directory created/verified")
        
        return True
    except Exception as e:
        logger.error(f"Error resetting database: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    if input("Are you sure you want to reset the database? This will delete all data. (y/n): ").lower() == 'y':
        if reset_database():
            logger.info("Database reset successfully")
        else:
            logger.error("Failed to reset database")
    else:
        logger.info("Database reset cancelled") 