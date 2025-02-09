from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, List
import pandas as pd

class DatabaseInterface(ABC):
    @abstractmethod
    def save_trades(self, df: pd.DataFrame) -> None:
        """Save trades to database"""
        pass
    
    @abstractmethod
    def get_trades(self, start_date: datetime, end_date: datetime,
                  symbol: Optional[str] = None) -> pd.DataFrame:
        """Retrieve trades from database"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close database connection"""
        pass
