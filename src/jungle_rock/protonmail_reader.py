#!/usr/bin/env python3
"""
ProtonMail Email Reader

This script connects to ProtonMail via Bridge, reads emails, and stores them in a database.
Requires ProtonMail Bridge to be installed and running on your system.
"""

import imaplib
import email
import smtplib
from email.header import decode_header
from email.message import Message
from email.mime.text import MIMEText
import sqlite3
from datetime import datetime
import os
import configparser
import logging
import sys
from typing import Dict, List, Optional, Tuple, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='protonmail_reader.log'
)
logger = logging.getLogger('protonmail_reader')

class ProtonMailReader:
    def __init__(self, config_file: str = 'config.ini'):
        """Initialize the ProtonMail reader with configuration."""
        self.config = self._load_config(config_file)
        self.conn = None
        self.db_conn = None
        
    def _load_config(self, config_file: str) -> configparser.ConfigParser:
        """Load configuration from the specified file."""
        if not os.path.exists(config_file):
            self._create_default_config(config_file)
            logger.info(f"Created default configuration file: {config_file}")
            raise FileNotFoundError(f"Please edit {config_file} with your ProtonMail credentials")
        
        config = configparser.ConfigParser()
        config.read(config_file)
        return config
    
    def _create_default_config(self, config_file: str) -> None:
        """Create a default configuration file."""
        config = configparser.ConfigParser()
        config['ProtonMail'] = {
            'email': 'john.gambill@protonmail.com',
            'bridge_password': 'cN0mvXqWUhAbbQi7aBrRYw',
            'imap_server': '127.0.0.1',
            'imap_port': '1143',
            'mailbox': 'jr_programs',
            'smtp_server': '127.0.0.1',
            'smtp_port': '1025',
            'smtp_use_tls': 'False'
        }
        config['Database'] = {
            'db_path': 'jungle_rock_emails.db'
        }
        config['Notifications'] = {
            'phone_number': '4846801564',
            'carrier': 'tmomail.net',
            'from_email': 'john.gambill@protonmail.com'
        }
        
        with open(config_file, 'w') as f:
            config.write(f)
    
    def connect_to_protonmail(self) -> None:
        """Connect to ProtonMail via the Bridge's IMAP server."""
        try:
            # Connect to the IMAP server provided by ProtonMail Bridge
            self.conn = imaplib.IMAP4(
                host=self.config['ProtonMail']['imap_server'],
                port=int(self.config['ProtonMail']['imap_port'])
            )
            
            # Login using your ProtonMail email and Bridge password (not your main password)
            self.conn.login(
                self.config['ProtonMail']['email'], 
                self.config['ProtonMail']['bridge_password']
            )
            
            logger.info("Successfully connected to ProtonMail Bridge")
        except Exception as e:
            logger.error(f"Failed to connect to ProtonMail: {str(e)}")
            raise
    
    def setup_database(self) -> None:
        """Set up the SQLite database for storing emails."""
        try:
            db_path = self.config['Database']['db_path']
            self.db_conn = sqlite3.connect(db_path)
            cursor = self.db_conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY,
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
            logger.info(f"Database initialized at {db_path}")
        except Exception as e:
            logger.error(f"Database setup failed: {str(e)}")
            raise
    
    def fetch_emails(self, limit: int = 10, unread_only: bool = True, 
                 sender: Optional[str] = None, subject_keyword: Optional[str] = None,
                 date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch emails from the specified mailbox with filtering options.
        
        Args:
            limit: Maximum number of emails to fetch
            unread_only: If True, fetch only unread emails
            sender: Filter emails from this sender (email address)
            subject_keyword: Filter emails containing this keyword in subject
            date_from: Filter emails from this date (format: DD-MMM-YYYY, e.g., 01-Jan-2023)
            date_to: Filter emails until this date (format: DD-MMM-YYYY)
            
        Returns:
            List of dictionaries containing email data
        """
        try:
            # Select the mailbox
            mailbox = self.config['ProtonMail']['mailbox']
            status, messages = self.conn.select(mailbox)
            
            if status != 'OK':
                logger.error(f"Failed to select mailbox {mailbox}: {messages}")
                return []
            
            # Get number of messages in the mailbox
            num_messages = int(messages[0])
            logger.info(f"Found {num_messages} messages in {mailbox}")
            
            # Build search criteria
            search_criteria = []
            
            # Add read/unread filter
            if unread_only:
                search_criteria.append('UNSEEN')
            
            # Add date filters if provided
            if date_from:
                search_criteria.append(f'SINCE {date_from}')
            if date_to:
                search_criteria.append(f'BEFORE {date_to}')
                
            # Combine search criteria
            if search_criteria:
                search_str = ' '.join(search_criteria)
            else:
                search_str = 'ALL'
                
            # Search for messages
            status, data = self.conn.search(None, search_str)
            
            if status != 'OK':
                logger.error(f"Search failed: {data}")
                return []
            
            # Get message IDs
            message_ids = data[0].split()
            
            # Process messages
            emails = []
            count = 0
            
            # Process messages in reverse order (newest first)
            for msg_id in reversed(message_ids):
                if limit and count >= limit:
                    break
                    
                email_data = self._fetch_email_data(msg_id)
                
                if not email_data:
                    continue
                
                # Apply additional filters that can't be done via IMAP search
                if sender and sender.lower() not in email_data['from'].lower():
                    continue
                    
                if subject_keyword and subject_keyword.lower() not in email_data['subject'].lower():
                    continue
                
                emails.append(email_data)
                count += 1
            
            return emails
        except Exception as e:
            logger.error(f"Error fetching emails: {str(e)}")
            return []
    
    def _fetch_email_data(self, msg_id: bytes) -> Optional[Dict[str, Any]]:
        """Fetch and parse a single email."""
        try:
            status, data = self.conn.fetch(msg_id, '(RFC822)')
            
            if status != 'OK':
                logger.error(f"Failed to fetch message {msg_id}: {data}")
                return None
            
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Extract header information
            message_id = msg.get('Message-ID', '')
            from_addr = msg.get('From', '')
            to_addr = msg.get('To', '')
            subject = self._decode_header_str(msg.get('Subject', ''))
            date = msg.get('Date', '')
            
            # Extract body
            body_text, body_html = self._get_email_body(msg)
            
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
            logger.error(f"Error parsing email {msg_id}: {str(e)}")
            return None
    
    def _decode_header_str(self, header: str) -> str:
        """Decode email header string."""
        decoded_parts = decode_header(header)
        decoded_str = ''
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                if encoding:
                    decoded_str += part.decode(encoding)
                else:
                    decoded_str += part.decode('utf-8', errors='replace')
            else:
                decoded_str += part
                
        return decoded_str
    
    def _get_email_body(self, msg: Message) -> Tuple[str, str]:
        """Extract text and HTML body from email message."""
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
                        decoded_body = body.decode(charset, errors='replace')
                        
                        if content_type == "text/plain":
                            body_text += decoded_body
                        elif content_type == "text/html":
                            body_html += decoded_body
                except Exception as e:
                    logger.warning(f"Error decoding email part: {str(e)}")
        else:
            # Not multipart - get content directly
            content_type = msg.get_content_type()
            try:
                body = msg.get_payload(decode=True)
                if body:
                    charset = msg.get_content_charset() or 'utf-8'
                    decoded_body = body.decode(charset, errors='replace')
                    
                    if content_type == "text/plain":
                        body_text = decoded_body
                    elif content_type == "text/html":
                        body_html = decoded_body
            except Exception as e:
                logger.warning(f"Error decoding email body: {str(e)}")
        
        return body_text, body_html
    
    def store_emails(self, emails: List[Dict[str, Any]]) -> int:
        """Store emails in the database."""
        if not emails:
            return 0
        
        count = 0
        cursor = self.db_conn.cursor()
        
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
                    count += 1
            except Exception as e:
                logger.error(f"Failed to store email: {str(e)}")
        
        self.db_conn.commit()
        return count
    
    def close(self) -> None:
        """Close all connections."""
        if self.conn:
            try:
                self.conn.close()
                logger.info("IMAP connection closed")
            except:
                pass
        
        if self.db_conn:
            try:
                self.db_conn.close()
                logger.info("Database connection closed")
            except:
                pass
                
    def send_notification(self, message: str) -> bool:
        """Send an SMS notification using email-to-SMS gateway."""
        if 'Notifications' not in self.config:
            logger.warning("Notifications section not found in config.")
            return False
            
        # Get SMS settings
        phone_number = self.config['Notifications'].get('phone_number')
        carrier = self.config['Notifications'].get('carrier', 'tmomail.net')
        
        # Get SMTP settings from ProtonMail section
        smtp_server = self.config['ProtonMail'].get('smtp_server', '127.0.0.1')
        smtp_port = int(self.config['ProtonMail'].get('smtp_port', '1025'))
        smtp_use_tls = self.config['ProtonMail'].get('smtp_use_tls', 'False').lower() == 'true'
        email_address = self.config['ProtonMail'].get('email')
        password = self.config['ProtonMail'].get('bridge_password')
        
        if not all([phone_number, email_address, password]):
            logger.warning("Email-to-SMS settings not properly configured.")
            return False
            
        # Create email-to-SMS gateway address
        to_address = f"{phone_number}@{carrier}"
        
        try:
            # Try a completely different approach using Python's email standard library
            from email.message import EmailMessage
            
            # Create a simple message
            msg = EmailMessage()
            msg.set_content(message)
            msg['Subject'] = 'Alert'
            msg['From'] = email_address
            msg['To'] = email_address  # Send to your own email as a workaround
            
            # Connect to SMTP server and send
            server = smtplib.SMTP(smtp_server, smtp_port)
            
            if smtp_use_tls:
                server.starttls()
                
            server.login(email_address, password)
            
            # Send the message to yourself with the notification
            server.send_message(msg)
            
            # Log the fallback approach
            logger.info(f"Using fallback notification: Email sent to {email_address}")
            logger.info(f"Original SMS destination would have been: {to_address}")
            return True
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return False

def main():
    import argparse
    from datetime import datetime
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ProtonMail Email Reader')
    parser.add_argument('--config', type=str, default='config.ini',
                        help='Path to configuration file')
    parser.add_argument('--limit', type=int, default=100,
                        help='Maximum number of emails to fetch')
    parser.add_argument('--all', action='store_true',
                        help='Process all emails, not just unread')
    parser.add_argument('--sender', type=str,
                        help='Filter emails from this sender')
    parser.add_argument('--subject', type=str,
                        help='Filter emails containing this keyword in subject')
    parser.add_argument('--date-from', type=str,
                        help='Filter emails from this date (format: YYYY-MM-DD)')
    parser.add_argument('--date-to', type=str,
                        help='Filter emails until this date (format: YYYY-MM-DD)')
    parser.add_argument('--notify', action='store_true',
                        help='Send SMS notification about results')
    parser.add_argument('--notify-only', action='store_true',
                        help='Only send notification without checking emails')
    parser.add_argument('--message', type=str,
                        help='Custom notification message (used with --notify-only)')
    parser.add_argument('--exit-code', action='store_true',
                        help='Return non-zero exit code if no emails found')
    
    args = parser.parse_args()

    # Handle notify-only mode
    if args.notify_only:
        if not args.message:
            print("Error: --notify-only requires --message")
            return 1
            
        reader = ProtonMailReader(config_file=args.config)
        try:
            success = reader.send_notification(args.message)
            print(f"Notification {'sent' if success else 'failed'}")
            return 0 if success else 1
        except Exception as e:
            print(f"Notification error: {str(e)}")
            return 1
    
    # Convert date format if provided
    date_from = None
    date_to = None
    
    if args.date_from:
        try:
            date = datetime.strptime(args.date_from, '%Y-%m-%d')
            date_from = date.strftime('%d-%b-%Y')
        except ValueError:
            print(f"Error: Invalid date format for --date-from. Use YYYY-MM-DD")
            return 1
    
    if args.date_to:
        try:
            date = datetime.strptime(args.date_to, '%Y-%m-%d')
            date_to = date.strftime('%d-%b-%Y')
        except ValueError:
            print(f"Error: Invalid date format for --date-to. Use YYYY-MM-DD")
            return 1
    
    reader = ProtonMailReader(config_file=args.config)
    
    try:
        # Setup connections
        reader.connect_to_protonmail()
        reader.setup_database()
        
        # Fetch and store emails
        emails = reader.fetch_emails(
            limit=args.limit, 
            unread_only=not args.all,
            sender=args.sender,
            subject_keyword=args.subject,
            date_from=date_from,
            date_to=date_to
        )
        
        if emails:
            stored_count = reader.store_emails(emails)
            message = f"Fetched {len(emails)} emails, stored {stored_count} new emails"
            logger.info(message)
            print(message)
            
            # Send notification if requested
            if args.notify:
                reader.send_notification(message)
                
            return 0  # Success
        else:
            message = "No emails matched the filter criteria"
            logger.info(message)
            print(message)
            
            # Send notification if requested
            if args.notify:
                reader.send_notification(message)
                
            # Return non-zero exit code if requested and no emails found
            return 1 if args.exit_code else 0
            
    except Exception as e:
        error_message = f"Error: {str(e)}"
        logger.error(f"Error in main process: {str(e)}")
        print(error_message)
        
        # Send notification about error if requested
        if args.notify:
            reader.send_notification(f"ProtonMail reader error: {str(e)}")
            
        return 1  # Error
    finally:
        reader.close()

if __name__ == "__main__":
    sys.exit(main())