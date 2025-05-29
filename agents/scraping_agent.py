import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import httpx
from typing import List, Optional
import asyncio
from dotenv import load_dotenv

load_dotenv() # To load environment variables if you store the API key there

app = FastAPI()

SCRAPINGDOG_API_KEY = os.getenv("SCRAPINGDOG_API_KEY")
GOOGLE_NEWS_API_URL = "https://api.scrapingdog.com/google_news"
SCRAPE_API_URL = "https://api.scrapingdog.com/scrape"

REQUEST_TIMEOUT = 45.0 

class ScrapeRequest(BaseModel):
    query: str
    results_limit: int = 10 # How many initial news results to fetch
    summary_limit: int = 4  # How many of those to summarize

class InitialNewsArticle(BaseModel):
    title: Optional[str] = None
    snippet: Optional[str] = None
    source: Optional[str] = None
    lastUpdated: Optional[str] = None # Note: JSON uses 'lastUpdated', Python prefers 'last_updated'
    url: HttpUrl # Pydantic will validate this is a URL

class SummarizedNewsArticle(InitialNewsArticle):
    summary: Optional[str] = None

# --- Helper Functions ---
async def fetch_initial_news_list(query: str, results_limit: int, client: httpx.AsyncClient) -> List[InitialNewsArticle]:
    """Fetches a list of news articles from ScrapingDog Google News API."""
    params = {
        "api_key": SCRAPINGDOG_API_KEY,
        "query": query,
        "results": results_limit,
        "country": "us", # As per your example
        "page": 0
    }
    try:
        print(f"ScrapingAgent: Fetching initial news list for query: '{query}'")
        response = await client.get(GOOGLE_NEWS_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()
        
        articles = []
        if "news_results" in data and isinstance(data["news_results"], list):
            for item in data["news_results"]:
                try:
                    # Ensure URL is valid before creating Pydantic model
                    if item.get("url"):
                        articles.append(InitialNewsArticle(**item))
                except Exception as e:
                    print(f"ScrapingAgent: Error parsing individual news item: {item}. Error: {e}")
            print(f"ScrapingAgent: Successfully fetched {len(articles)} initial articles.")
            return articles
        else:
            print(f"ScrapingAgent: 'news_results' not found or not a list in API response. Response: {data}")
            return []
    except httpx.HTTPStatusError as e:
        print(f"ScrapingAgent: HTTP error fetching initial news list: {e.response.status_code} - {e.response.text}")
        return []
    except httpx.RequestError as e:
        print(f"ScrapingAgent: Request error fetching initial news list: {e}")
        return []
    except Exception as e: # Catch-all for other errors like JSON decoding
        print(f"ScrapingAgent: Unexpected error fetching initial news list: {e}")
        return []

async def fetch_article_summary(article_url: str, client: httpx.AsyncClient) -> Optional[str]:
    """Fetches an AI-generated summary for a given article URL using ScrapingDog."""
    params = {
        'api_key': SCRAPINGDOG_API_KEY,
        'url': article_url,
        'dynamic': 'false', # As per your example, set to 'true' if JS rendering is needed
        'ai_query': 'Please provide a detailed summary of the news article, including all the key points, background context, and any important developments. Ensure that the summary is written in a comprehensive and descriptive manner, capturing the full scope of the story. Additionally, include the overall emotional tone or sentiment conveyed by the news—such as whether it is optimistic, tragic, alarming, hopeful, neutral, etc.—and explain why that emotion is appropriate based on the content.'
    }
    try:
        print(f"ScrapingAgent: Fetching summary for URL: {article_url}")
        response = await client.get(SCRAPE_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        # The response.text here *is* the summary based on your example.
        # If it were JSON, you'd use response.json().get("summary_field_name")
        summary = response.text 
        print(f"ScrapingAgent: Successfully fetched summary for {article_url[:50]}...")
        return summary.strip() if summary else None
    except httpx.HTTPStatusError as e:
        print(f"ScrapingAgent: HTTP error fetching summary for {article_url}: {e.response.status_code} - {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"ScrapingAgent: Request error fetching summary for {article_url}: {e}")
        return None
    except Exception as e:
        print(f"ScrapingAgent: Unexpected error fetching summary for {article_url}: {e}")
        return None

@app.post("/scrape_summarized_news", response_model=List[SummarizedNewsArticle])
async def scrape_news_and_summarize(request: ScrapeRequest):
    if not SCRAPINGDOG_API_KEY:
        raise HTTPException(status_code=500, detail="ScrapingDog API key not configured.")
    if not request.query:
        raise HTTPException(status_code=400, detail="A search query must be provided.")

    async with httpx.AsyncClient() as client:
        initial_articles = await fetch_initial_news_list(request.query, request.results_limit, client)

        if not initial_articles:
            print(f"ScrapingAgent: No initial articles found for query '{request.query}'. Returning empty list.")
            return []

        articles_to_summarize = initial_articles[:request.summary_limit]
        
        print(f"ScrapingAgent: Attempting to summarize top {len(articles_to_summarize)} articles.")

        summary_tasks = []
        for article_stub in articles_to_summarize:
            summary_tasks.append(fetch_article_summary(str(article_stub.url), client)) # Ensure URL is string

        summaries = await asyncio.gather(*summary_tasks)

        final_articles: List[SummarizedNewsArticle] = []
        for i, article_stub in enumerate(articles_to_summarize):
            summary_content = summaries[i] # This will be None if summarization failed
            summarized_article = SummarizedNewsArticle(
                **article_stub.model_dump(), # Spread fields from InitialNewsArticle
                summary=summary_content
            )
            final_articles.append(summarized_article)
        

        print(f"ScrapingAgent: Processed {len(final_articles)} articles for query '{request.query}'.")
        return final_articles
