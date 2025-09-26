import pandas as pd
from datetime import datetime, timedelta
from ib_async import IB
from trade_rec_v2 import compute_recommendation
from notifications.notifier import GmailEmailer

def main():
    # Read CSV
    df = pd.read_csv("data/oquants_earnings_calendar.csv")
    
    # Convert announcement_date to datetime, then to date
    df['announcement_date'] = pd.to_datetime(df['announcement_date'], format='%Y-%m-%d').dt.date
    
    # Get today
    today = datetime.now().date()
    
    # Calculate BMO date based on day of week
    if today.weekday() == 4:  # Friday (0=Monday, 4=Friday)
        bmo_date = today + timedelta(days=3)  # Monday
        print(f"Today is Friday, looking for BMO on Monday ({bmo_date})")
    else:
        bmo_date = today + timedelta(days=1)  # Tomorrow
        print(f"Looking for BMO tomorrow ({bmo_date})")
    
    print(f"Looking for: Today ({today}) AMC and {bmo_date} BMO")
    
    # Filter tickers
    today_amc = df[(df['announcement_date'] == today) & (df['announcement_time'] == 'amc')]['ticker'].tolist()
    bmo_tickers = df[(df['announcement_date'] == bmo_date) & (df['announcement_time'] == 'bmo')]['ticker'].tolist()
    
    print(f"Today AMC: {today_amc}")
    print(f"{bmo_date} BMO: {bmo_tickers}")
    
    all_tickers = today_amc + bmo_tickers
    
    if not all_tickers:
        print("No tickers found")
        return
    
    print(f"Processing {len(all_tickers)} tickers: {all_tickers}")
    
    # Connect to IB
    ib = IB()
    ib.connect('127.0.0.1', 4001)
    
    results = []
    error_details = {}  # Changed to dict to store error details
    
    # Process each ticker
    for ticker in all_tickers:
        try:
            print(f"Processing {ticker}...")
            result = compute_recommendation(ticker, ib)
            if result:  # Check if result is not None
                result['ticker'] = ticker
                results.append(result)
            else:
                error_details[ticker] = "Unknown error (function returned None)"
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            error_details[ticker] = str(e)
    
    # Disconnect from IB
    ib.disconnect()
    
    # Create results DataFrame
    results_df = pd.DataFrame(results)
    
    # Email results
    emailer = GmailEmailer()
    
    # Build email message with detailed error reporting
    message = f"Earnings recommendations for {today}:\n\nProcessed {len(results)} tickers successfully."
    
    if error_details:
        message += f"\n\nErrors occurred for {len(error_details)} tickers:\n"
        
        # Categorize errors
        insufficient_expirations = []
        other_errors = []
        
        for ticker, error in error_details.items():
            if "Not enough expirations found" in error:
                insufficient_expirations.append(ticker)
            else:
                other_errors.append(f"{ticker}: {error}")
        
        if insufficient_expirations:
            message += f"\n• Insufficient expirations (<2): {', '.join(insufficient_expirations)}"
        
        if other_errors:
            message += f"\n• Other errors:\n"
            for error in other_errors:
                message += f"  - {error}\n"
    
    if not results_df.empty:
        # Reorder columns to put ticker first
        cols = ['ticker'] + [col for col in results_df.columns if col != 'ticker']
        results_df = results_df[cols]
        
        emailer.send_email_with_dataframe(
            to_email="john.gambill@protonmail.com",
            subject=f"Earnings Recommendations - {today}",
            df=results_df,
            message=message
        )
    else:
        error_msg = f"No successful recommendations generated.\n\n{message}"
        
        emailer.send_email(
            to_email="john.gambill@protonmail.com",
            subject=f"Earnings Recommendations - {today} (No Results)",
            content=error_msg
        )
    
    print("Email sent!")

if __name__ == "__main__":
    main()