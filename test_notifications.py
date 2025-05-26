#!/usr/bin/env python3
"""
Test script for Gmail SMTP Email and Twilio SMS
"""

import pandas as pd
import sys
import logging
from pathlib import Path

# Add src to path so we can import from notifications
sys.path.append(str(Path(__file__).parent / 'src'))

from notifications.notifier import GmailEmailer, TwilioTexter, Notifier

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_gmail_emailer():
    """Test Gmail SMTP email functionality"""
    print("=" * 50)
    print("TESTING GMAIL EMAILER")
    print("=" * 50)
    
    try:
        emailer = GmailEmailer()
        
        # Test 1: Simple text email
        print("\n1. Testing simple text email...")
        success = emailer.send_email(
            to_email="john.gambill@protonmail.com",
            subject="Test Email from Gmail SMTP",
            content="This is a test email from your Gmail SMTP setup. If you receive this, it's working!"
        )
        print(f"   Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        # Test 2: HTML email
        print("\n2. Testing HTML email...")
        html_content = """
        <html>
        <body>
            <h2>Gmail SMTP Test Email</h2>
            <p>This is an <strong>HTML test email</strong> from your Gmail SMTP setup.</p>
            <p style="color: green;">If you can see this green text, HTML emails are working!</p>
        </body>
        </html>
        """
        success = emailer.send_email(
            to_email="john.gambill@protonmail.com",
            subject="HTML Test Email from Gmail SMTP",
            content=html_content,
            content_type="text/html"
        )
        print(f"   Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        # Test 3: DataFrame email
        print("\n3. Testing DataFrame email...")
        test_df = pd.DataFrame({
            'Symbol': ['AAPL', 'MSFT', 'GOOGL'],
            'Company': ['Apple Inc.', 'Microsoft Corp.', 'Alphabet Inc.'],
            'Price': ['$150.00', '$280.00', '$95.00'],
            'Rating': ['Buy', 'Hold', 'Buy']
        })
        
        success = emailer.send_email_with_dataframe(
            to_email="john.gambill@protonmail.com",
            subject="DataFrame Test Email from Gmail SMTP",
            df=test_df,
            message="This is a test of sending a DataFrame as an HTML table:"
        )
        print(f"   Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        # Test 4: Send to Gmail as well
        print("\n4. Testing email to Gmail...")
        success = emailer.send_email(
            to_email="john.f.gambill@gmail.com",
            subject="Test Email from Gmail SMTP to Gmail",
            content="Testing Gmail SMTP sending to Gmail account. This should definitely work!"
        )
        print(f"   Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
    except Exception as e:
        print(f"   ✗ EMAILER ERROR: {e}")
        return False
    
    return True


def test_twilio_texter():
    """Test Twilio SMS functionality"""
    print("\n" + "=" * 50)
    print("TESTING TWILIO TEXTER")
    print("=" * 50)
    
    try:
        texter = TwilioTexter()
        
        # Test 1: Simple SMS
        print("\n1. Testing simple SMS...")
        success = texter.send_sms(
            to_phone="+14846801564",  # Your phone number
            message="Test SMS from your Twilio setup. If you receive this, SMS is working!"
        )
        print(f"   Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        # Test 2: Earnings summary SMS
        print("\n2. Testing earnings summary SMS...")
        test_df = pd.DataFrame({
            'Symbol': ['AAPL', 'MSFT', 'TSLA'],
            'Company': ['Apple', 'Microsoft', 'Tesla'],
            'rating': ['Go', 'Consider', 'Go']
        })
        
        success = texter.send_earnings_summary(
            to_phone="+14846801564",
            earnings_df=test_df
        )
        print(f"   Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
    except Exception as e:
        print(f"   ✗ TEXTER ERROR: {e}")
        return False
    
    return True


def test_notifier():
    """Test the combined Notifier class"""
    print("\n" + "=" * 50)
    print("TESTING COMBINED NOTIFIER")
    print("=" * 50)
    
    try:
        notifier = Notifier(
            email_to="john.gambill@protonmail.com",
            phone_to="+14846801564"
        )
        
        # Test 1: Earnings results notification
        print("\n1. Testing earnings results notification...")
        test_earnings_df = pd.DataFrame({
            'Symbol': ['AAPL', 'MSFT', 'NVDA', 'TSLA'],
            'Company': ['Apple Inc.', 'Microsoft Corp.', 'NVIDIA Corp.', 'Tesla Inc.'],
            'rating': ['Go', 'Consider', 'Go', 'Consider'],
            'avg_volume': [True, True, False, True],
            'iv30_rv30': [True, False, True, False],
            'expected_move': ['3.2%', '2.1%', '4.8%', '5.5%']
        })
        
        notifier.notify_earnings_results(test_earnings_df, "2025-05-26")
        print("   Result: ✓ COMPLETED (check your email and phone)")
        
        # Test 2: Error notification
        print("\n2. Testing error notification...")
        notifier.notify_error(
            error_message="This is a test error message from your notification system.",
            date_str="2025-05-26"
        )
        print("   Result: ✓ COMPLETED (check your email and phone)")
        
    except Exception as e:
        print(f"   ✗ NOTIFIER ERROR: {e}")
        return False
    
    return True


def main():
    """Run all tests"""
    print("GMAIL SMTP NOTIFICATION SYSTEM TEST")
    print("=" * 70)
    
    # Test Gmail emailer first
    email_success = test_gmail_emailer()
    
    # Only test SMS if email works (to avoid unnecessary charges)
    if email_success:
        input("\nPress Enter to test SMS (this will cost money)...")
        sms_success = test_twilio_texter()
        
        if sms_success:
            input("\nPress Enter to test combined notifier...")
            test_notifier()
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("Check your email (ProtonMail AND Gmail) and phone for test messages!")
    print("=" * 70)


if __name__ == "__main__":
    main()