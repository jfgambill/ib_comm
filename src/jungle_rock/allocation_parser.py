#!/usr/bin/env python3
"""
Allocation Parser

This script parses allocation data from HTML emails and converts it to a structured JSON format.
"""

import sqlite3
import json
import re
import os
import sys
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional, Tuple
import logging
import hashlib

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='allocation_parser.log'
)
logger = logging.getLogger('allocation_parser')

class AllocationParser:
    def __init__(self, db_path: str, output_dir: str = 'allocations'):
        """
        Initialize the allocation parser.
        
        Args:
            db_path: Path to the SQLite database with emails
            output_dir: Directory to save allocation JSON files
        """
        self.db_path = db_path
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Mapping of common tickers to asset classes
        self.asset_class_map = {
            'SPY': 'equities',
            'IVV': 'equities',
            'VOO': 'equities',
            'QQQ': 'equities',
            'VTI': 'equities',
            'VEA': 'equities',
            'VWO': 'equities',
            'EFA': 'equities',
            'EEM': 'equities',
            'IEF': 'bonds',
            'TLT': 'bonds',
            'BND': 'bonds',
            'AGG': 'bonds',
            'LQD': 'bonds',
            'HYG': 'bonds',
            'MBB': 'bonds',
            'GLD': 'commodities',
            'IAU': 'commodities',
            'SLV': 'commodities',
            'GSG': 'commodities',
            'DBC': 'commodities',
            'USO': 'commodities',
            'BIL': 'cash',
            'SHV': 'cash',
            'SHY': 'cash',
            'VMFXX': 'cash',
            'SPAXX': 'cash',
            'FDRXX': 'cash'
        }
    
    def get_unprocessed_emails(self) -> List[Dict[str, Any]]:
        """
        Retrieve unprocessed emails from the database.
        
        Returns:
            List of email dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if we have a processed flag column, if not add it
            cursor.execute("PRAGMA table_info(emails)")
            columns = [info[1] for info in cursor.fetchall()]
            
            if 'processed' not in columns:
                cursor.execute("ALTER TABLE emails ADD COLUMN processed INTEGER DEFAULT 0")
                conn.commit()
            
            # Get unprocessed emails
            cursor.execute("""
                SELECT id, email_id, from_address, to_address, subject, date, body_html, body_text
                FROM emails
                WHERE processed = 0
            """)
            
            emails = []
            for row in cursor.fetchall():
                emails.append({
                    'id': row[0],
                    'email_id': row[1],
                    'from': row[2],
                    'to': row[3],
                    'subject': row[4],
                    'date': row[5],
                    'body_html': row[6],
                    'body_text': row[7]
                })
            
            return emails
        except Exception as e:
            logger.error(f"Error retrieving emails: {str(e)}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()
    
    def parse_email(self, email: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse allocation data from an email.
        
        Args:
            email: Email dictionary
        
        Returns:
            Allocation data dictionary or None if parsing failed
        """
        try:
            # Use HTML content if available, otherwise use text
            content = email['body_html'] if email['body_html'] else email['body_text']
            
            if not content:
                logger.warning(f"Empty content for email {email['id']}")
                return None
            
            # Parse HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            # Get strategy description from h3 tag
            strategy_description = soup.find('h3')
            if not strategy_description:
                logger.warning(f"No strategy description found in email {email['id']}")
                return None
            
            strategy_description = strategy_description.text.strip()
            
            # Extract allocation table data
            table = soup.find('table')
            if not table:
                logger.warning(f"No table found in email {email['id']}")
                return None
            
            # Process table rows
            rows = table.find_all('tr')
            
            # Get computation date and allocation date
            metadata = {}
            allocations = []
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) != 2:
                    continue
                
                key = cells[0].text.strip()
                value = cells[1].text.strip()
                
                if key == "Last Computation Date":
                    metadata['computation_date'] = value
                elif key == "Last Allocation Date":
                    metadata['allocation_date'] = value
                else:
                    # Try to extract ticker and percentage
                    ticker = key.strip()
                    percentage_str = value.strip()
                    
                    # Remove "%" and convert to float
                    if percentage_str.endswith('%'):
                        percentage_str = percentage_str[:-1]
                    
                    try:
                        percentage = float(percentage_str)
                        
                        # Determine asset class
                        asset_class = self.asset_class_map.get(ticker, 'unknown')
                        
                        allocations.append({
                            'ticker': ticker,
                            'percentage': percentage,
                            'asset_class': asset_class
                        })
                    except ValueError:
                        logger.warning(f"Could not parse percentage for {ticker}: {percentage_str}")
            
            # Calculate total allocation and leverage
            total_allocation = sum(item['percentage'] for item in allocations)
            leverage = total_allocation / 100.0 if total_allocation > 0 else 0
            
            # Create received date in ISO format
            try:
                # Try to parse the email date
                email_date_str = email['date']
                received_date = self._parse_email_date(email_date_str)
                received_date_iso = received_date.isoformat() if received_date else datetime.now().isoformat()
            except:
                # Default to current time if parsing fails
                received_date_iso = datetime.now().isoformat()
            
            # Use the email_id directly
            email_id = email['email_id']
            
            # Create the allocation data structure
            allocation_data = {
                "schema_version": "1.0",
                "metadata": {
                    "strategy_name": email['subject'],
                    "strategy_description": strategy_description,
                    "computation_date": metadata.get('computation_date', ''),
                    "allocation_date": metadata.get('allocation_date', ''),
                    "received_date": received_date_iso,
                    "processing_timestamp": datetime.now().isoformat(),
                    "email_id": email_id,
                    "db_record_id": email['id'],
                    "source": "email"
                },
                "summary": {
                    "total_allocation": round(total_allocation, 2),
                    "leverage": round(leverage, 2),
                    "ticker_count": len(allocations)
                },
                "allocations": allocations,
                "validation": {
                    "is_valid": total_allocation <= 200.0,
                    "messages": [] if total_allocation <= 200.0 else ["Total allocation exceeds 200%"]
                }
            }
            
            return allocation_data
        except Exception as e:
            logger.error(f"Error parsing email {email['id']}: {str(e)}")
            return None
    
    def _parse_email_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse email date string to datetime.
        
        Args:
            date_str: Email date string
            
        Returns:
            Datetime object or None if parsing failed
        """
        # Try various date formats
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # RFC 2822 format
            '%d %b %Y %H:%M:%S %z',
            '%a, %d %b %Y %H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def _generate_message_id(self, email: Dict[str, Any]) -> str:
        """
        Generate a message ID for the email.
        
        Args:
            email: Email dictionary
            
        Returns:
            Message ID string
        """
        # Create a string with email attributes
        data = f"{email['subject']}-{email['date']}-{email['from']}"
        
        # Generate a hash
        return hashlib.md5(data.encode()).hexdigest()
    
    def save_allocation(self, allocation_data: Dict[str, Any]) -> str:
        """
        Save allocation data to a JSON file.
        
        Args:
            allocation_data: Allocation data dictionary
            
        Returns:
            Path to the saved file
        """
        try:
            # Create a filename with strategy name and date
            strategy_name = allocation_data['metadata']['strategy_name']
            allocation_date = allocation_data['metadata']['allocation_date']
            
            # Sanitize strategy name for use in filename
            safe_strategy_name = re.sub(r'[^\w]', '_', strategy_name)
            
            # Create filename
            filename = f"{safe_strategy_name}_{allocation_date}.json"
            file_path = os.path.join(self.output_dir, filename)
            
            # If file already exists, add a timestamp to make it unique
            if os.path.exists(file_path):
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"{safe_strategy_name}_{allocation_date}_{timestamp}.json"
                file_path = os.path.join(self.output_dir, filename)
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(allocation_data, f, indent=2)
            
            logger.info(f"Saved allocation data to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error saving allocation data: {str(e)}")
            return ""
    
    def mark_email_processed(self, email_id: int) -> bool:
        """
        Mark an email as processed in the database.
        
        Args:
            email_id: Email ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("UPDATE emails SET processed = 1 WHERE id = ?", (email_id,))
            conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error marking email {email_id} as processed: {str(e)}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_emails(self) -> List[str]:
        """
        Process all unprocessed emails.
        
        Returns:
            List of paths to saved allocation files
        """
        saved_files = []
        
        # Get unprocessed emails
        emails = self.get_unprocessed_emails()
        
        if not emails:
            logger.info("No unprocessed emails found")
            return saved_files
        
        logger.info(f"Found {len(emails)} unprocessed emails")
        
        # Process each email
        for email in emails:
            logger.info(f"Processing email {email['id']}: {email['subject']}")
            
            # Parse email
            allocation_data = self.parse_email(email)
            
            if allocation_data:
                # Save allocation data
                file_path = self.save_allocation(allocation_data)
                
                if file_path:
                    saved_files.append(file_path)
                    
                    # Mark email as processed
                    self.mark_email_processed(email['id'])
            else:
                logger.warning(f"Failed to parse email {email['id']}")
        
        return saved_files

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse allocation data from emails')
    parser.add_argument('--db', type=str, required=True, help='Path to emails database')
    parser.add_argument('--output', type=str, default='allocations', help='Output directory for allocation files')
    
    args = parser.parse_args()
    
    parser = AllocationParser(args.db, args.output)
    saved_files = parser.process_emails()
    
    print(f"Processed {len(saved_files)} allocation messages:")
    for file_path in saved_files:
        print(f"  - {file_path}")

if __name__ == "__main__":
    main()