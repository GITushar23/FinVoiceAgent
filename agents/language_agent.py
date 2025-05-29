import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage # AIMessage for assistant history
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
llm = None

# MODEL_NAME IS SET AS PER YOUR REQUEST
MODEL_NAME = "gemini-2.0-flash-lite"

if not GEMINI_API_KEY:
    print(f"WARNING: GEMINI_API_KEY not found. LangChain Google LLM ({MODEL_NAME}) will not be initialized.")
else:
    try:
        llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            google_api_key=GEMINI_API_KEY,
            temperature=0.1,
        )
        print(f"LangChain ChatGoogleGenerativeAI model ({MODEL_NAME}) initialized successfully for LanguageAgent.")
    except Exception as e:
        print(f"Error initializing LangChain ChatGoogleGenerativeAI model ({MODEL_NAME}): {e}")
        llm = None

app = FastAPI()

class KeywordGenerationRequest(BaseModel):
    user_query: str
class KeywordGenerationResponse(BaseModel):
    keywords: str

class ScrapedArticleInput(BaseModel):
    title: Optional[str] = None; url: str; source: Optional[str] = None
    lastUpdated: Optional[str] = None; snippet: Optional[str] = None; summary: Optional[str] = None

class ChatMessageInput(BaseModel): # For receiving chat history
    role: str # "user" or "assistant"
    content: str

class SynthesisRequest(BaseModel):
    user_query: str # The current user query
    chat_history: Optional[List[ChatMessageInput]] = [] # Previous turns
    retrieved_rag_context: List[str]
    scraped_news_articles: List[ScrapedArticleInput]
    portfolio_csv_data: Optional[str] = None

class SynthesisResponse(BaseModel):
    narrative: str

@app.post("/generate_keywords", response_model=KeywordGenerationResponse)
async def generate_keywords_for_news_search(request: KeywordGenerationRequest):
    if not llm: raise HTTPException(status_code=503, detail="Language model not initialized.")
    prompt_text = f"""Given the user's financial query: "{request.user_query}" Generate a concise and effective search query string (2 to 5 keywords, including company names or symbols if present) for financial news. Focus on entities, actions, and financial terms. E.g., "Apple AAPL TSMC TSM regulations risk news" or "Nvidia NVDA earnings results". Output ONLY the search query string."""
    messages = [HumanMessage(content=prompt_text)]
    try:
        response = llm.invoke(messages); keywords = response.content.strip()
        print(f"LanguageAgent (/generate_keywords): Generated: '{keywords}' for query: '{request.user_query}'")
        return KeywordGenerationResponse(keywords=keywords)
    except Exception as e: raise HTTPException(status_code=500, detail=f"Failed to generate keywords: {str(e)}")


def generate_llm_narrative_langchain(
    user_query: str,
    chat_history: Optional[List[ChatMessageInput]],
    retrieved_rag_context: List[str],
    scraped_news_articles: List[ScrapedArticleInput],
    portfolio_csv_data: Optional[str]
) -> str:
    global llm
    if not llm:
        raise HTTPException(status_code=503, detail="LangChain Google LLM not initialized.")

    langchain_messages: List[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content="You are a highly capable financial analyst AI. Your task is to generate a concise, data-driven, and professional market brief—no longer than 3–4 lines—based on the user's query, conversation history, and provided information. Be crisp, accurate, and professional.")
    ]
    if chat_history:
        for msg in chat_history:
            if msg.role == "user":
                langchain_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant": # Assuming "assistant" role from history
                langchain_messages.append(AIMessage(content=msg.content))

    rag_context_string = "\n\n".join(retrieved_rag_context)
    news_context_parts = []
    if scraped_news_articles:
        news_context_parts.append("Recent News Summaries (use for current events/sentiment):")
        for i, article in enumerate(scraped_news_articles, 1):
            news_context_parts.append(f"\n--- News {i}: {article.title or 'N/A'} (Source: {article.source or 'N/A'}, Updated: {article.lastUpdated or 'N/A'}) ---")
            if article.summary: news_context_parts.append(f"Summary: {article.summary}")
            elif article.snippet: news_context_parts.append(f"Snippet: {article.snippet}")
    news_context_string = "\n".join(news_context_parts)

    portfolio_info_string = ""
    if portfolio_csv_data:
        portfolio_info_string = f"\nPortfolio Data (raw CSV - interpret for holdings/context):\n<csv>\n{portfolio_csv_data}\n</csv>\n"
    
    current_turn_prompt_content = f"""
User's Current Query: "{user_query}"

{portfolio_info_string if portfolio_info_string else "No portfolio data provided for this query."}

Background Information (from internal documents, if relevant):
{rag_context_string if rag_context_string else "No specific background documents."}

{news_context_string if news_context_string else "No recent news summaries for current keywords."}

Instructions for your response (max 4 lines for the brief itself):
1. Directly address the CURRENT user query, considering conversation history for context.
2. If portfolio data is relevant and provided, infer holdings and values (Quantity * CurrentPrice from CSV). State if data for detailed calculations (like total AUM or comparisons) is missing.
3. For earnings surprises, cite news summaries if specific percentages are mentioned. Otherwise, describe general performance.
4. Synthesize regional sentiment from news if asked; mention drivers like 'rising yields' ONLY IF in provided news/background.
5. If information is unavailable, state that. DO NOT FABRICATE.
"""
    langchain_messages.append(HumanMessage(content=current_turn_prompt_content))
    
    try:
        print(f"LanguageAgent (/synthesize): Invoking LLM. History turns: {len(chat_history or [])}. Current prompt content approx length: {len(current_turn_prompt_content)}")
        response = llm.invoke(langchain_messages) # Pass the full message list
        narrative = response.content.strip()
        print(f"LanguageAgent (/synthesize): Generated narrative successfully.")
        return narrative
    except Exception as e:
        print(f"LanguageAgent (/synthesize): LLM Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LLM synthesis error: {str(e)}")

@app.post("/synthesize", response_model=SynthesisResponse)
async def synthesize_narrative(request: SynthesisRequest):
    if not llm:
        raise HTTPException(status_code=503, detail="Language model not initialized.")
    try:
        print(f"LanguageAgent (/synthesize): Received request. Current Query: '{request.user_query}', "
              f"History items: {len(request.chat_history or [])}, "
              f"{len(request.retrieved_rag_context)} RAG_docs, "
              f"{len(request.scraped_news_articles)} news_articles. "
              f"Portfolio CSV provided: {bool(request.portfolio_csv_data)}")
        
        narrative_text = generate_llm_narrative_langchain(
            request.user_query,
            request.chat_history, # Pass the history
            request.retrieved_rag_context,
            request.scraped_news_articles,
            request.portfolio_csv_data
        )
        return SynthesisResponse(narrative=narrative_text)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error in synthesis: {str(e)}")