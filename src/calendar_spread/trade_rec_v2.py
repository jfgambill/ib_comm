from datetime import datetime, timedelta
from scipy.interpolate import interp1d
import numpy as np
import pandas as pd
import pytz

from ib_async import *

def get_daily_price_history(symbol, n_days, ib):
    contract = Stock(symbol, 'SMART', 'USD')

    bars = ib.reqHistoricalData(
        contract=contract, 
        endDateTime="", 
        durationStr=f"{n_days} D", 
        barSizeSetting="1 day", 
        whatToShow="TRADES", 
        useRTH=1, 
        formatDate=1, 
        keepUpToDate=False
    )
    price_data = util.df(bars)
    return price_data

def is_market_hours():
   """Check if current time is between 9:30 AM and 4:00 PM ET."""
   et = pytz.timezone('US/Eastern')
   now = datetime.now(et)
   return now.time() >= datetime.strptime('09:30', '%H:%M').time() and \
          now.time() <= datetime.strptime('16:00', '%H:%M').time()

def yang_zhang(price_data, window=30, trading_periods=252, return_last_only=True):
    """
    
    price_data - df with OHLC values

    """
    # Check for sufficient data
    if len(price_data) < window + 1:
        print(f"Warning: Not enough data for Yang-Zhang calculation. Need {window+1}, got {len(price_data)}")
        return np.nan
        
    # Check for missing data and fill if necessary
    if price_data['high'].isna().any() or price_data['low'].isna().any() or \
       price_data['open'].isna().any() or price_data['close'].isna().any():
        # Fill missing values with forward fill then backward fill
        price_data = price_data.fillna(method='ffill').fillna(method='bfill')

    log_ho = (price_data['high'] / price_data['open']).apply(np.log)
    log_lo = (price_data['low'] / price_data['open']).apply(np.log)
    log_co = (price_data['close'] / price_data['open']).apply(np.log)
    
    log_oc = (price_data['open'] / price_data['close'].shift(1)).apply(np.log)
    log_oc_sq = log_oc**2
    
    log_cc = (price_data['close'] / price_data['close'].shift(1)).apply(np.log)
    log_cc_sq = log_cc**2
    
    rs = log_ho * (log_ho - log_co) + log_lo * (log_lo - log_co)
    
    close_vol = log_cc_sq.rolling(
        window=window,
        center=False
    ).sum() * (1.0 / (window - 1.0))

    open_vol = log_oc_sq.rolling(
        window=window,
        center=False
    ).sum() * (1.0 / (window - 1.0))

    window_rs = rs.rolling(
        window=window,
        center=False
    ).sum() * (1.0 / (window - 1.0))

    k = 0.34 / (1.34 + ((window + 1) / (window - 1)) )
    result = (open_vol + k * close_vol + (1 - k) * window_rs).apply(np.sqrt) * np.sqrt(trading_periods)

    if return_last_only:
        return result.iloc[-1]
    else:
        return result.dropna()

# def build_term_structure(days, ivs):
#     days = np.array(days)
#     ivs = np.array(ivs)

#     sort_idx = days.argsort()
#     days = days[sort_idx]
#     ivs = ivs[sort_idx]


#     spline = interp1d(days, ivs, kind='linear', fill_value="extrapolate")

#     def term_spline(dte):
#         if dte < days[0]:  
#             return ivs[0]
#         elif dte > days[-1]:
#             return ivs[-1]
#         else:  
#             return float(spline(dte))

#     return term_spline

def build_term_structure(days, ivs):
    days = np.array(days)
    ivs = np.array(ivs)

    # Remove duplicates and sort
    unique_data = {}
    for d, iv in zip(days, ivs):
        unique_data[d] = iv  # This automatically handles duplicates by keeping last value
    
    days = np.array(sorted(unique_data.keys()))
    ivs = np.array([unique_data[d] for d in days])
    
    # Need at least 2 points for interpolation
    if len(days) < 2:
        # Return constant function
        constant_iv = ivs[0] if len(ivs) > 0 else 0.2  # fallback to 20% IV
        return lambda dte: constant_iv
    
    # Check for identical values that would cause division by zero
    if np.allclose(days, days[0]):  # All days are the same
        constant_iv = ivs[0]
        return lambda dte: constant_iv
    
    spline = interp1d(days, ivs, kind='linear', fill_value="extrapolate")

    def term_spline(dte):
        if dte < days[0]:  
            return ivs[0]
        elif dte > days[-1]:
            return ivs[-1]
        else:  
            return float(spline(dte))

    return term_spline

def middle_six(lst):
    """
    Take the middle 6 elements from a list.
    If list has < 6 elements, return the original list.
    If list length is odd, remove one extra element from the rear.
    """
    if len(lst) <= 6:
        return lst
    
    # Calculate how many elements to remove from each end
    excess = len(lst) - 6
    front_remove = excess // 2
    back_remove = excess - front_remove  # This handles the odd case
    
    # Slice the list
    return lst[front_remove:len(lst) - back_remove]
    
