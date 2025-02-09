# src/ib_comm/client/base.py
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from threading import Thread
import time
from typing import Optional
from ..database.interface import DatabaseInterface

class IBKRBaseApp(EWrapper, EClient):
    """Base application class for IBKR API wrapper/client"""
    def __init__(self):
        EClient.__init__(self, self)
        self.data_received = False
        
    def error(self, reqId: int, errorCode: int, errorString: str):
        """Handle errors from API"""
        print(f'Error {errorCode}: {errorString}')
        
    def nextValidId(self, orderId: int):
        """Callback when connection is successfully established"""
        print('Connected to IBKR')

class IBKRBaseClient:
    """Base client class for IBKR interactions"""
    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 4001,  # Default to live trading port
        client_id: int = 1,
        database: Optional[DatabaseInterface] = None
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.database = database
        self.app = None
        self.thread = None
        
    def connect(self):
        """Establish connection to IBKR"""
        if self.app is not None:
            print("Already connected")
            return
            
        self.app = self._create_app()
        self.app.connect(self.host, self.port, self.client_id)
        
        # Start the socket in a thread
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        time.sleep(1)  # Give time for connection to establish
        
    def disconnect(self):
        """Disconnect from IBKR and cleanup"""
        if self.app is not None:
            self.app.disconnect()
            self.app = None
        if self.database is not None:
            self.database.close()
            
    def _create_app(self) -> IBKRBaseApp:
        """Create the API application instance"""
        return IBKRBaseApp()
        
    def _run_loop(self):
        """Run the API event loop"""
        self.app.run()
        
    @staticmethod
    def create_contract(
        symbol: str,
        sec_type: str = 'STK',
        exchange: str = 'SMART',
        currency: str = 'USD'
    ) -> Contract:
        """Create a contract object"""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.exchange = exchange
        contract.currency = currency
        return contract