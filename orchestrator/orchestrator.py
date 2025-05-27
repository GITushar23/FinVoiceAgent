# /orchestrator/orchestrator.py
from fastapi import FastAPI, HTTPException
import httpx
from pydantic import BaseModel

app = FastAPI()

# Agent URLs - Ensure these ports match how you are running your agents
API_AGENT_URL = "http://127.0.0.1:8001" # For fetching direct stock data (will be used later)
RETRIEVER_AGENT_URL = "http://127.0.0.1:8002"
LANGUAGE_AGENT_URL = "http://127.0.0.1:8003"

class QueryRequest(BaseModel):
    user_query: str # Changed from 'symbol' or 'text' to 'user_query'

@app.post("/process_market_brief_query/") # Renamed for clarity
async def process_market_brief_query(request: QueryRequest):
    user_query = request.user_query
    if not user_query:
        raise HTTPException(status_code=400, detail="No user_query provided.")

    retrieved_chunks_content = []
    try:
        # 1. Call Retriever Agent
        async with httpx.AsyncClient(timeout=20.0) as client: # Increased timeout
            retriever_payload = {"query": user_query, "top_k": 3}
            print(f"Orchestrator: Calling Retriever Agent with query: {user_query}")
            response_retriever = await client.post(f"{RETRIEVER_AGENT_URL}/search", json=retriever_payload)
            response_retriever.raise_for_status()
            retrieved_data = response_retriever.json()
            
            if retrieved_data and "results" in retrieved_data:
                for item in retrieved_data["results"]:
                    if "page_content" in item:
                        retrieved_chunks_content.append(item["page_content"])
            print(f"Orchestrator: Retrieved context: {retrieved_chunks_content}")

    except httpx.HTTPStatusError as exc:
        error_detail = exc.response.json().get("detail") if exc.response.content else str(exc)
        raise HTTPException(status_code=exc.response.status_code, 
                            detail=f"Error from Retriever Agent: {error_detail}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Error connecting to Retriever Agent: {exc}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during retrieval step: {str(e)}")

    try:
        # 2. Call Language Agent with original query and retrieved context
        async with httpx.AsyncClient(timeout=30.0) as client: # Increased timeout for LLM
            language_payload = {
                "user_query": user_query,
                "retrieved_context": retrieved_chunks_content
            }
            print(f"Orchestrator: Calling Language Agent with query and context.")
            response_language = await client.post(f"{LANGUAGE_AGENT_URL}/synthesize", json=language_payload)
            response_language.raise_for_status()
            narrative_response = response_language.json()
            print(f"Orchestrator: Received narrative: {narrative_response.get('narrative')}")
            return narrative_response # Should be {"narrative": "..."}

    except httpx.HTTPStatusError as exc:
        error_detail = exc.response.json().get("detail") if exc.response.content else str(exc)
        raise HTTPException(status_code=exc.response.status_code, 
                            detail=f"Error from Language Agent: {error_detail}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Error connecting to Language Agent: {exc}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during synthesis step: {str(e)}")

# To run this orchestrator (from the root directory of your project):
# cd orchestrator
# uvicorn orchestrator:app --reload --port 8000
#
# Test with curl:
# curl -X POST -H "Content-Type: application/json" -d '{"user_query": "What are the latest results for TSMC?"}' http://127.0.0.1:8000/process_market_brief_query/
# curl -X POST -H "Content-Type: application/json" -d '{"user_query": "How is Samsung doing?"}' http://127.0.0.1:8000/process_market_brief_query/