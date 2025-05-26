#!/usr/bin/env python3
"""
Gmail SMTP Email and Twilio SMS Classes
More reliable than ProtonMail bridge or AWS SES sandbox
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import pandas as pd

# Import API keys from credentials
from credentials.keys import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN

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
            msg['From'] = f"John's Trading Bot <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Reply-To'] = self.from_email
            
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
            
            # Create HTML content with better formatting
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .table {{ border-collapse: collapse; width: 100%; }}
                    .table th, .table td {{ 
                        border: 1px solid #ddd; 
                        padding: 8px; 
                        text-align: left; 
                    }}
                    .table th {{ background-color: #f2f2f2; font-weight: bold; }}
                    .table-striped tbody tr:nth-child(odd) {{ 
                        background-color: #f9f9f9; 
                    }}
                    .message {{ margin-bottom: 20px; color: #333; }}
                </style>
            </head>
            <body>
                <div class="message">
                    <p>Hi John,</p>
                    {f'<p>{message}</p>' if message else ''}
                </div>
                {html_table}
                <br>
                <p>Best regards,<br>Your Trading Bot</p>
            </body>
            </html>
            """
            
            # Also create plain text version
            plain_content = f"""Hi John,

{message + chr(10) + chr(10) if message else ''}{df.to_string(index=False)}

Best regards,
Your Trading Bot"""
            
            # Create multipart message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"John's Trading Bot <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Reply-To'] = self.from_email
            
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


class TwilioTexter:
    """
    SMS sender using Twilio API
    Sign up at: https://www.twilio.com ($15 free credit)
    """
    
    def __init__(self, from_phone: str = None):
        """
        Initialize Twilio client
        
        Args:
            from_phone: Phone number to send from (Twilio phone number)
                       If None, will use first available Twilio number
        """
        try:
            from twilio.rest import Client
            
            self.client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            self.from_phone = from_phone
            
            # If no from_phone specified, get the first Twilio number
            if not self.from_phone:
                phone_numbers = self.client.incoming_phone_numbers.list(limit=1)
                if phone_numbers:
                    self.from_phone = phone_numbers[0].phone_number
                    logger.info(f"Using Twilio number: {self.from_phone}")
                else:
                    raise Exception("No Twilio phone numbers found. Please purchase a number.")
            
            logger.info("Twilio client initialized")
            
        except ImportError:
            raise ImportError("Please install twilio: pip install twilio")
        except Exception as e:
            logger.error(f"Failed to initialize Twilio: {e}")
            raise
    
    def send_sms(self, to_phone: str, message: str) -> bool:
        """
        Send SMS message
        
        Args:
            to_phone: Recipient phone number (format: +1234567890)
            message: Text message content (max 1600 characters)
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Ensure phone number has country code
            if not to_phone.startswith('+'):
                to_phone = '+1' + to_phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
            
            # Truncate message if too long
            if len(message) > 1600:
                message = message[:1597] + "..."
                logger.warning("Message truncated to 1600 characters")
            
            message = self.client.messages.create(
                body=message,
                from_=self.from_phone,
                to=to_phone
            )
            
            logger.info(f"SMS sent successfully to {to_phone}. Message SID: {message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending SMS to {to_phone}: {e}")
            return False
    
    def send_earnings_summary(self, to_phone: str, earnings_df: pd.DataFrame) -> bool:
        """
        Send earnings summary via SMS
        
        Args:
            to_phone: Recipient phone number
            earnings_df: DataFrame with earnings recommendations
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if earnings_df.empty:
                message = "No earnings recommendations found for today."
            else:
                go_stocks = earnings_df[earnings_df['rating'] == 'Go']['Symbol'].tolist()
                consider_stocks = earnings_df[earnings_df['rating'] == 'Consider']['Symbol'].tolist()
                
                message = f"Earnings Recommendations:\n"
                
                if go_stocks:
                    message += f"GO: {', '.join(go_stocks)}\n"
                
                if consider_stocks:
                    message += f"CONSIDER: {', '.join(consider_stocks)}\n"
                
                message += f"\nTotal: {len(earnings_df)} recommendations"
            
            return self.send_sms(to_phone, message)
            
        except Exception as e:
            logger.error(f"Error sending earnings summary: {e}")
            return False


# Enhanced notification class that combines both
class Notifier:
    """
    Combined email and SMS notifications using Gmail SMTP and Twilio
    """
    
    def __init__(self, email_from: str = None, 
                 email_to: str = "john.gambill@protonmail.com",
                 phone_to: str = "+14846801564"):
        """
        Initialize both email and SMS clients
        
        Args:
            email_from: Gmail address to send from (uses GMAIL_ADDRESS from credentials if None)
            email_to: Default email recipient
            phone_to: Default phone number for SMS
        """
        self.emailer = GmailEmailer(email_from)
        self.texter = TwilioTexter()
        self.default_email = email_to
        self.default_phone = phone_to
    
    def notify_earnings_results(self, earnings_df: pd.DataFrame, date_str: str) -> None:
        """
        Send both email and SMS notifications about earnings results
        
        Args:
            earnings_df: DataFrame with earnings recommendations
            date_str: Date string for the earnings
        """
        subject = f"Trading Alert - Earnings Calendar for {date_str}"
        
        # Send email with full DataFrame
        if not earnings_df.empty:
            email_success = self.emailer.send_email_with_dataframe(
                to_email=self.default_email,
                subject=subject,
                df=earnings_df,
                message=f"Found {len(earnings_df)} earnings recommendations for {date_str}:"
            )
        else:
            email_success = self.emailer.send_email(
                to_email=self.default_email,
                subject=subject,
                content=f"""Hi John,

No earnings recommendations found for {date_str}.

Best regards,
Your Trading Bot"""
            )
        
        # Send SMS summary
        sms_success = self.texter.send_earnings_summary(
            to_phone=self.default_phone,
            earnings_df=earnings_df
        )
        
        logger.info(f"Notifications sent - Email: {'✓' if email_success else '✗'}, SMS: {'✓' if sms_success else '✗'}")
    
    def notify_error(self, error_message: str, date_str: str) -> None:
        """
        Send error notifications
        
        Args:
            error_message: Error description
            date_str: Date string for context
        """
        subject = f"Trading Alert - Error for {date_str}"
        
        # Send email
        self.emailer.send_email(
            to_email=self.default_email,
            subject=subject,
            content=f"""Hi John,

An error occurred while processing the earnings calendar for {date_str}:

{error_message}

Please check the system logs for more details.

Best regards,
Your Trading Bot"""
        )
        
        # Send SMS
        self.texter.send_sms(
            to_phone=self.default_phone,
            message=f"Trading bot error for {date_str}: {error_message[:100]}..."
        )


# Example usage
if __name__ == "__main__":
    # Test both services
    notifier = Notifier()
    
    # Test with sample data
    test_df = pd.DataFrame({
        'Symbol': ['AAPL', 'MSFT'],
        'Company': ['Apple Inc.', 'Microsoft Corp.'],
        'rating': ['Go', 'Consider'],
        'expected_move': ['3.2%', '2.8%']
    })
    
    notifier.notify_earnings_results(test_df, "2025-05-26")