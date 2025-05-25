import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import argparse
import time
import random
import os
from trade_rec import compute_recommendation
from notifications.send_email import EmailSender

def is_market_cap_over_threshold(market_cap_text, threshold_millions=750):
    """
    Check if market cap text (e.g., '1.2B', '800M') is over the threshold.
    
    Args:
        market_cap_text: String like '1.2B' or '800M'
        threshold_millions: Threshold in millions (default 750)
        
    Returns:
        Boolean: True if market cap is over threshold, False otherwise
    """
    try:
        # Clean the text and make uppercase
        market_cap_text = market_cap_text.strip().upper()
        
        # Return False if empty
        if not market_cap_text:
            return False
            
        # Parse value and multiplier
        if market_cap_text.endswith('T'):
            value = float(market_cap_text[:-1]) * 1000000  # Convert to millions
            return value > threshold_millions
        elif market_cap_text.endswith('B'):
            value = float(market_cap_text[:-1]) * 1000  # Convert to millions
            return value > threshold_millions  
        elif market_cap_text.endswith('M'):
            value = float(market_cap_text[:-1])
            return value > threshold_millions
        else:
            # Assume raw number (unlikely but handle it)
            value = float(market_cap_text) / 1000000  # Convert to millions
            return value > threshold_millions
    except:
        # If any error in parsing, return False
        return False
    

