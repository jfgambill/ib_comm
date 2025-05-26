"""
API Keys and Credentials
"""

# Read from your CSV file
import pandas as pd
import os

def load_keys_from_csv():
    """Load keys from CSV file"""
    csv_path = os.path.join(os.path.dirname(__file__), 'keys.csv')
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        # Assuming CSV has columns: key_name, key_value
        keys = dict(zip(df['key'], df['value']))
        return keys
    return {}

keys = load_keys_from_csv()

# Extract individual keys
FINNHUB_API_KEY = keys.get('FINNHUB_API_KEY')
AWS_ACCESS_KEY_ID = keys.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = keys.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = keys.get('AWS_REGION', 'us-east-2')
TWILIO_ACCOUNT_SID = keys.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = keys.get('TWILIO_AUTH_TOKEN')