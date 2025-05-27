# /agents/analysis_agent.py
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
import httpx # To call our other agents (API Agent)

app = FastAPI()

# URLs for other agents this agent might need to call
API_AGENT_URL = "http://127.0.0.1:8001" # For fetching stock prices

# --- Mocked Portfolio Data ---
# In a real system, this would come from a database or portfolio management system.
MOCK_PORTFOLIO = {
    "total_aum_yesterday": 1000000.00, # Example total AUM
    "holdings": [
        {"symbol": "TSM", "quantity": 100, "category": "Asia Tech", "avg_cost": 150.0},
        {"symbol": "005930.KS", "quantity": 50, "category": "Asia Tech", "avg_cost": 70000.0}, # Samsung
        {"symbol": "AAPL", "quantity": 70, "category": "US Tech", "avg_cost": 180.0},
        {"symbol": "MSFT", "quantity": 60, "category": "US Tech", "avg_cost": 400.0},
        # Add a non-tech stock for AUM calculation variety
        {"symbol": "JNJ", "quantity": 40, "category": "Healthcare", "avg_cost": 150.0}
    ]
}
# Note: avg_cost isn't strictly needed for allocation % calc but is typical portfolio data.
# We need current and previous day prices to calculate allocation dynamically.

# --- Pydantic Models for Input & Output ---

class StockPriceData(BaseModel):
    symbol: str
    latest_close: float
    previous_close: float

class ScrapedNewsArticle(BaseModel):
    date: Optional[str] = None
    symbol: Optional[str] = None
    title: str
    url: HttpUrl
    source: str = "StockTitan"

class ScrapedDataInput(BaseModel):
    search_query: str
    articles: List[ScrapedNewsArticle] = []
    eps_surprise_percentage: Optional[float] = None # e.g. TSM: 4.0, Samsung: -2.0

class AnalysisRequest(BaseModel):
    # This agent will be triggered by the orchestrator, possibly with specific symbols of interest.
    # For the AUM calculation, it will use its internal MOCK_PORTFOLIO.
    # It might receive scraped data for relevant companies.
    target_symbols_data: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of data objects, each potentially containing API data and Scraped data for a symbol"
    )
    # Example for target_symbols_data:
    # [
    #   {
    #       "symbol": "TSM",
    #       "api_data": {"symbol":"TSM", "latest_close":191.98, "previous_close":196.19},
    #       "scraped_data": {"search_query":"TSMC", "articles": [...], "eps_surprise_percentage": 4.0}
    #   },
    #   // ... for Samsung etc.
    # ]


class PortfolioAllocation(BaseModel):
    current_percentage_aum: float
    yesterday_percentage_aum: float
    change_percentage_points: float # e.g., 4.0 for a 4 percentage point increase

class EarningsSurpriseInfo(BaseModel):
    symbol: str
    description: str # e.g., "TSMC beat estimates by 4.0%" or "Samsung missed by 2.0%"

class AnalysisResponse(BaseModel):
    asia_tech_allocation: Optional[PortfolioAllocation] = None
    earnings_surprises: List[EarningsSurpriseInfo] = []
    key_news_headlines: List[str] = [] # A few relevant headlines
    # 'regional_sentiment_raw_indicators' could be a list of strings/data points
    # that the LLM can use to infer sentiment.
    regional_sentiment_raw_indicators: List[str] = []


async def get_stock_data_from_api_agent(symbol: str) -> Optional[StockPriceData]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_AGENT_URL}/stock/{symbol}")
            response.raise_for_status()
            data = response.json()
            # Ensure the fields match what StockPriceData expects (floats for prices)
            return StockPriceData(
                symbol=data["symbol"],
                latest_close=float(data["latest_close"]),
                previous_close=float(data["previous_close"])
            )
    except Exception as e:
        print(f"AnalysisAgent: Error fetching price for {symbol} from API Agent: {e}")
        return None