def compute_recommendation(ticker_symbol, ib):
    try:
        print(f"computing recommendation for {ticker_symbol}")
        stock = Stock(ticker_symbol, 'SMART', 'USD')
        ib.qualifyContracts(stock) # make sure that the contract is valid

        # set data type
        '''
        Market Data Types
        Type	     Code	    Description
        Live	        1	    Real-time streaming data (requires market data subscription).
        Frozen	        2	    Last data recorded at market close (useful when markets are closed).
        Delayed	        3	    Data delayed by 15-20 minutes (for users without live data subscriptions).
        Delayed Frozen	4	    Last available delayed data at market close (for users without live data subscriptions).
        '''
        data_type = 3 if is_market_hours() else 2
        ib.reqMarketDataType(data_type)
        print(f"Market data received for {ticker_symbol}")

        # get 'ticker' and current price of the stock
        ticker = ib.reqTickers(stock)[0]    
        current_price = ticker.marketPrice()    

        # Get options chain
        chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
        print(f"Options chain received for {ticker_symbol}")
        
        # Can display df for debug visualization purposes
        # chains_df = util.df(chains)
        
        # Grab first chain where conditions true
        chain = next(c for c in chains if c.tradingClass == stock.symbol and c.exchange == 'SMART')

        # filter out irrelevant chains
        strikes = middle_six([strike for strike in chain.strikes if 0.8 * current_price < strike < current_price * 1.2])
        today_plus_45 = datetime.today() + timedelta(days=45)
        expirations = sorted(exp for exp in chain.expirations if datetime.strptime(exp, "%Y%m%d") < today_plus_45)
        if len(expirations) < 2:
            raise Exception(f"Can't compute recommendation for {ticker_symbol}. Not enough expirations found: {expirations}")
    
        rights = ['P', 'C']
        
        today = datetime.today().date()
        dtes = []
        ivs = []
        straddle = None 
        for i, expiration in enumerate(expirations):
            print(f"Processing expiration {i+1} of {len(expirations)}: {expiration} for {ticker_symbol}")
            exp_date_obj = datetime.strptime(expiration, "%Y%m%d").date()
            days_to_expiry = (exp_date_obj - today).days
                    
            # find all the calls at the given expiration
            all_calls_exp = [
                Option(ticker_symbol, expiration, strike, 'C', 'SMART', tradingClass=ticker_symbol)
                for strike in strikes
            ]
            # find the call contract that is atm
            atm_strike_idx = (pd.Series([c.strike for c in all_calls_exp]) - current_price).abs().idxmin()
            atm_call_contract = all_calls_exp[atm_strike_idx]
            # build put contract w exp and strike
            atm_put_contract = Option(ticker_symbol, expiration, atm_call_contract.strike, 'P', 'SMART', tradingClass=ticker_symbol)
            
            # fill in all details of the contract including conId
            atm_call_contract = ib.qualifyContracts(atm_call_contract)[0]
            atm_put_contract = ib.qualifyContracts(atm_put_contract)[0]
           
            # compute iv - avg of P and C iv
            '''
            The option greeks are available from the modelGreeks attribute, and if there is a bid, ask resp. 
            last price available also from bidGreeks, askGreeks and lastGreeks. For streaming ticks the greek 
            values will be kept up to date to the current market situation.'''
            atm_call_ticker = ib.reqTickers(atm_call_contract)[0]
            atm_put_ticker = ib.reqTickers(atm_put_contract)[0]
            
            atm_iv_value = (atm_call_ticker.modelGreeks.impliedVol + atm_put_ticker.modelGreeks.impliedVol) / 2.0
            
            if i == 0:
                call_mid = (atm_call_ticker.bid + atm_call_ticker.ask) / 2
                put_mid = (atm_put_ticker.bid + atm_put_ticker.ask) / 2
                straddle = (call_mid + put_mid)
            
            dtes.append(days_to_expiry)
            ivs.append(atm_iv_value)   

        term_spline = interp1d(dtes, ivs, kind='linear', fill_value="extrapolate")
        ts_slope_0_45 = (term_spline(45) - term_spline(dtes[0])) / (45-dtes[0])

        price_data = get_daily_price_history(ticker_symbol, 31, ib)
        realized_vol = yang_zhang(price_data, window=30, trading_periods=252, return_last_only=True)
        iv30_rv30 = term_spline(30) / realized_vol
        avg_volume = price_data['volume'].rolling(30).mean().dropna().iloc[-1]
        expected_move = str(round(straddle / current_price * 100,2)) + "%" if straddle else None
        print("Recommendation computed successfully")
        return {
            'avg_volume': avg_volume >= 1500000, 
            'iv30_rv30': iv30_rv30 >= 1.25, 
            'ts_slope_0_45': ts_slope_0_45 <= -0.00406, 
            'expected_move': expected_move,
            'current_price': current_price,
        }
    except Exception as e:
        print(f"Error processing {ticker_symbol}: {e}")
        return None
    
def main():
    """
    Example usage of the compute_recommendation function
    """
    ib = IB()
    ib.connect('127.0.0.1', 4001, clientId=10) # 4001 is the default port for IB Gateway, 7497 for TWS
    ticker_symbol = 'AAPL'  # Example ticker symbol
    recommendation = compute_recommendation(ticker_symbol, ib)
    if recommendation:
        print(f"Recommendation for {ticker_symbol}: {recommendation}")
    else:
        print(f"Failed to compute recommendation for {ticker_symbol}")