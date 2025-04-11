# src/ib_comm/client/web_client.py
import os
import requests
from typing import Dict, Any, Optional, List
import time
from pathlib import Path

class IBKRWebClient:
    def __init__(
        self, 
        base_url: str = "https://localhost:5055/v1/api",
        cert_path: Optional[str] = None,
        account_id: Optional[str] = None
    ):
        """
        Initialize IBKR Web Client
        
        Args:
            base_url: Base URL for the Client Portal API
            cert_path: Path to certificate file (PEM format)
            account_id: IBKR account ID (can be set via IBKR_ACCOUNT_ID env var)
        """
        self.base_url = base_url
        self.cert_path = cert_path or os.getenv('IBKR_CERT_PATH', 'cacert.pem')
        self.account_id = account_id or os.getenv('IBKR_ACCOUNT_ID')
        
        if not self.account_id:
            raise ValueError("Account ID must be provided or set in IBKR_ACCOUNT_ID env var")
            
        if not Path(self.cert_path).exists():
            raise FileNotFoundError(f"Certificate file not found: {self.cert_path}")
            
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """Create a requests session with proper SSL configuration"""
        session = requests.Session()
        session.verify = self.cert_path
        return session
        
    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make a request to the API with proper error handling"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.SSLError as e:
            raise ConnectionError(f"SSL Error: {e}. Check your certificate configuration.")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"API Request failed: {e}")
            
    def get_accounts(self) -> List[Dict]:
        """Get all available accounts"""
        return self._request('GET', 'portfolio/accounts')
        
    def get_account_summary(self) -> Dict:
        """Get account summary"""
        return self._request('GET', f'portfolio/{self.account_id}/summary')
        
    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        return self._request('GET', f'portfolio/{self.account_id}/positions/0') or []
        
    def get_orders(self) -> List[Dict]:
        """Get current orders"""
        response = self._request('GET', 'iserver/account/orders')
        return response.get('orders', [])
        
    def place_order(self, contract_id: int, side: str, quantity: int, 
                   order_type: str = 'LMT', price: Optional[float] = None) -> Dict:
        """Place a new order"""
        data = {
            "orders": [{
                "conid": contract_id,
                "orderType": order_type,
                "quantity": quantity,
                "side": side,
                "tif": "GTC"
            }]
        }
        if price is not None:
            data['orders'][0]['price'] = price
            
        return self._request('POST', f'iserver/account/{self.account_id}/orders', json=data)
        
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an existing order"""
        return self._request('DELETE', f'iserver/account/{self.account_id}/order/{order_id}')
        
    def search_contracts(self, symbol: str, sec_type: str = 'STK') -> List[Dict]:
        """Search for contracts"""
        return self._request('GET', 
                           f'iserver/secdef/search?symbol={symbol}&secType={sec_type}&name=true')
        
    def get_market_history(self, contract_id: int, period: str = '1d', 
                          bar: str = '5min') -> Dict:
        """Get market data history"""
        return self._request('GET', 
                           f'iserver/marketdata/history?conid={contract_id}&period={period}&bar={bar}')
        
    def get_watchlists(self) -> List[Dict]:
        """Get all watchlists"""
        response = self._request('GET', 'iserver/watchlists')
        return response.get('data', {}).get('user_lists', [])
        
    def create_watchlist(self, name: str, symbols: List[str]) -> Dict:
        """Create a new watchlist"""
        # First get contract IDs for symbols
        rows = []
        for symbol in symbols:
            contracts = self.search_contracts(symbol)
            if contracts:
                rows.append({"C": contracts[0]['conid']})
                
        data = {
            "id": int(time.time()),
            "name": name,
            "rows": rows
        }
        
        return self._request('POST', 'iserver/watchlist', json=data)
        
    def delete_watchlist(self, watchlist_id: int) -> None:
        """Delete a watchlist"""
        self._request('DELETE', f'iserver/watchlist?id={watchlist_id}')