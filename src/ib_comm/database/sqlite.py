import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional
from pathlib import Path
from .interface import DatabaseInterface

class SQLiteDatabase(DatabaseInterface):
    def __init__(self, db_path: str = 'trades.db'):
        """Initialize SQLite database with WAL journal mode"""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        # Enable WAL mode for better concurrency
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.create_tables()
    
    def create_tables(self) -> None:
        """Create necessary tables if they don't exist"""
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS account_trades (
                    execution_id TEXT PRIMARY KEY,
                    symbol TEXT,
                    date TIMESTAMP,
                    side TEXT,
                    shares REAL,
                    price REAL,
                    order_id INTEGER,
                    commission REAL,
                    account TEXT
                )
            ''')
            # Create indices for better query performance
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_trades_date 
                ON account_trades(date)
            ''')
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_trades_symbol 
                ON account_trades(symbol)
            ''')
    
    def save_trades(self, df: pd.DataFrame) -> None:
        """Save trades to database"""
        if df.empty:
            return
        
        # Use pandas to_sql with 'replace' to handle duplicates
        df.to_sql('account_trades', self.conn, 
                 if_exists='replace', index=False)
        print(f"Saved {len(df)} trades to database")
    
    def get_trades(self, start_date: datetime, end_date: datetime,
                  symbol: Optional[str] = None) -> pd.DataFrame:
        """Retrieve trades from database"""
        query = '''
            SELECT * FROM account_trades 
            WHERE date BETWEEN ? AND ?
        '''
        params = [start_date, end_date]
        
        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol)
        
        query += ' ORDER BY date DESC'
        
        df = pd.read_sql_query(
            query, 
            self.conn,
            params=params,
            parse_dates=['date']
        )
        return df
    
    def close(self) -> None:
        """Close database connection"""
        self.conn.close()