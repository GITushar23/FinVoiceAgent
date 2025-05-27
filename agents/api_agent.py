# /agents/api_agent.py
import os
from fastapi import FastAPI, HTTPException
import httpx # Using httpx for async requests
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"

app = FastAPI()

async def fetch_stock_data_alphavantage(symbol: str):
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "apikey": ALPHA_VANTAGE_API_KEY,
        "outputsize": "compact" # compact for fewer data points
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(BASE_URL, params=params)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error fetching data from AlphaVantage")
    
    data = response.json()
    
    if "Error Message" in data:
        raise HTTPException(status_code=400, detail=f"AlphaVantage API error: {data['Error Message']}")
    if "Note" in data: # Handles API call frequency limits
        raise HTTPException(status_code=429, detail=f"AlphaVantage API Note: {data['Note']}. You might be over the free tier limit.")
    if "Time Series (Daily)" not in data:
        raise HTTPException(status_code=500, detail=f"Unexpected data format from AlphaVantage for {symbol}. 'Time Series (Daily)' not found.")

    time_series = data["Time Series (Daily)"]
    
    # Get the latest two available dates
    dates = sorted(time_series.keys(), reverse=True)
    if len(dates) < 2:
        raise HTTPException(status_code=404, detail=f"Not enough historical data found for {symbol} to get current and previous day.")
        
    latest_date_str = dates[0]
    previous_date_str = dates[1]
    
    latest_close = time_series[latest_date_str]["4. close"]
    previous_close = time_series[previous_date_str]["4. close"]
    
    return {
        "symbol": symbol,
        "latest_trading_day": latest_date_str,
        "latest_close": latest_close,
        "previous_trading_day": previous_date_str,
        "previous_close": previous_close
    }

@app.get("/stock/{symbol}")
async def get_stock_data(symbol: str):
    """
    Fetches the latest closing price and the previous day's closing price for a given stock symbol.
    Example symbols for Asian tech: 'TSM' (TSMC), '005930.KS' (Samsung on KRX), 'BABA' (Alibaba)
    """
    if not ALPHA_VANTAGE_API_KEY:
        raise HTTPException(status_code=500, detail="AlphaVantage API key not configured.")
    try:
        stock_info = await fetch_stock_data_alphavantage(symbol)
        return stock_info
    except HTTPException as e:
        raise e # Re-raise HTTPException to ensure FastAPI handles it correctly
    except Exception as e:
        # Catch any other unexpected errors during the fetch or processing
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# To run this agent (from the root directory of your project):
# cd agents
# uvicorn api_agent:app --reload --port 8001
#
# Then you can test it in your browser or with curl:
# curl http://127.0.0.1:8001/stock/TSM
# curl http://127.0.0.1:8001/stock/005930.KS 
# (Samsung might require its specific exchange ticker like '005930.KS' for KRX, 
# 'SMSN.IL' for LSE, etc. depending on what AlphaVantage supports well. 
# 'MSFT' or 'NVDA' are good general test cases too if Asian ones give trouble initially.)