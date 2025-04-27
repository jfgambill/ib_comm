#!/usr/bin/env python3
"""
Database Migration Script

This script migrates an existing emails.db from using message_id to the new email_id format.
"""

import sqlite3
import os
import sys
import argparse
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='db_migration.log'
)
logger = logging.getLogger('db_migration')

def migrate_database(db_path: str, backup: bool = True) -> bool:
    """
    Migrate the database from message_id to email_id.
    
    Args:
        db_path: Path to the database file
        backup: Whether to create a backup before migration
        
    Returns:
        True if migration was successful, False otherwise
    """
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    # Create backup if requested
    if backup:
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            import shutil
            shutil.copy2(db_path, backup_path)
            logger.info(f"Created backup at {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
            return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if we already have an email_id column
        cursor.execute("PRAGMA table_info(emails)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'email_id' in columns:
            logger.info("email_id column already exists, no migration needed")
            conn.close()
            return True
        
        # Check if we have a message_id column
        if 'message_id' not in columns:
            logger.error("message_id column not found, cannot migrate")
            conn.close()
            return False
        
        # Start transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Add email_id column
        cursor.execute("ALTER TABLE emails ADD COLUMN email_id TEXT")
        
        # Generate email_id values
        cursor.execute("SELECT id FROM emails ORDER BY id")
        rows = cursor.fetchall()
        
        # Update rows with new email_id values
        for i, row in enumerate(rows):
            id_value = row[0]
            email_id = f"e{i+1:05d}"
            cursor.execute("UPDATE emails SET email_id = ? WHERE id = ?", (email_id, id_value))
        
        # Make email_id unique
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_email_id ON emails(email_id)")
        
        # Create a new table with the updated schema
        cursor.execute("""
        CREATE TABLE emails_new (
            id INTEGER PRIMARY KEY,
            email_id TEXT UNIQUE,
            from_address TEXT,
            to_address TEXT,
            subject TEXT,
            date TEXT,
            body_text TEXT,
            body_html TEXT,
            received_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed INTEGER DEFAULT 0
        )
        """)
        
        # When copying data to new table, change this line:
        cursor.execute("""
        INSERT INTO emails_new (
            id, email_id, from_address, to_address, subject, date, body_text, body_html, received_date
        )
        SELECT 
            id, email_id, from_address, to_address, subject, date, body_text, body_html, received_date
        FROM emails
        """)
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE emails")
        cursor.execute("ALTER TABLE emails_new RENAME TO emails")
        
        # Commit changes
        conn.commit()
        logger.info("Migration completed successfully")
        
        # Log statistics
        cursor.execute("SELECT COUNT(*) FROM emails")
        count = cursor.fetchone()[0]
        logger.info(f"Total emails migrated: {count}")
        
        return True
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    parser = argparse.ArgumentParser(description='Migrate emails database from message_id to email_id')
    parser.add_argument('--db', type=str, required=True, help='Path to the database file')
    parser.add_argument('--no-backup', action='store_true', help='Skip database backup')
    
    args = parser.parse_args()
    
    success = migrate_database(args.db, not args.no_backup)
    
    if success:
        print("Database migration completed successfully")
        sys.exit(0)
    else:
        print("Database migration failed, see db_migration.log for details")
        sys.exit(1)

if __name__ == "__main__":
    main()