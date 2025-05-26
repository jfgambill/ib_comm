#!/usr/bin/env python3
"""
SendGrid Email and Twilio SMS Classes
More reliable than ProtonMail bridge
"""

import logging
from typing import Optional
import pandas as pd

# Import API keys from utils
from credentials.keys import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN

logger = logging.getLogger(__name__)

# You'll need to install these packages:
# pip install boto3 twilio


class AWSEmailer:
    """
    Email sender using AWS SES
    AWS SES: $0.10 per 1,000 emails (very cheap)
    """
    
    def __init__(self, from_email: str = "john.gambill@protonmail.com"):
        """
        Initialize AWS SES client
        
        Args:
            from_email: Email address to send from (must be verified in AWS SES)
        """
        try:
            import boto3
            
            self.ses_client = boto3.client(
                'ses',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_REGION
            )
            self.from_email = from_email
            logger.info("AWS SES client initialized")
            
        except ImportError:
            raise ImportError("Please install boto3: pip install boto3")
        except Exception as e:
            logger.error(f"Failed to initialize AWS SES: {e}")
            raise
    
    def send_email(self, to_email: str, subject: str, content: str, 
                   content_type: str = "text/plain") -> bool:
        """
        Send a simple email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            content: Email content
            content_type: "text/plain" or "text/html"
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Prepare email body based on content type
            if content_type == "text/html":
                body = {
                    'Html': {
                        'Charset': 'UTF-8',
                        'Data': content,
                    }
                }
            else:
                body = {
                    'Text': {
                        'Charset': 'UTF-8',
                        'Data': content,
                    }
                }
            
            # Send email using SES
            response = self.ses_client.send_email(
                Destination={
                    'ToAddresses': [to_email],
                },
                Message={
                    'Body': body,
                    'Subject': {
                        'Charset': 'UTF-8',
                        'Data': subject,
                    },
                },
                Source=self.from_email,
            )
            
            logger.info(f"Email sent successfully to {to_email}. Message ID: {response['MessageId']}")
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
            
            # Send with both HTML and plain text using SES
            response = self.ses_client.send_email(
                Destination={
                    'ToAddresses': [to_email],
                },
                Message={
                    'Body': {
                        'Html': {
                            'Charset': 'UTF-8',
                            'Data': html_content,
                        },
                        'Text': {
                            'Charset': 'UTF-8',
                            'Data': plain_content,
                        }
                    },
                    'Subject': {
                        'Charset': 'UTF-8',
                        'Data': subject,
                    },
                },
                Source=self.from_email,
            )
            
            logger.info(f"DataFrame email sent successfully to {to_email}. Message ID: {response['MessageId']}")
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
    Combined email and SMS notifications using AWS SES and Twilio
    """
    
    def __init__(self, email_from: str = "john.gambill@protonmail.com", 
                 email_to: str = "john.gambill@protonmail.com",
                 phone_to: str = "+14846801564"):
        """
        Initialize both email and SMS clients
        
        Args:
            email_from: Email address to send from
            email_to: Default email recipient
            phone_to: Default phone number for SMS
        """
        self.emailer = AWSEmailer(email_from)
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
        subject = f"Earnings Calendar for {date_str}"
        
        # Send email with full DataFrame
        if not earnings_df.empty:
            email_success = self.emailer.send_email_with_dataframe(
                to_email=self.default_email,
                subject=subject,
                df=earnings_df,
                message=f"Found {len(earnings_df)} earnings recommendations for {date_str}"
            )
        else:
            email_success = self.emailer.send_email(
                to_email=self.default_email,
                subject=subject,
                content="No earnings recommendations found for the specified date."
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
        subject = f"Earnings Calendar Error for {date_str}"
        
        # Send email
        self.emailer.send_email(
            to_email=self.default_email,
            subject=subject,
            content=f"Error occurred while processing earnings calendar:\n\n{error_message}"
        )
        
        # Send SMS
        self.texter.send_sms(
            to_phone=self.default_phone,
            message=f"Earnings calendar error for {date_str}: {error_message[:100]}..."
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
    
    notifier.notify_earnings_results(test_df, "2025-05-25")