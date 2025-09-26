import requests
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import json

def get_fresh_token():
    """Get fresh token by intercepting browser requests."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--user-data-dir=/tmp/chrome_profile")  # Persist login

    # Enable logging to capture network requests
    chrome_options.add_argument("--enable-logging")
    chrome_options.add_argument("--log-level=0")
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Go to the earnings page
        driver.get("https://oquants.com/dashboard/earnings")
        
        # Get network logs
        logs = driver.get_log("performance")
        
        # Look for the API request
        for log in logs:
            message = json.loads(log["message"])
            if message["message"]["method"] == "Network.requestWillBeSent":
                url = message["message"]["params"]["request"]["url"]
                if "earnings-calendar" in url:
                    headers = message["message"]["params"]["request"]["headers"]
                    if "Authorization" in headers:
                        return headers["Authorization"].replace("Bearer ", "")
        
        return None
        
    finally:
        driver.quit()

def get_earnings_calendar():
    """Get earnings calendar with fresh token."""
    print("Make sure you are logged in to Oquants in your browser before running this script.")
    token = get_fresh_token()
    if not token:
        raise Exception("Could not get fresh token")

    url = "https://api.oquants.com/api/v1/dashboard/earnings/earnings-calendar"
    headers = {
        'Authorization': f'Bearer {token}',
        'Referer': 'https://oquants.com/',
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0'
    }

    response = requests.get(url, headers=headers)
    json_response = response.json()
    if not response.ok or 'data' not in json_response:
        raise Exception(f"Failed to fetch earnings calendar: {json_response.get('message', 'Unknown error')}")
    return pd.json_normalize(json_response['data']['earnings_calendar'])

if __name__ == "__main__":
    try:
        earnings_calendar_df = get_earnings_calendar()
        if earnings_calendar_df.empty:
            print("No earnings data found.")
        else:
            earnings_calendar_df.to_csv("data/oquants_earnings_calendar.csv", index=False)
            print(f"Successfully fetched and saved {len(earnings_calendar_df)} earnings records to 'data/oquants_earnings_calendar.csv'")
    except Exception as e:
        print(f"Error: {e}")