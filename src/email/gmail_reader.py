#!/usr/bin/env python3
"""
Simple Gmail IMAP Reader
Much simpler than ProtonMail Bridge - just enable 2FA and create an App Password
"""

import imaplib
import email
from email.header import decode_header
import sqlite3
from datetime import datetime
import logging
from typing import List, Dict, Any, Optional
import sys
import os
# Add the src directory to Python path so we can import from credentials
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from credentials.keys import GMAIL_EMAIL, GMAIL_APP_PASSWORD

logger = logging.getLogger(__name__)

class GmailReader:
    def __init__(self, email_address: str = GMAIL_EMAIL, app_password: str = GMAIL_APP_PASSWORD, db_path: str = 'gmail_emails.db'):
        """
        Initialize Gmail reader
        
        Args:
            email_address: Your Gmail address
            app_password: Gmail App Password (not your regular password)
            db_path: SQLite database path
        """
        self.email_address = email_address
        self.app_password = app_password
        self.db_path = db_path
        self.conn = None
        self.db_conn = None
        
        # Setup database
        self.setup_database()
    
    def setup_database(self):
        """Setup SQLite database"""
        self.db_conn = sqlite3.connect(self.db_path)
        cursor = self.db_conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                from_address TEXT,
                to_address TEXT,
                subject TEXT,
                date TEXT,
                body_text TEXT,
                body_html TEXT,
                received_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.db_conn.commit()
        logger.info(f"Database initialized at {self.db_path}")
    
    def connect(self):
        """Connect to Gmail IMAP"""
        try:
            self.conn = imaplib.IMAP4_SSL('imap.gmail.com', 993)
            self.conn.login(self.email_address, self.app_password)
            logger.info("Connected to Gmail successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Gmail: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from Gmail"""
        if self.conn:
            try:
                self.conn.close()
                self.conn.logout()
            except:
                pass
        
        if self.db_conn:
            self.db_conn.close()
    
    def get_emails(self, folder: str = 'INBOX', limit: int = 10, 
                   sender_filter: str = None, subject_filter: str = None,
                   unread_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get emails from Gmail
        
        Args:
            folder: Gmail folder ('INBOX', 'SENT', etc.)
            limit: Max number of emails to fetch
            sender_filter: Filter by sender email
            subject_filter: Filter by subject keyword (partial matching supported)
            unread_only: Only get unread emails
            
        Returns:
            List of email dictionaries
        """
        try:
            # Select folder
            self.conn.select(folder)
            
            # Build search criteria
            search_criteria = []
            
            if unread_only:
                search_criteria.append('UNSEEN')
            
            if sender_filter:
                search_criteria.append(f'FROM "{sender_filter}"')
            
            if subject_filter:
                # Support partial matching - IMAP will find subjects containing this text
                search_criteria.append(f'SUBJECT "{subject_filter}"')
            
            # Search for emails
            if search_criteria:
                search_query = '(' + ' '.join(search_criteria) + ')'
            else:
                search_query = 'ALL'
            
            status, messages = self.conn.search(None, search_query)
            
            if status != 'OK':
                logger.error(f"Search failed: {messages}")
                return []
            
            # Get message IDs
            message_ids = messages[0].split()
            
            # Limit results
            if limit:
                message_ids = message_ids[-limit:]  # Get most recent
            
            emails = []
            for msg_id in reversed(message_ids):  # Most recent first
                email_data = self._parse_email(msg_id)
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []
    
    def _parse_email(self, msg_id: bytes) -> Optional[Dict[str, Any]]:
        """Parse a single email"""
        try:
            # Fetch email
            status, msg_data = self.conn.fetch(msg_id, '(RFC822)')
            
            if status != 'OK':
                return None
            
            # Parse email
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Extract basic info
            message_id = msg.get('Message-ID', '')
            from_addr = msg.get('From', '')
            to_addr = msg.get('To', '')
            subject = self._decode_header(msg.get('Subject', ''))
            date = msg.get('Date', '')
            
            # Extract body
            body_text, body_html = self._extract_body(msg)
            
            return {
                'message_id': message_id,
                'from': from_addr,
                'to': to_addr,
                'subject': subject,
                'date': date,
                'body_text': body_text,
                'body_html': body_html
            }
            
        except Exception as e:
            logger.error(f"Error parsing email: {e}")
            return None
    
    def _decode_header(self, header: str) -> str:
        """Decode email header"""
        decoded_parts = decode_header(header)
        result = ''
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                if encoding:
                    result += part.decode(encoding)
                else:
                    result += part.decode('utf-8', errors='ignore')
            else:
                result += part
        
        return result
    
    def _extract_body(self, msg) -> tuple:
        """Extract text and HTML body from email"""
        body_text = ""
        body_html = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                try:
                    body = part.get_payload(decode=True)
                    if body:
                        charset = part.get_content_charset() or 'utf-8'
                        decoded_body = body.decode(charset, errors='ignore')
                        
                        if content_type == "text/plain":
                            body_text += decoded_body
                        elif content_type == "text/html":
                            body_html += decoded_body
                except:
                    continue
        else:
            # Single part message
            content_type = msg.get_content_type()
            try:
                body = msg.get_payload(decode=True)
                if body:
                    charset = msg.get_content_charset() or 'utf-8'
                    decoded_body = body.decode(charset, errors='ignore')
                    
                    if content_type == "text/plain":
                        body_text = decoded_body
                    elif content_type == "text/html":
                        body_html = decoded_body
            except:
                pass
        
        return body_text, body_html
    
    def store_emails(self, emails: List[Dict[str, Any]]) -> int:
        """Store emails in database"""
        if not emails:
            return 0
        
        cursor = self.db_conn.cursor()
        stored_count = 0
        
        for email_data in emails:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO emails 
                    (message_id, from_address, to_address, subject, date, body_text, body_html)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    email_data['message_id'],
                    email_data['from'],
                    email_data['to'],
                    email_data['subject'],
                    email_data['date'],
                    email_data['body_text'],
                    email_data['body_html']
                ))
                
                if cursor.rowcount > 0:
                    stored_count += 1
                    
            except Exception as e:
                logger.error(f"Error storing email: {e}")
        
        self.db_conn.commit()
        return stored_count


# Example usage
def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple Gmail Reader')
    # parser.add_argument('--email', required=True, help='Gmail address')
    # parser.add_argument('--password', required=True, help='Gmail App Password')
    parser.add_argument('--sender', help='Filter by sender')
    parser.add_argument('--subject', help='Filter by subject')
    parser.add_argument('--limit', type=int, default=10, help='Max emails to fetch')
    parser.add_argument('--unread', action='store_true', help='Only unread emails')
    
    args = parser.parse_args()
    
    # Create reader
    reader = GmailReader()
    
    try:
        # Connect and fetch emails
        reader.connect()
        
        emails = reader.get_emails(
            limit=args.limit,
            sender_filter=args.sender,
            subject_filter=args.subject,
            unread_only=args.unread
        )
        
        print(f"Found {len(emails)} emails")
        
        # Store in database
        stored = reader.store_emails(emails)
        print(f"Stored {stored} new emails")
        
        # Display results
        for email in emails:
            print(f"\nFrom: {email['from']}")
            print(f"Subject: {email['subject']}")
            print(f"Date: {email['date']}")
            print("-" * 50)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        reader.disconnect()


if __name__ == "__main__":
    main()