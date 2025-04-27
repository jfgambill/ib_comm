import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import argparse
import time
import random
import os
from trade_rec import compute_recommendation

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
    max_pages = 20  # Safety limit to prevent infinite loops
    
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
    
    print(f"Fetching earnings data for {formatted_date}...")
    
    # Keep fetching data until no more results or max pages reached
    while page_count < max_pages:
        # URL with pagination
        url = f"https://finance.yahoo.com/calendar/earnings?day={formatted_date}&offset={offset}&size=100"
        
        try:
            # Make request with random delay to avoid being blocked
            time.sleep(random.uniform(1, 3))
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
                            
                            # Add to results
                            all_earnings.append({
                                'Symbol': symbol,
                                'Company': company_name,
                                'Call Time': call_time,
                                'EPS Estimate': eps_estimate
                            })
                            rows_processed += 1
                
                print(f"Processed {rows_processed} rows from page {page_count + 1}")
                
                if rows_processed < 100:
                    # Less than 100 results, likely the last page
                    break
                
                # Increment offset for next page
                offset += 100
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
            recommendation = compute_recommendation(symbol)
            
            # If the result is a dictionary, update the dataframe
            if isinstance(recommendation, dict):
                for key, value in recommendation.items():
                    if key in df.columns:
                        df.at[idx, key] = value
            else:
                print(f"Skipping {symbol}: {recommendation}")
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
    
    # Save to CSV with date in filename
    filename = f"{file_date}.csv"
    df.to_csv(filename, index=False)
    print(f"Results saved to {filename}")
    
    return df

if __name__ == "__main__":
    # Command line argument parsing
    parser = argparse.ArgumentParser(description='Get earnings reports for a specific date')
    parser.add_argument('date', type=str, help='Date in format YYYY-MM-DD')
    
    args = parser.parse_args()
    
    # Get earnings data with recommendations
    earnings_df = get_earnings_for_date(args.date)
    
    # Display results
    if not earnings_df.empty:
        # Show relevant columns
        display_cols = ['Symbol', 'Company', 'Call Time', 'avg_volume', 'iv30_rv30', 'ts_slope_0_45', 'expected_move']
        available_cols = [col for col in display_cols if col in earnings_df.columns]
        
        print("\nFirst 10 companies with recommendations:")
        print(earnings_df[available_cols].head(10))