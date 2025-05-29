import os
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
from typing import List, Optional, Dict, Any
import base64
from pathlib import Path

app = FastAPI()

# Updated URLs to use the single port with different endpoints
BASE_URL = "https://finvoiceagent.onrender.com"
RETRIEVER_AGENT_URL = f"{BASE_URL}/retriever"
LANGUAGE_AGENT_URL = f"{BASE_URL}/language"
SCRAPING_AGENT_URL = f"{BASE_URL}/scraping"
STT_AGENT_URL = f"{BASE_URL}/stt"
TTS_AGENT_URL = f"{BASE_URL}/tts"

PORTFOLIO_CSV_PATH = Path(__file__).resolve().parent.parent / "data_ingestion" / "mock_portfolio_multi_day_real_companies.csv"


def read_portfolio_csv() -> Optional[str]:
    try:
        if os.path.exists(PORTFOLIO_CSV_PATH):
            with open(PORTFOLIO_CSV_PATH, 'r', encoding='utf-8') as f: 
                return f.read()
        else: 
            print(f"Orchestrator: Portfolio CSV file not found at {PORTFOLIO_CSV_PATH}")
            return None
    except Exception as e: 
        print(f"Orchestrator: Error reading portfolio CSV: {str(e)}")
        return None

class ChatMessage(BaseModel):
    role: str
    content: str

class OrchestratorTextQueryRequest(BaseModel): 
    user_query: str
    chat_history: Optional[List[ChatMessage]] = []

class ArticleDataForLLM(BaseModel):
    title: Optional[str] = None
    url: str
    source: Optional[str] = None
    lastUpdated: Optional[str] = None
    snippet: Optional[str] = None
    summary: Optional[str] = None

class OrchestratorBriefResponse(BaseModel):
    narrative_text: str
    audio_base64: Optional[str] = None

async def get_news_search_keywords_from_llm(user_query: str, client: httpx.AsyncClient) -> str:
    try:
        response = await client.post(f"{LANGUAGE_AGENT_URL}/generate_keywords", json={"user_query": user_query}, timeout=20.0)
        response.raise_for_status()
        keywords_data = response.json()
        return keywords_data.get("keywords", user_query)
    except: 
        return user_query

