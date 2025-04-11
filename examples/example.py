from datetime import datetime, timedelta
from ib_comm.database import SQLiteDatabase
from ib_comm.client.account import AccountDataClient
from ib_comm.client.market import MarketDataClient

# Initialize database
db = SQLiteDatabase('trades.db')

# Fetch account data
account_client = AccountDataClient(database=db)
trades = account_client.get_executed_trades(
    start_date=datetime.now() - timedelta(days=90)
)
print("Trades:", trades)
account_client.disconnect()

# # Fetch market data
# market_client = MarketDataClient()
# market_data = market_client.get_historical_data(
#     symbol='ES',
#     start_date=datetime.now() - timedelta(days=30),
#     bar_size='1 day'
# )
# print("Market Data:", market_data)
# market_client.disconnect()
