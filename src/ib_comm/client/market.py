# src/ib_comm/client/market.py
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import time

from ibapi.common import BarData
from .base import IBKRBaseApp, IBKRBaseClient

class MarketDataApp(IBKRBaseApp):
    """Application for handling market data"""
    def __init__(self):
        super().__init__()
        self.data: List[Dict] = []
        self.data_received = False
        
    def historicalData(self, reqId: int, bar: BarData):
        """Called when historical data is received"""
        try:
            # Try first format (with time)
            date = datetime.strptime(bar.date, '%Y%m%d %H:%M:%S')
        except ValueError:
            try:
                # Try second format (date only)
                date = datetime.strptime(bar.date, '%Y%m%d')
            except ValueError:
                print(f"Warning: Unexpected date format: {bar.date}")
                return

        self.data.append({
            'date': date,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume,
            'average': bar.average,
            'barCount': bar.barCount
        })
        
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Called when all historical data has been received"""
        print("Historical data retrieval completed")
        self.data_received = True

class MarketDataClient(IBKRBaseClient):
    """Client for fetching market data"""
    def _create_app(self) -> MarketDataApp:
        """Create the market data application instance"""
        return MarketDataApp()
        
    def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        bar_size: str = '1 day',
        what_to_show: str = 'TRADES',
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch historical market data for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date for data fetch
            end_date: End date for data fetch (defaults to today)
            bar_size: Size of each bar ('1 day', '1 hour', '5 mins', etc.)
            what_to_show: Type of data ('TRADES', 'MIDPOINT', 'BID', 'ASK', etc.)
            use_cache: Whether to check database first before fetching
            
        Returns:
            DataFrame containing the historical data
        """
        if end_date is None:
            end_date = datetime.now()
            
        # Calculate duration string
        duration = (end_date - start_date).days
        if duration <= 0:
            raise ValueError("End date must be after start date")
        duration_str = f"{duration} D"
        
        # Format end date for API
        end_date_str = end_date.strftime('%Y%m%d %H:%M:%S')
        
        # Ensure connection
        if self.app is None:
            self.connect()
        
        # Create contract
        contract = self.create_contract(symbol)
        
        # Reset data
        self.app.data = []
        self.app.data_received = False
        
        # Request historical data
        self.app.reqHistoricalData(
            reqId=1,
            contract=contract,
            endDateTime=end_date_str,
            durationStr=duration_str,
            barSizeSetting=bar_size,
            whatToShow=what_to_show,
            useRTH=1,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[]  # Empty list for default options
        )
        
        # Wait for data
        timeout = 10  # seconds
        start_time = time.time()
        while not self.app.data_received and time.time() - start_time < timeout:
            time.sleep(0.1)
            
        if not self.app.data_received:
            print("Warning: Data retrieval timed out")
            
        # Convert to DataFrame
        df = pd.DataFrame(self.app.data)
        
        # Filter by date range
        if not df.empty:
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
            df.sort_values('date', inplace=True)
            
        return df