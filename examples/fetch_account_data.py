from ib_comm.database import SQLiteDatabase
from ib_comm.client import IBKRAccountDataFetcher
from datetime import datetime, timedelta

# Initialize with SQLite
db = SQLiteDatabase('trades.db')
fetcher = IBKRAccountDataFetcher(database=db)

# Fetch trades
start_date = datetime.now() - timedelta(days=30)
trades = fetcher.get_executed_trades(start_date)

# The visualization app can independently access the same database:
db = SQLiteDatabase('trades.db')
trades = db.get_trades(start_date, datetime.now())