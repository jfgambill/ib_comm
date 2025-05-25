#!/usr/bin/env python3
"""
Finnhub API Client
"""

import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
import logging

# Import API key from utils
from credentials.keys import FINNHUB_API_KEY

logger = logging.getLogger(__name__)


class FinnhubClient:
    """
    General client for Finnhub API
    """
    
    def __init__(self):
        self.api_key = FINNHUB_API_KEY
        self.base_url = "https://finnhub.io/api/v1"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        }
    
    def get_earnings_calendar(self, from_date: str, to_date: str) -> pd.DataFrame:
        """
        Get earnings calendar for a date range
        
        Args:
            from_date: Start date in format YYYY-MM-DD
            to_date: End date in format YYYY-MM-DD
            
        Returns:
            DataFrame with earnings calendar data
        """
        url = f"{self.base_url}/calendar/earnings"
        params = {
            'from': from_date,
            'to': to_date,
            'token': self.api_key
        }
        
        try:
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            earnings_data = data.get('earningsCalendar', [])
            
            if earnings_data:
                df = pd.DataFrame(earnings_data)
                logger.info(f"Retrieved {len(df)} earnings records from Finnhub")
                return df
            else:
                logger.warning("No earnings data returned from Finnhub")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error fetching earnings calendar from Finnhub: {e}")
            return pd.DataFrame()
        
def main():
    """
    Example usage of the FinnhubClient
    """
    client = FinnhubClient()
    
    # Example: Get earnings calendar for the next week
    today = datetime.now().strftime('%Y-%m-%d')
    next_week = (datetime.now() + pd.Timedelta(days=7)).strftime('%Y-%m-%d')
    
    earnings_df = client.get_earnings_calendar(today, next_week)
    
    if not earnings_df.empty:
        print(earnings_df.head())
    else:
        print("No earnings data found.")
        
if __name__ == "__main__":
    main()
