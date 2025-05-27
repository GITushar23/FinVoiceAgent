# /orchestrator/orchestrator.py
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
import httpx
from typing import List, Optional, Dict

app = FastAPI()

RETRIEVER_AGENT_URL = "http://127.0.0.1:8002"
LANGUAGE_AGENT_URL = "http://127.0.0.1:8003"
SCRAPING_AGENT_URL = "http://127.0.0.1:8004"
STT_AGENT_URL = "http://127.0.0.1:8005" # New STT Agent

# Company lookup data (remains the same)
COMPANY_DATA = [
    {"primary_name": "Apple", "symbol": "AAPL", "aliases": ["APPLE INC"]},
    {"primary_name": "TSMC", "symbol": "TSM", "aliases": ["TAIWAN SEMICONDUCTOR MANUFACTURING COMPANY", "TAIWAN SEMICONDUCTOR"]},
    {"primary_name": "Samsung Electronics", "symbol": "005930.KS", "aliases": ["SAMSUNG"]},
    {"primary_name": "Nvidia", "symbol": "NVDA", "aliases": ["NVIDIA CORPORATION"]},
    {"primary_name": "Microsoft", "symbol": "MSFT", "aliases": ["MICROSOFT CORPORATION"]},
]

def extract_company_info_from_query(user_query: str) -> Optional[Dict[str, str]]:
    # ... (function remains the same)
    query_upper = user_query.upper()
    for company in COMPANY_DATA:
        if company["symbol"] in query_upper: return {"name": company["primary_name"], "symbol": company["symbol"]}
        if company["primary_name"].upper() in query_upper: return {"name": company["primary_name"], "symbol": company["symbol"]}
        for alias in company["aliases"]:
            if alias in query_upper: return {"name": company["primary_name"], "symbol": company["symbol"]}
    return None

class OrchestratorTextQueryRequest(BaseModel): # For existing text endpoint
    user_query: str

class ArticleDataForLLM(BaseModel):
    # ... (model remains the same)
    title: Optional[str] = None; url: str; source: Optional[str] = None; lastUpdated: Optional[str] = None
    snippet: Optional[str] = None; summary: Optional[str] = None
    sentiment: Optional[str] = None; impact: Optional[str] = None


# Helper function to run the main brief generation logic
async def generate_brief_from_text_query(user_query: str) -> dict:
    """Handles scraping, RAG, and LLM synthesis based on a text query."""
    print(f"Orchestrator (generate_brief_from_text_query): Processing text query: '{user_query}'")
    
    company_info = extract_company_info_from_query(user_query)
    scraper_search_term = user_query
    if company_info:
        scraper_search_term = f"{company_info['name']} {company_info['symbol']}"
        print(f"Orchestrator: Company identified: {company_info['name']}. Scraper term: '{scraper_search_term}'")
    else:
        print(f"Orchestrator: No specific company. Scraper term: '{scraper_search_term}'")

    summarized_articles_for_llm: List[ArticleDataForLLM] = []
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            scraper_payload = {"query": scraper_search_term, "results_limit": 5, "summary_limit": 3}
            response_scraper = await client.post(f"{SCRAPING_AGENT_URL}/scrape_summarized_news", json=scraper_payload)
            response_scraper.raise_for_status()
            scraped_data_list = response_scraper.json()
            for article_data in scraped_data_list:
                summarized_articles_for_llm.append(ArticleDataForLLM(**article_data))
            print(f"Orchestrator: Scraped {len(summarized_articles_for_llm)} articles.")
    except Exception as e:
        print(f"Orchestrator: Error in scraping step: {str(e)}")
        # Continue, LLM will be informed about missing news

    retrieved_rag_chunks: List[str] = []
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            retriever_payload = {"query": user_query, "top_k": 2}
            response_retriever = await client.post(f"{RETRIEVER_AGENT_URL}/search", json=retriever_payload)
            response_retriever.raise_for_status()
            retrieved_data = response_retriever.json()
            if "results" in retrieved_data:
                retrieved_rag_chunks = [item.get("page_content", "") for item in retrieved_data["results"]]
            print(f"Orchestrator: Retrieved {len(retrieved_rag_chunks)} RAG chunks.")
    except Exception as e:
        print(f"Orchestrator: Error in RAG retrieval: {str(e)}")
        # Continue, LLM will be informed

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            language_payload = {
                "user_query": user_query,
                "retrieved_rag_context": retrieved_rag_chunks,
                "scraped_news_articles": [article.model_dump() for article in summarized_articles_for_llm]
            }
            print(f"Orchestrator: Calling Language Agent with {len(summarized_articles_for_llm)} news articles.")
            response_language = await client.post(f"{LANGUAGE_AGENT_URL}/synthesize", json=language_payload)
            response_language.raise_for_status()
            return response_language.json() # This is the final narrative dict
    except httpx.HTTPStatusError as exc_lang: # Catch specific error from language agent
        detail = exc_lang.response.json().get("detail", exc_lang.response.text) if exc_lang.response.content else str(exc_lang)
        print(f"Orchestrator: Error from Language Agent: {detail}")
        raise HTTPException(status_code=exc_lang.response.status_code, detail=f"Language Agent Error: {detail}")
    except Exception as e_lang: # Catch other errors during language agent call
        print(f"Orchestrator: Unexpected error during Language Agent call: {str(e_lang)}")
        raise HTTPException(status_code=500, detail=f"Synthesis step failed: {str(e_lang)}")


