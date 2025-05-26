#!/usr/bin/env python3
"""
Gmail SMTP Emailer - Much simpler than AWS SES
No domain required, works immediately
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from typing import Optional

# Import from your credentials
from credentials.keys import GMAIL_ADDRESS, GMAIL_APP_PASSWORD

logger = logging.getLogger(__name__)


class GmailEmailer:
    """
    Email sender using Gmail SMTP
    Much simpler than AWS SES, no domain verification needed
    """
    
    def __init__(self, from_email: str = None):
        """
        Initialize Gmail SMTP client
        
        Args:
            from_email: Gmail address to send from
        """
        self.from_email = from_email or GMAIL_ADDRESS
        self.password = GMAIL_APP_PASSWORD
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        
        logger.info("Gmail SMTP client initialized")
    
    def send_email(self, to_email: str, subject: str, content: str, 
                   content_type: str = "text/plain") -> bool:
        """
        Send a simple email via Gmail
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            content: Email content
            content_type: "text/plain" or "text/html"
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add content
            if content_type == "text/html":
                part = MIMEText(content, 'html')
            else:
                part = MIMEText(content, 'plain')
            
            msg.attach(part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.from_email, self.password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    def send_email_with_dataframe(self, to_email: str, subject: str, 
                                  df: pd.DataFrame, message: str = "") -> bool:
        """
        Send email with DataFrame as HTML table
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            df: Pandas DataFrame to include
            message: Optional message before the table
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Convert DataFrame to HTML
            html_table = df.to_html(index=False, border=1, 
                                   table_id="earnings-table",
                                   classes="table table-striped")
            
            # Create HTML content
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .table {{ border-collapse: collapse; width: 100%; }}
                    .table th, .table td {{ 
                        border: 1px solid #ddd; 
                        padding: 8px; 
                        text-align: left; 
                    }}
                    .table th {{ background-color: #f2f2f2; }}
                    .table-striped tbody tr:nth-child(odd) {{ 
                        background-color: #f9f9f9; 
                    }}
                </style>
            </head>
            <body>
                {f'<p>{message}</p>' if message else ''}
                {html_table}
            </body>
            </html>
            """
            
            # Also create plain text version
            plain_content = message + "\n\n" + df.to_string(index=False) if message else df.to_string(index=False)
            
            # Create multipart message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add both parts
            part1 = MIMEText(plain_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.from_email, self.password)
                server.send_message(msg)
            
            logger.info(f"DataFrame email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending DataFrame email: {e}")
            return False


# Test function
def test_gmail_emailer():
    """Test Gmail SMTP functionality"""
    print("Testing Gmail SMTP Emailer...")
    
    emailer = GmailEmailer()
    
    # Test 1: Simple email
    success = emailer.send_email(
        to_email="john.gambill@protonmail.com",
        subject="Test Email from Gmail SMTP",
        content="This should work immediately!"
    )
    print(f"Simple email: {'✓ SUCCESS' if success else '✗ FAILED'}")
    
    # Test 2: DataFrame email
    test_df = pd.DataFrame({
        'Symbol': ['AAPL', 'MSFT'],
        'Rating': ['Go', 'Consider'],
        'Expected Move': ['3.2%', '2.1%']
    })
    
    success = emailer.send_email_with_dataframe(
        to_email="john.gambill@protonmail.com",
        subject="DataFrame Test from Gmail SMTP",
        df=test_df,
        message="Testing DataFrame email via Gmail:"
    )
    print(f"DataFrame email: {'✓ SUCCESS' if success else '✗ FAILED'}")


if __name__ == "__main__":
    test_gmail_emailer()