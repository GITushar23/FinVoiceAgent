# /agents/language_agent.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl # HttpUrl might not be needed if Orchestrator sends string
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
llm = None

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found. LangChain Google LLM will not be initialized.")
else:
    try:
        # MODEL_NAME = "gemini-2.5-flash-preview-05-20"
        MODEL_NAME = "gemini-2.0-flash-lite"
        llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            google_api_key=GEMINI_API_KEY,
            temperature=0.2,
        )
        print(f"LangChain ChatGoogleGenerativeAI model ({MODEL_NAME}) initialized successfully.")
    except Exception as e:
        print(f"Error initializing LangChain ChatGoogleGenerativeAI model: {e}")
        llm = None

app = FastAPI()

# This model should match what Orchestrator sends in "scraped_news_articles"
class ScrapedArticleInput(BaseModel):
    title: Optional[str] = None
    url: str # Expecting string URL from Orchestrator
    source: Optional[str] = None
    lastUpdated: Optional[str] = None
    snippet: Optional[str] = None
    summary: Optional[str] = None # Key new field
    sentiment: Optional[str] = None # Will be None for now
    impact: Optional[str] = None    # Will be None for now

class SynthesisRequest(BaseModel):
    user_query: str
    retrieved_rag_context: List[str]
    scraped_news_articles: List[ScrapedArticleInput] # Use the updated model

class SynthesisResponse(BaseModel):
    narrative: str

def generate_llm_narrative_langchain(
    user_query: str,
    retrieved_rag_context: List[str],
    scraped_news_articles: List[ScrapedArticleInput]
) -> str:
    global llm
    if not llm:
        raise HTTPException(status_code=503, detail="LangChain Google LLM not initialized.")

    rag_context_string = "\n\n".join(retrieved_rag_context)
    
    news_context_parts = []
    if scraped_news_articles:
        news_context_parts.append("Recent News Summaries:")
        for i, article in enumerate(scraped_news_articles, 1): # Already limited by orchestrator
            news_context_parts.append(f"\n--- News Summary {i} ---")
            news_context_parts.append(f"Title: {article.title if article.title else 'N/A'}")
            news_context_parts.append(f"Source: {article.source if article.source else 'N/A'} (Last Updated: {article.lastUpdated if article.lastUpdated else 'N/A'})")
            if article.summary:
                news_context_parts.append(f"Summary: {article.summary}")
            elif article.snippet: # Fallback to snippet if summary is missing
                news_context_parts.append(f"Snippet: {article.snippet}")
            else:
                news_context_parts.append("Content/Summary: Not available.")
            news_context_parts.append(f"URL: {article.url}")
        news_context_parts.append("--- End of News Summaries ---")
    news_context_string = "\n".join(news_context_parts)

    prompt_text = f"""
You are a financial assistant. Your task is to synthesize a concise, well-formatted, and easily readable market brief based on the user's query, relevant background documents, and recent summarized news articles.

User Query: {user_query}

Background Information (from internal documents, if any):
{rag_context_string if rag_context_string else "No specific background documents found for this query."}

{news_context_string if news_context_string else "No recent news summaries were found for this specific query."}

Instructions:
1.  Address the user's query directly using the provided information.
2.  Prioritize information from the "Recent News Summaries." If a summary is available, use that.
3.  Integrate information from background documents if it complements the news or answers parts of the query not covered by news.
4.  Ensure all numbers, currency symbols, and units are clearly written.
5.  Avoid making up information. If the provided context is insufficient, state what you found or indicate that more specific information isn't available from the provided sources.
6.  Present the information clearly and professionally as a market brief.
"""
    messages = [HumanMessage(content=prompt_text)]
    try:
        print(f"LanguageAgent: Constructing prompt. Approx length: {len(prompt_text)} chars.")
        print(f"LanguageAgent: Invoking LLM model '{llm.model}'...")
        response = llm.invoke(messages)
        
        if hasattr(response, 'content') and response.content:
            print("LanguageAgent: Successfully received content from LLM.")
            return response.content
        else:
            print(f"LanguageAgent Error: LLM returned an unexpected response or empty content: {response}")
            raise HTTPException(status_code=500, detail="LLM generated an empty or unreadable response via LangChain.")
    except Exception as e:
        error_type = type(e).__name__
        error_details = str(e)
        log_message = f"LanguageAgent Error during LLM call: {error_type} - {error_details}"
        print(log_message)
        raise HTTPException(status_code=500, detail=f"LLM Error ({error_type}): {error_details}")

@app.post("/synthesize", response_model=SynthesisResponse)
async def synthesize_narrative(request: SynthesisRequest):
    print(f"LanguageAgent: Received /synthesize request. Query: '{request.user_query}', "
          f"{len(request.retrieved_rag_context)} RAG_docs, "
          f"{len(request.scraped_news_articles)} news_articles (with summaries).")
    if not llm:
        raise HTTPException(status_code=503, detail="Language model (LangChain) not initialized.")
    try:
        narrative_text = generate_llm_narrative_langchain(
            request.user_query,
            request.retrieved_rag_context,
            request.scraped_news_articles
        )
        return SynthesisResponse(narrative=narrative_text)
    except HTTPException as e:
        raise e
    except Exception as e:
        error_type = type(e).__name__
        error_details = str(e)
        print(f"LanguageAgent Error in /synthesize endpoint: {error_type} - {error_details}")
        raise HTTPException(status_code=500, detail=f"Unexpected error in LanguageAgent ({error_type}): {error_details}")