@app.post("/analyze_market_data", response_model=AnalysisResponse)
async def analyze_market_data(request: AnalysisRequest = Body(...)):
    """
    Analyzes portfolio data, stock prices, and news to generate insights
    for the morning market brief.
    """
    print(f"AnalysisAgent received request: {request.dict(exclude_none=True)}")

    # 1. Calculate Portfolio Allocation for "Asia Tech"
    current_total_aum = 0.0
    yesterday_total_aum = 0.0
    current_asia_tech_value = 0.0
    yesterday_asia_tech_value = 0.0
    
    # Fetch current and previous prices for all holdings in the mock portfolio
    # This is a bit inefficient if the Orchestrator already fetched some of this for target_symbols_data,
    # but for the sake of isolated AUM calculation within this agent:
    portfolio_holdings_with_prices = []
    for holding in MOCK_PORTFOLIO["holdings"]:
        price_data = await get_stock_data_from_api_agent(holding["symbol"])
        if price_data:
            portfolio_holdings_with_prices.append({**holding, **price_data.dict()})
        else:
            # If price data is missing, we can't accurately calculate AUM.
            # For MVP, we might skip this holding or use a fallback.
            # Here, we'll just print a warning and it won't contribute.
            print(f"AnalysisAgent: Warning - could not get price for {holding['symbol']} for AUM calculation.")
            continue # Skip this holding if no price data

    if not portfolio_holdings_with_prices:
        # If we couldn't get prices for any holdings, AUM calculation isn't possible.
        # This part might need more robust error handling or fallbacks.
        print("AnalysisAgent: Error - No price data for any portfolio holdings. Cannot calculate AUM.")
        # Depending on strictness, could raise HTTPException or return partial response.
        # For now, allocation will be None.
        asia_tech_allocation_result = None
    else:
        for item in portfolio_holdings_with_prices:
            current_value = item["quantity"] * item["latest_close"]
            yesterday_value = item["quantity"] * item["previous_close"]
            
            current_total_aum += current_value
            yesterday_total_aum += yesterday_value
            
            if item["category"] == "Asia Tech":
                current_asia_tech_value += current_value
                yesterday_asia_tech_value += yesterday_value
        
        current_asia_tech_allocation_pct = (current_asia_tech_value / current_total_aum * 100) if current_total_aum > 0 else 0
        yesterday_asia_tech_allocation_pct = (yesterday_asia_tech_value / yesterday_total_aum * 100) if yesterday_total_aum > 0 else 0
        
        asia_tech_allocation_result = PortfolioAllocation(
            current_percentage_aum=round(current_asia_tech_allocation_pct, 2),
            yesterday_percentage_aum=round(yesterday_asia_tech_allocation_pct, 2),
            change_percentage_points=round(current_asia_tech_allocation_pct - yesterday_asia_tech_allocation_pct, 2)
        )

    # 2. Process Earnings Surprises (from the input `target_symbols_data`)
    earnings_surprises_list = []
    key_news_list = []
    
    # Iterate through the data provided by the Orchestrator for key target symbols
    for symbol_data in request.target_symbols_data:
        symbol = symbol_data.get("symbol")
        scraped_data_dict = symbol_data.get("scraped_data", {}) # It's now a dict
        
        # Check for eps_surprise_percentage from the scraping_agent's output for this symbol
        eps_surprise = scraped_data_dict.get("eps_surprise_percentage")

        if eps_surprise is not None and symbol:
            if eps_surprise > 0:
                desc = f"{symbol} beat estimates by {eps_surprise}%"
            elif eps_surprise < 0:
                desc = f"{symbol} missed estimates by {abs(eps_surprise)}%"
            else:
                desc = f"{symbol} met estimates"
            earnings_surprises_list.append(EarningsSurpriseInfo(symbol=symbol, description=desc))

        # Extract some key headlines from the scraped data
        articles = scraped_data_dict.get("articles", [])
        for i, article_dict in enumerate(articles):
            # Take top 1-2 headlines per relevant symbol, or overall top few
            if i < 2 and "earnings" in article_dict.get("title", "").lower(): # Prioritize earnings headlines
                 key_news_list.append(f"{symbol}: {article_dict.get('title')}")
            elif i < 1: # General headline if no earnings specific one
                 key_news_list.append(f"{symbol}: {article_dict.get('title')}")


    # 3. Gather indicators for Regional Sentiment
    # This is simplistic for now. The LLM will do the heavy lifting of interpretation.
    # We can add some of the general news headlines here.
    # Or, if our vector store had "regional sentiment reports", those retrieved chunks would serve this.
    # For now, use a couple of the most general headlines if available from the broader scrape (if any passed)
    regional_sentiment_indicators = []
    if asia_tech_allocation_result: # Simple indicator based on portfolio performance
        if asia_tech_allocation_result.change_percentage_points > 1:
            regional_sentiment_indicators.append("Positive momentum in Asia tech portfolio allocation noted.")
        elif asia_tech_allocation_result.change_percentage_points < -1:
            regional_sentiment_indicators.append("Negative momentum in Asia tech portfolio allocation noted.")

    # Add a couple of broader news headlines if they exist, without symbol prefix if they are general
    # This part assumes the orchestrator might also pass some general news not tied to a specific target symbol.
    # For now, we'll rely on the LLM to synthesize sentiment from all provided info (portfolio, earnings, news).
    # We could also use the `asia_tech_market_overview_may_2025.txt` from our vector store via RAG for this,
    # which the orchestrator should already be doing.
    # So, this agent focuses on quantifiable data and specific news processing.
    # The LLM will combine this with the RAG context for regional sentiment.


    # Consolidate unique headlines (simple approach)
    unique_key_news_list = list(dict.fromkeys(key_news_list))[:3] # Max 3 key headlines

    return AnalysisResponse(
        asia_tech_allocation=asia_tech_allocation_result,
        earnings_surprises=earnings_surprises_list,
        key_news_headlines=unique_key_news_list,
        regional_sentiment_raw_indicators=regional_sentiment_indicators
    )

# To run this agent (from the root directory of your project):
# cd agents
# uvicorn analysis_agent:app --reload --port 8005
#
# Example curl (Orchestrator would construct this payload):
# curl -X POST -H "Content-Type: application/json" -d '{
#   "target_symbols_data": [
#     {
#       "symbol": "TSM",
#       "api_data": {"symbol":"TSM", "latest_close":191.98, "previous_close":196.19},
#       "scraped_data": {
#         "search_query":"TSMC",
#         "articles": [{"date":"05/20/2025", "symbol":"TSM", "title":"TSMC reports stellar earnings again", "url":"http://example.com/tsmc", "source":"StockTitan"}],
#         "eps_surprise_percentage": 4.0
#       }
#     },
#     {
#       "symbol": "005930.KS",
#       "api_data": {"symbol":"005930.KS", "latest_close":75000, "previous_close":76000},
#       "scraped_data": {
#         "search_query":"Samsung",
#         "articles": [{"date":"05/19/2025", "symbol":"005930.KS", "title":"Samsung faces chip challenges", "url":"http://example.com/samsung", "source":"StockTitan"}],
#         "eps_surprise_percentage": -2.0
#       }
#     }
#   ]
# }' http://127.0.0.1:8005/analyze_market_data