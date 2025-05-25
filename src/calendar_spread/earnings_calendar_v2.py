#!/usr/bin/env python3
"""
Earnings Calendar Script using Finnhub API and ib_async
Replaces the broken Yahoo Finance version
"""

import pandas as pd
from datetime import datetime, timedelta
import argparse
import asyncio
import os
from typing import List, Dict, Optional

# Local imports
from finnhub_client import FinnhubClient
from notifications.send_email import EmailSender
from ib_async import IB, Stock
import logging

logger = logging.getLogger(__name__)


class IBMarketCapFilter:
    """
    Use Interactive Brokers to get market cap data for filtering
    """
    
    def __init__(self):
        self.ib = IB()
        self.connected = False
    
    async def connect(self, host='127.0.0.1', port=7497, clientId=1):
        """Connect to Interactive Brokers"""
        try:
            await self.ib.connectAsync(host, port, clientId)
            self.connected = True
            logger.info("Connected to Interactive Brokers")
        except Exception as e:
            logger.error(f"Failed to connect to IB: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Interactive Brokers"""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
    
    async def get_market_cap(self, symbol: str) -> Optional[float]:
        """
        Get market cap for a symbol in millions USD
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Market cap in millions USD, or None if not available
        """
        if not self.connected:
            return None
        
        try:
            # Create stock contract
            stock = Stock(symbol, 'SMART', 'USD')
            
            # Get contract details
            details = await self.ib.reqContractDetailsAsync(stock)
            if not details:
                return None
            
            # Get fundamental data
            fundamentals = await self.ib.reqFundamentalDataAsync(stock, 'ReportsFinSummary')
            
            if fundamentals:
                # Parse XML to get market cap
                # This is simplified - you may need to parse the XML properly
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(fundamentals)
                    # Look for market cap in the fundamental data
                    # This will depend on the exact structure of IB's fundamental data
                    market_cap_element = root.find('.//MarketCap')
                    if market_cap_element is not None:
                        market_cap = float(market_cap_element.text) / 1_000_000  # Convert to millions
                        return market_cap
                except:
                    pass
            
            # Fallback: calculate market cap from shares outstanding and price
            ticker = self.ib.reqMktData(stock)
            await asyncio.sleep(2)  # Wait for data
            
            price = ticker.last or ticker.close
            if price:
                # Try to get shares outstanding from contract details
                contract_detail = details[0]
                # IB doesn't always provide shares outstanding directly
                # This is a limitation we'll have to work with
                logger.warning(f"Could not get precise market cap for {symbol}, using price: ${price}")
                
            self.ib.cancelMktData(stock)
            return None
            
        except Exception as e:
            logger.error(f"Error getting market cap for {symbol}: {e}")
            return None
    
    async def is_market_cap_over_threshold(self, symbol: str, threshold_millions: float = 750) -> bool:
        """
        Check if market cap is over threshold using IB data
        
        Args:
            symbol: Stock symbol
            threshold_millions: Threshold in millions USD
            
        Returns:
            True if market cap is over threshold, False otherwise
        """
        market_cap = await self.get_market_cap(symbol)
        if market_cap is None:
            # If we can't get market cap, err on the side of inclusion
            logger.warning(f"Could not determine market cap for {symbol}, including in results")
            return True
        
        return market_cap > threshold_millions


class IBTradeRecommendation:
    """
    Trade recommendation logic using ib_async instead of yfinance
    """
    
    def __init__(self, ib_client: IB):
        self.ib = ib_client
    
    async def get_option_data(self, symbol: str) -> Dict:
        """
        Get option chain data from IB
        """
        try:
            stock = Stock(symbol, 'SMART', 'USD')
            
            # Get current stock price
            ticker = self.ib.reqMktData(stock)
            await asyncio.sleep(2)
            
            underlying_price = ticker.last or ticker.close
            if not underlying_price:
                return {'error': f'No price data for {symbol}'}
            
            # Get option chains
            option_chains = await self.ib.reqSecDefOptParamsAsync(stock)
            if not option_chains:
                return {'error': f'No options available for {symbol}'}
            
            # Get 30-day options for IV calculation
            from datetime import datetime, timedelta
            target_date = datetime.now() + timedelta(days=30)
            
            # Find closest expiration to 30 days
            closest_expiry = None
            min_diff = float('inf')
            
            for chain in option_chains:
                for expiry in chain.expirations:
                    expiry_date = datetime.strptime(expiry, '%Y%m%d')
                    diff = abs((expiry_date - target_date).days)
                    if diff < min_diff:
                        min_diff = diff
                        closest_expiry = expiry
            
            if not closest_expiry:
                return {'error': f'No suitable options expiry found for {symbol}'}
            
            # Get ATM strike
            strikes = [s for s in option_chains[0].strikes 
                      if abs(s - underlying_price) / underlying_price < 0.05]  # Within 5%
            
            if not strikes:
                return {'error': f'No ATM strikes found for {symbol}'}
            
            atm_strike = min(strikes, key=lambda x: abs(x - underlying_price))
            
            # Get call and put data
            from ib_async import Option
            call_contract = Option(symbol, closest_expiry, atm_strike, 'C', 'SMART')
            put_contract = Option(symbol, closest_expiry, atm_strike, 'P', 'SMART')
            
            call_ticker = self.ib.reqMktData(call_contract)
            put_ticker = self.ib.reqMktData(put_contract)
            
            await asyncio.sleep(3)  # Wait for option data
            
            # Calculate straddle price and IV
            call_mid = (call_ticker.bid + call_ticker.ask) / 2 if call_ticker.bid and call_ticker.ask else None
            put_mid = (put_ticker.bid + put_ticker.ask) / 2 if put_ticker.bid and put_ticker.ask else None
            
            straddle_price = None
            if call_mid and put_mid:
                straddle_price = call_mid + put_mid
            
            call_iv = getattr(call_ticker, 'impliedVolatility', None)
            put_iv = getattr(put_ticker, 'impliedVolatility', None)
            
            atm_iv = None
            if call_iv and put_iv:
                atm_iv = (call_iv + put_iv) / 2
            
            # Get volume
            volume = ticker.volume or 0
            
            # Cancel subscriptions
            self.ib.cancelMktData(stock)
            self.ib.cancelMktData(call_contract)
            self.ib.cancelMktData(put_contract)
            
            return {
                'underlying_price': underlying_price,
                'volume': volume,
                'straddle_price': straddle_price,
                'atm_iv': atm_iv,
                'expiry': closest_expiry,
                'strike': atm_strike
            }
            
        except Exception as e:
            return {'error': f'Error getting option data for {symbol}: {e}'}
    
    async def get_historical_volatility(self, symbol: str, days: int = 30) -> Optional[float]:
        """
        Get historical volatility using IB historical data
        """
        try:
            stock = Stock(symbol, 'SMART', 'USD')
            
            # Get historical data
            bars = await self.ib.reqHistoricalDataAsync(
                stock,
                endDateTime='',
                durationStr=f'{days*2} D',  # Get more data to ensure we have enough
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True
            )
            
            if len(bars) < days:
                logger.warning(f"Not enough historical data for {symbol}")
                return None
            
            # Calculate Yang-Zhang volatility (simplified version)
            import numpy as np
            closes = [bar.close for bar in bars[-days:]]
            
            if len(closes) < 2:
                return None
            
            returns = np.diff(np.log(closes))
            volatility = np.std(returns) * np.sqrt(252)  # Annualized
            
            return volatility
            
        except Exception as e:
            logger.error(f"Error getting historical volatility for {symbol}: {e}")
            return None
    
    async def compute_recommendation(self, symbol: str) -> Dict:
        """
        Compute trade recommendation using IB data
        """
        try:
            # Get option data
            option_data = await self.get_option_data(symbol)
            
            if 'error' in option_data:
                return option_data
            
            # Get historical volatility
            historical_vol = await self.get_historical_volatility(symbol)
            
            # Calculate metrics
            avg_volume = option_data['volume'] >= 1_500_000
            
            iv30_rv30 = None
            if historical_vol and option_data['atm_iv']:
                iv30_rv30 = option_data['atm_iv'] / historical_vol >= 1.25
            
            # For term structure slope, we'd need multiple expirations
            # Simplified check: assume negative slope if IV is high relative to HV
            ts_slope_negative = iv30_rv30 if iv30_rv30 is not None else False
            
            expected_move = None
            if option_data['straddle_price'] and option_data['underlying_price']:
                expected_move = f"{round(option_data['straddle_price'] / option_data['underlying_price'] * 100, 2)}%"
            
            return {
                'avg_volume': avg_volume,
                'iv30_rv30': iv30_rv30,
                'ts_slope_0_45': ts_slope_negative,
                'expected_move': expected_move
            }
            
        except Exception as e:
            return {'error': f'Error computing recommendation for {symbol}: {e}'}


async def get_earnings_for_date(date_str: str) -> pd.DataFrame:
    """
    Get earnings calendar and recommendations for a specific date
    """
    # Get earnings data from Finnhub
    finnhub_client = FinnhubClient()
    
    # Convert date to required format
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"Fetching earnings data for {date_str} from Finnhub...")
    earnings_df = finnhub_client.get_earnings_calendar(date_str, end_date)
    
    if earnings_df.empty:
        print(f"No earnings data found for {date_str}")
        return pd.DataFrame()
    
    print(f"Found {len(earnings_df)} companies reporting earnings")
    
    # Connect to IB
    market_cap_filter = IBMarketCapFilter()
    await market_cap_filter.connect()
    
    # Filter by market cap
    print("Filtering by market cap...")
    filtered_symbols = []
    for _, row in earnings_df.iterrows():
        symbol = row.get('symbol', '')
        if symbol:
            is_large_cap = await market_cap_filter.is_market_cap_over_threshold(symbol)
            if is_large_cap:
                filtered_symbols.append(symbol)
            else:
                print(f"Filtered out {symbol} due to market cap")
    
    if not filtered_symbols:
        print("No companies passed market cap filter")
        await market_cap_filter.disconnect()
        return pd.DataFrame()
    
    print(f"{len(filtered_symbols)} companies passed market cap filter")
    
    # Run trade recommendations
    print("Running trade recommendation analysis...")
    trade_rec = IBTradeRecommendation(market_cap_filter.ib)
    
    results = []
    for i, symbol in enumerate(filtered_symbols):
        print(f"Processing {symbol} ({i+1}/{len(filtered_symbols)})...")
        
        try:
            recommendation = await trade_rec.compute_recommendation(symbol)
            
            if 'error' not in recommendation:
                # Get company name from original earnings data
                company_row = earnings_df[earnings_df['symbol'] == symbol].iloc[0]
                company_name = company_row.get('name', symbol)
                
                result = {
                    'Symbol': symbol,
                    'Company': company_name,
                    'avg_volume': recommendation.get('avg_volume'),
                    'iv30_rv30': recommendation.get('iv30_rv30'),
                    'ts_slope_0_45': recommendation.get('ts_slope_0_45'),
                    'expected_move': recommendation.get('expected_move')
                }
                results.append(result)
            else:
                print(f"Skipping {symbol}: {recommendation['error']}")
                
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
    
    await market_cap_filter.disconnect()
    
    if not results:
        print("No successful recommendations generated")
        return pd.DataFrame()
    
    # Create DataFrame and add ratings
    results_df = pd.DataFrame(results)
    
    # Add rating logic
    results_df['rating'] = None
    
    for idx, row in results_df.iterrows():
        if not row['ts_slope_0_45']:
            continue
        
        if row['avg_volume'] or row['iv30_rv30']:
            if row['ts_slope_0_45'] and row['avg_volume'] and row['iv30_rv30']:
                results_df.at[idx, 'rating'] = "Go"
            else:
                results_df.at[idx, 'rating'] = "Consider"
    
    # Filter to only rated recommendations
    filtered_df = results_df.dropna(subset=['rating'])
    
    if filtered_df.empty:
        print("No recommendations met the criteria")
        return pd.DataFrame()
    
    # Sort by rating and expected move
    if 'expected_move' in filtered_df.columns:
        filtered_df['sort_move'] = filtered_df['expected_move'].apply(
            lambda x: float(x.replace('%', '')) if isinstance(x, str) and '%' in x else 0
        )
    else:
        filtered_df['sort_move'] = 0
    
    filtered_df['rating_sort'] = filtered_df['rating'].apply(lambda x: 0 if x == 'Go' else 1)
    filtered_df = filtered_df.sort_values(['rating_sort', 'sort_move'], ascending=[True, False])
    
    # Clean up sort columns
    filtered_df = filtered_df.drop(['rating_sort', 'sort_move'], axis=1)
    
    # Keep only required columns
    columns_to_keep = ['Symbol', 'Company', 'rating', 'avg_volume', 'iv30_rv30', 'expected_move']
    filtered_df = filtered_df[columns_to_keep]
    
    # Save results
    file_date = date_obj.strftime('%Y%m%d')
    os.makedirs('data/reco', exist_ok=True)
    reco_filename = f"data/reco/reco{file_date}.csv"
    filtered_df.to_csv(reco_filename, index=False)
    print(f"Recommendations saved to {reco_filename}")
    
    return filtered_df


async def main():
    parser = argparse.ArgumentParser(description='Get earnings reports for a specific date using Finnhub + IB')
    parser.add_argument('date', type=str, default=datetime.today().strftime("%Y-%m-%d"), 
                        help='Date in format YYYY-MM-DD')
    
    args = parser.parse_args()
    
    try:
        earnings_df = await get_earnings_for_date(args.date)
        sender = EmailSender()
        
        if not earnings_df.empty:
            print(f"\n{len(earnings_df)} recommendations made")
            
            sender.send_email_with_inline_df(
                subject=f"Earnings Calendar for {args.date}",
                df=earnings_df
            )
        else:
            print("No recommendations found.")
            sender.send_email(
                subject=f"Earnings Calendar for {args.date}",
                body="No recommendations found for the specified date."
            )
        
        print("Email notification sent.")
        
    except Exception as e:
        print(f"Error: {e}")
        sender = EmailSender()
        sender.send_email(
            subject=f"Earnings Calendar Error for {args.date}",
            body=f"Error occurred: {str(e)}"
        )


if __name__ == "__main__":
    asyncio.run(main())