import time
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional
import pandas as pd

from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.execution import Execution, ExecutionFilter

from .base import IBKRBaseApp, IBKRBaseClient

class AccountDataApp(IBKRBaseApp):
    """Application for handling account-related data"""
    def __init__(self):
        super().__init__()
        self.trades: List[Dict] = []
        self.data_received = False
        self.lock = Lock()
        
    def execDetails(self, reqId: int, contract: Contract, execution: Execution):
        """Called when execution data is received"""
        with self.lock:
            self.trades.append({
                'symbol': contract.symbol,
                'date': datetime.strptime(execution.time, '%Y%m%d  %H:%M:%S'),
                'side': execution.side,
                'shares': execution.shares,
                'price': execution.price,
                'execution_id': execution.execId,
                'order_id': execution.orderId,
                'commission': execution.commission,
                'account': execution.acctNumber
            })
    
    def execDetailsEnd(self, reqId: int):
        """Called when all execution data has been received"""
        self.data_received = True
        print("Trade data retrieval completed")

class AccountDataClient(IBKRBaseClient):
    """Client for fetching account-related data"""
    def _create_app(self) -> AccountDataApp:
        """Create the account data application instance"""
        return AccountDataApp()
        
    def get_executed_trades(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch executed trades from the account.
        
        Args:
            start_date: Start date for data fetch
            end_date: End date for data fetch (defaults to today)
            use_cache: Whether to check database first before fetching from IBKR
            
        Returns:
            DataFrame containing the trade data
        """
        if end_date is None:
            end_date = datetime.now()
            
        # Check cache first if enabled and database is available
        if use_cache and self.database is not None:
            cached_data = self.database.get_trades(start_date, end_date)
            if not cached_data.empty:
                print("Retrieved trades from cache")
                return cached_data
        
        # Ensure connection
        if self.app is None:
            self.connect()
        
        # Reset data
        self.app.trades = []
        self.app.data_received = False
        
        # Request execution data
        self.app.reqExecutions(1, ExecutionFilter())
        
        # Wait for data
        timeout = 10  # seconds
        start_time = time.time()
        while not self.app.data_received and time.time() - start_time < timeout:
            time.sleep(0.1)
            
        if not self.app.data_received:
            print("Warning: Data retrieval timed out")
            
        # Convert to DataFrame
        df = pd.DataFrame(self.app.trades)
        
        # Filter by date range
        if not df.empty:
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
            df.sort_values('date', ascending=False, inplace=True)
            
            # Save to database if available
            if self.database is not None:
                self.database.save_trades(df)
            
        return df