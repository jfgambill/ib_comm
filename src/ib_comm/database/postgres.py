import pandas as pd
from datetime import datetime
from typing import Optional
import psycopg2
from psycopg2.extras import execute_values
from .interface import DatabaseInterface

class PostgresDatabase(DatabaseInterface):
    def __init__(self, dbname: str, user: str, password: str,
                 host: str = 'localhost', port: int = 5432):
        """Initialize PostgreSQL database connection"""
        self.conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        self.create_tables()
    
    def create_tables(self) -> None:
        """Create necessary tables if they don't exist"""
        with self.conn.cursor() as cur:
            cur.execute('''
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
            # Create indices
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_trades_date 
                ON account_trades(date)
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_trades_symbol 
                ON account_trades(symbol)
            ''')
        self.conn.commit()
    
    def save_trades(self, df: pd.DataFrame) -> None:
        """Save trades to database"""
        if df.empty:
            return
            
        # Convert DataFrame to list of tuples
        data = [tuple(x) for x in df.to_numpy()]
        
        # Use execute_values for efficient batch insert
        with self.conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO account_trades (
                    execution_id, symbol, date, side, shares,
                    price, order_id, commission, account
                ) VALUES %s
                ON CONFLICT (execution_id) 
                DO UPDATE SET
                    symbol = EXCLUDED.symbol,
                    date = EXCLUDED.date,
                    side = EXCLUDED.side,
                    shares = EXCLUDED.shares,
                    price = EXCLUDED.price,
                    order_id = EXCLUDED.order_id,
                    commission = EXCLUDED.commission,
                    account = EXCLUDED.account
                """,
                data
            )
        self.conn.commit()
        print(f"Saved {len(df)} trades to database")
    
    def get_trades(self, start_date: datetime, end_date: datetime,
                  symbol: Optional[str] = None) -> pd.DataFrame:
        """Retrieve trades from database"""
        query = '''
            SELECT * FROM account_trades 
            WHERE date BETWEEN %s AND %s
        '''
        params = [start_date, end_date]
        
        if symbol:
            query += ' AND symbol = %s'
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