# Existing endpoint for text queries
@app.post("/process_full_brief_query/")
async def process_text_brief_query_endpoint(request: OrchestratorTextQueryRequest):
    user_query = request.user_query
    if not user_query:
        raise HTTPException(status_code=400, detail="No user_query provided.")
    return await generate_brief_from_text_query(user_query)


# New endpoint for voice queries
@app.post("/process_voice_query/")
async def process_voice_query_endpoint(audio_file: UploadFile = File(...)):
    if not audio_file:
        raise HTTPException(status_code=400, detail="No audio file provided.")
    
    print("Orchestrator: Received voice query. Forwarding to STT Agent.")
    
    # 1. Call STT Agent
    transcribed_text = ""
    try:
        # Prepare multipart/form-data for STT agent
        files_for_stt = {'audio_file': (audio_file.filename, await audio_file.read(), audio_file.content_type)}
        async with httpx.AsyncClient(timeout=45.0) as client: # STT can take time
            response_stt = await client.post(f"{STT_AGENT_URL}/transcribe_audio", files=files_for_stt)
            response_stt.raise_for_status()
            stt_data = response_stt.json()
            transcribed_text = stt_data.get("transcribed_text")
            if not transcribed_text or not transcribed_text.strip():
                print("Orchestrator: STT returned empty transcript. Cannot proceed.")
                # You might want to return a specific message to Streamlit here
                # or allow empty string to proceed and let LLM say "I didn't understand"
                # For now, let's raise an error if no text.
                raise HTTPException(status_code=400, detail="Could not understand audio or no speech detected.")
            print(f"Orchestrator: STT successful. Transcribed text: '{transcribed_text}'")
    except httpx.HTTPStatusError as exc_stt:
        detail = exc_stt.response.json().get("detail", exc_stt.response.text) if exc_stt.response.content else str(exc_stt)
        print(f"Orchestrator: Error from STT Agent: {detail}")
        raise HTTPException(status_code=exc_stt.response.status_code, detail=f"STT Agent Error: {detail}")
    except Exception as e_stt:
        print(f"Orchestrator: Error during STT call: {str(e_stt)}")
        raise HTTPException(status_code=500, detail=f"STT processing failed: {str(e_stt)}")

    # 2. Use transcribed text to call the existing brief generation logic
    return await generate_brief_from_text_query(transcribed_text)