def get_earnings_for_date(date_str):
    """
    Get all tickers reporting earnings on a specific date by scraping Yahoo Finance
    
    Args:
        date_str: Date string in format 'YYYY-MM-DD'
    
    Returns:
        DataFrame containing tickers and earnings info for the specified date
    """
    # Convert input date string to required format for URL
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%Y-%m-%d')
        file_date = date_obj.strftime('%Y%m%d')
    except ValueError:
        raise ValueError("Date must be in format 'YYYY-MM-DD'")
    
    # Initialize results list
    all_earnings = []
    offset = 0
    page_count = 0
    max_pages = 30  # Safety limit to prevent infinite loops
    page_size = 25
    # Set headers to mimic browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }
    
    print(f"Fetching earnings data for {formatted_date}. Current time is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Keep fetching data until no more results or max pages reached
    while page_count < max_pages:
        # URL with pagination
        url = f"https://finance.yahoo.com/calendar/earnings?day={formatted_date}&offset={offset}&size={page_size}"
                
        try:
            # Make request with random delay to avoid being blocked
            sleep_time = random.uniform(1, 3)
            print(f"sleeping for a {sleep_time} to avoid being blocked...")
            time.sleep(sleep_time)
            print(f"Fetching page {page_count + 1} (url: {url})...")

            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            print(f"Processing page {page_count + 1} (offset: {offset})...")
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the earnings table - Yahoo may have changed the structure
            # Try different selectors
            tables = soup.find_all('table')
            table = None
            
            if tables:
                # Use the first table that seems to contain earnings data
                for t in tables:
                    # Check if this table has rows with ticker symbols
                    if t.find('a', href=lambda href: href and 'quote' in href):
                        table = t
                        break
            
            if table:
                # Get rows (skip header)
                rows = table.find_all('tr')[1:]
                
                if not rows:
                    print("No more rows found.")
                    break
                
                rows_processed = 0
                
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        # Extract ticker symbol from the first cell
                        symbol_cell = cells[0]
                        symbol_element = symbol_cell.find('a')
                        
                        if symbol_element:
                            symbol = symbol_element.text.strip()
                            
                            # Extract company name
                            company_name = cells[1].text.strip()
                            
                            # Extract additional data if available
                            call_time = cells[2].text.strip() if len(cells) > 2 else ''
                            eps_estimate = cells[3].text.strip() if len(cells) > 3 else ''
                            market_cap_text = cells[7].text.strip() if len(cells) > 7 else ''
                            if not is_market_cap_over_threshold(market_cap_text):
                                print(f"Skipping {symbol} due to market cap: {market_cap_text}")
                                continue  # Skip this company
                            
                            # Add to results
                            all_earnings.append({
                                'Symbol': symbol,
                                'Company': company_name,
                                'Call Time': call_time,
                                'EPS Estimate': eps_estimate,
                                'Market Cap': market_cap_text,
                            })
                            rows_processed += 1
                
                print(f"Processed {rows_processed} rows from page {page_count + 1}")
                
                if rows_processed < page_size:
                    # Less than page_size results, likely the last page
                    break
                
                # Increment offset for next page
                offset += page_size
                page_count += 1
            else:
                print("No earnings table found on page.")
                
                # Check if there's a message indicating no results
                no_results = soup.find(text=lambda text: text and "No results" in text)
                if no_results:
                    print("Page indicates no results available.")
                else:
                    print("Table structure may have changed. Check HTML content.")
                
                break
                
        except Exception as e:
            print(f"Error fetching data: {e}")
            break
    
    # Convert to DataFrame
    df = pd.DataFrame(all_earnings)
    
    if df.empty:
        print(f"No earnings reports found for {formatted_date}")
        return df
        
    print(f"Found {len(df)} companies reporting earnings on {formatted_date}")
    
    # Run compute_recommendation for each symbol
    print("Running trade recommendations analysis...")
    
    # Initialize new columns
    df['avg_volume'] = None
    df['iv30_rv30'] = None
    df['ts_slope_0_45'] = None
    df['expected_move'] = None
    
    # Process each symbol
    for idx, row in df.iterrows():
        symbol = row['Symbol']
        print(f"Processing {symbol} ({idx+1}/{len(df)})...")
        
        try:
            # Make request with random delay to avoid being blocked
            sleep_time = random.uniform(1, 3)
            print(f"sleeping for a {sleep_time} to avoid being blocked...")
            time.sleep(sleep_time)
            recommendation = compute_recommendation(symbol, sleep_time=2)
            
            # If the result is a dictionary, update the dataframe
            if isinstance(recommendation, dict):
                for key, value in recommendation.items():
                    if key in df.columns:
                        df.at[idx, key] = value
            else:
                print(f"Skipping {symbol}: {recommendation}")
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
    
    # Save the full data
    filename = f"data/raw/{file_date}.csv"
    df.to_csv(filename, index=False)
    print(f"Full results saved to {filename}")
    
    # Process recommendations
    print("Processing recommendations...")
    
    # Create rating column
    df['rating'] = None
    
    # Add rating based on criteria
    for idx, row in df.iterrows():
        # Skip rows where ts_slope_0_45 is not True
        if not row['ts_slope_0_45']:
            continue
            
        # Check if at least one of avg_volume or iv30_rv30 is True
        if row['avg_volume'] or row['iv30_rv30']:
            # Check if all three are True
            if row['ts_slope_0_45'] and row['avg_volume'] and row['iv30_rv30']:
                df.at[idx, 'rating'] = "Go"
            else:
                df.at[idx, 'rating'] = "Consider"
    
    # Filter to only include rows with a rating
    filtered_df = df.dropna(subset=['rating'])
    
    if filtered_df.empty:
        print("No recommendations found that meet the criteria.")
        return pd.DataFrame()
    
    # Sort by rating (Go first, then Consider) and expected_move
    # Convert expected_move to numeric for sorting
    # Remove % sign and convert to float
    if 'expected_move' in filtered_df.columns:
        filtered_df['sort_move'] = filtered_df['expected_move'].apply(
            lambda x: float(x.replace('%', '')) if isinstance(x, str) and '%' in x else 0
        )
    else:
        filtered_df['sort_move'] = 0
    
    # Custom sort for rating (Go before Consider)
    filtered_df['rating_sort'] = filtered_df['rating'].apply(lambda x: 0 if x == 'Go' else 1)
    
    # Sort by rating first, then by expected_move in descending order
    filtered_df = filtered_df.sort_values(['rating_sort', 'sort_move'], 
                                         ascending=[True, False])
    
    # Remove sort columns
    filtered_df = filtered_df.drop(['rating_sort', 'sort_move'], axis=1)
    
    # Keep only required columns
    columns_to_keep = ['Symbol', 'Company', 'rating', 'avg_volume', 'iv30_rv30', 'expected_move']
    filtered_df = filtered_df[columns_to_keep]
    
    # Save filtered recommendations
    reco_filename = f"data/reco/reco{file_date}.csv"
    filtered_df.to_csv(reco_filename, index=False)
    print(f"Recommendations saved to {reco_filename}")
    
    return filtered_df

if __name__ == "__main__":
    # Command line argument parsing
    parser = argparse.ArgumentParser(description='Get earnings reports for a specific date')
    parser.add_argument('date', type=str, default=datetime.today().strftime("%Y-%m-%d"), 
                        help='Date in format YYYY-MM-DD')
    
    args = parser.parse_args()
    
    # Get earnings data with recommendations
    earnings_df = get_earnings_for_date(args.date)
    sender = EmailSender()

    # Display results
    if not earnings_df.empty:
        print(f"\n {len(earnings_df)} recommendations made")
        
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