async def generate_brief_from_text_query(user_query: str, chat_history: Optional[List[ChatMessage]] = None) -> Dict[str, Any]:
    print(f"Orchestrator: Processing text query for brief: '{user_query}'")
    portfolio_csv_content = read_portfolio_csv()
    
    summarized_articles_for_llm: List[ArticleDataForLLM] = []
    scraper_search_term = user_query
    narrative_text_content = "Could not generate a narrative."
    audio_bytes_content = None
    
    async with httpx.AsyncClient() as client:
        scraper_search_term = await get_news_search_keywords_from_llm(user_query, client)
        
        try:
            scraper_payload = {"query": scraper_search_term, "results_limit": 5, "summary_limit": 3}
            response_scraper = await client.post(f"{SCRAPING_AGENT_URL}/scrape_summarized_news", json=scraper_payload, timeout=120.0)
            response_scraper.raise_for_status()
            scraped_data_list = response_scraper.json()
            for article_data in scraped_data_list: 
                summarized_articles_for_llm.append(ArticleDataForLLM(**article_data))
            print(f"Orchestrator: Scraped {len(summarized_articles_for_llm)} articles.")
        except Exception as e: 
            print(f"Orchestrator: Error in scraping step: {str(e)}")
        
        retrieved_rag_chunks: List[str] = []
        try:
            retriever_payload = {"query": user_query, "top_k": 2}
            response_retriever = await client.post(f"{RETRIEVER_AGENT_URL}/search", json=retriever_payload, timeout=20.0)
            response_retriever.raise_for_status()
            retrieved_data = response_retriever.json()
            if "results" in retrieved_data: 
                retrieved_rag_chunks = [item.get("page_content", "") for item in retrieved_data["results"]]
            print(f"Orchestrator: Retrieved {len(retrieved_rag_chunks)} RAG chunks.")
        except Exception as e: 
            print(f"Orchestrator: Error in RAG retrieval: {str(e)}")
        
        try:
            chat_history_for_api = []
            if chat_history:
                for msg in chat_history:
                    chat_history_for_api.append({"role": msg.role, "content": msg.content})
            
            language_payload = {
                "user_query": user_query,
                "chat_history": chat_history_for_api,
                "retrieved_rag_context": retrieved_rag_chunks,
                "scraped_news_articles": [article.model_dump() for article in summarized_articles_for_llm],
                "portfolio_csv_data": portfolio_csv_content
            }
            response_language = await client.post(f"{LANGUAGE_AGENT_URL}/synthesize", json=language_payload, timeout=60.0)
            response_language.raise_for_status()
            narrative_response = response_language.json()
            narrative_text_content = narrative_response.get("narrative", "No narrative generated.")
            print(f"Orchestrator: Received narrative. Length: {len(narrative_text_content)}")
            
            if narrative_text_content and narrative_text_content.strip():
                try:
                    print(f"Orchestrator: Calling TTS Agent for narrative...")
                    tts_payload = {"text": narrative_text_content}
                    audio_response_chunks = []
                    async with client.stream("POST", f"{TTS_AGENT_URL}/synthesize_speech", json=tts_payload, timeout=90.0) as tts_stream_response:
                        tts_stream_response.raise_for_status()
                        async for chunk in tts_stream_response.aiter_bytes():
                            audio_response_chunks.append(chunk)
                    
                    if audio_response_chunks:
                        audio_bytes_content = b"".join(audio_response_chunks)
                        print(f"Orchestrator: Received {len(audio_bytes_content)} audio bytes from TTS Agent.")
                    else:
                        print("Orchestrator: TTS Agent returned no audio data.")
                except httpx.HTTPStatusError as exc_tts_status:
                     print(f"Orchestrator: HTTP error from TTS Agent: {exc_tts_status.response.status_code} - {exc_tts_status.response.text}")
                except Exception as e_tts:
                    print(f"Orchestrator: Error calling TTS Agent: {str(e_tts)}")
            else:
                print("Orchestrator: Narrative text is empty, skipping TTS.")
        
        except httpx.HTTPStatusError as exc_lang:
            detail = exc_lang.response.json().get("detail", exc_lang.response.text)
            raise HTTPException(status_code=exc_lang.response.status_code, detail=f"Language Agent Error: {detail}")
        except Exception as e_lang:
            raise HTTPException(status_code=500, detail=f"Synthesis step failed: {str(e_lang)}")
            
    audio_b64 = base64.b64encode(audio_bytes_content).decode('utf-8') if audio_bytes_content else None
    return {"narrative_text": narrative_text_content, "audio_base64": audio_b64}

@app.post("/process_full_brief_query/", response_model=OrchestratorBriefResponse)
async def process_text_brief_query_endpoint(request: OrchestratorTextQueryRequest):
    user_query = request.user_query
    if not user_query: 
        raise HTTPException(status_code=400, detail="No user_query provided.")
    
    result = await generate_brief_from_text_query(user_query, request.chat_history)
    return OrchestratorBriefResponse(**result)

@app.post("/process_voice_query/", response_model=OrchestratorBriefResponse)
async def process_voice_query_endpoint(audio_file: UploadFile = File(...)):
    if not audio_file: 
        raise HTTPException(status_code=400, detail="No audio file provided.")
    
    transcribed_text = ""
    try:
        files_for_stt = {'audio_file': (audio_file.filename, await audio_file.read(), audio_file.content_type)}
        async with httpx.AsyncClient(timeout=45.0) as client:
            response_stt = await client.post(f"{STT_AGENT_URL}/transcribe_audio", files=files_for_stt)
            response_stt.raise_for_status()
            stt_data = response_stt.json()
            transcribed_text = stt_data.get("transcribed_text")
            if not transcribed_text or not transcribed_text.strip():
                raise HTTPException(status_code=400, detail="Could not understand audio.")
    except Exception as e_stt:
        raise HTTPException(status_code=500, detail=f"STT processing failed: {str(e_stt)}")
    
    result = await generate_brief_from_text_query(transcribed_text)
    return OrchestratorBriefResponse(**result)
