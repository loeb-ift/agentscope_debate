"""
Database migration script to add EDA artifact support to EvidenceDoc model.

This script adds two new columns to the evidence_docs table:
- artifact_type: Type of artifact ("report", "plot", "table", or NULL)
- file_path: Absolute path to the artifact file
"""
import sys
sys.path.insert(0, '/Users/loeb/Desktop/agentscope_debate')

from api.database import engine
from sqlalchemy import text, inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    """Execute migration to add EDA artifact support."""
    logger.info("Starting migration: Add EDA artifact support to evidence_docs")
    
    with engine.connect() as conn:
        # Check if columns already exist
        if check_column_exists('evidence_docs', 'artifact_type'):
            logger.info("Column 'artifact_type' already exists, skipping...")
        else:
            logger.info("Adding column 'artifact_type'...")
            conn.execute(text("""
                ALTER TABLE evidence_docs 
                ADD COLUMN artifact_type VARCHAR(20);
            """))
            conn.commit()
            logger.info("✓ Column 'artifact_type' added")
        
        if check_column_exists('evidence_docs', 'file_path'):
            logger.info("Column 'file_path' already exists, skipping...")
        else:
            logger.info("Adding column 'file_path'...")
            conn.execute(text("""
                ALTER TABLE evidence_docs 
                ADD COLUMN file_path VARCHAR(500);
            """))
            conn.commit()
            logger.info("✓ Column 'file_path' added")
    
    logger.info("✅ Migration completed successfully!")


def rollback():
    """Rollback migration (remove added columns)."""
    logger.info("Rolling back migration: Remove EDA artifact columns")
    
    with engine.connect() as conn:
        if check_column_exists('evidence_docs', 'artifact_type'):
            logger.info("Removing column 'artifact_type'...")
            conn.execute(text("""
                ALTER TABLE evidence_docs 
                DROP COLUMN artifact_type;
            """))
            conn.commit()
            logger.info("✓ Column 'artifact_type' removed")
        
        if check_column_exists('evidence_docs', 'file_path'):
            logger.info("Removing column 'file_path'...")
            conn.execute(text("""
                ALTER TABLE evidence_docs 
                DROP COLUMN file_path;
            """))
            conn.commit()
            logger.info("✓ Column 'file_path' removed")
    
    logger.info("✅ Rollback completed successfully!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate evidence_docs table for EDA support")
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback the migration (remove added columns)"
    )
    
    args = parser.parse_args()
    
    if args.rollback:
        rollback()
    else:
        migrate()
