# /agents/language_agent.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage #, SystemMessage (optional for system prompt)
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
llm = None # Initialize LangChain LLM as None

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in environment variables. LangChain Google LLM will not be initialized.")
else:
    try:
        MODEL_NAME = "gemini-2.5-flash-preview-05-20"
        llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            google_api_key=GEMINI_API_KEY, # Explicitly passing, though env var usually works
            temperature=0.2, # Setting temperature for more focused output
            # convert_system_message_to_human=True # Might be useful if using SystemMessage
        )
        print(f"LangChain ChatGoogleGenerativeAI model ({MODEL_NAME}) initialized successfully.")
    except Exception as e:
        print(f"Error initializing LangChain ChatGoogleGenerativeAI model: {e}")
        llm = None # Ensure llm is None if initialization fails

app = FastAPI()

class SynthesisRequest(BaseModel):
    user_query: str
    retrieved_context: list[str]

class SynthesisResponse(BaseModel):
    narrative: str

def generate_llm_narrative_langchain(user_query: str, retrieved_context: list[str]) -> str:
    global llm
    if not llm:
        raise HTTPException(status_code=500, detail="LangChain Google LLM not configured or initialization failed.")

    context_string = "\n\n".join(retrieved_context)

    prompt_parts = [
        "You are a financial assistant. Your task is to synthesize a concise, well-formatted, and easily readable market brief based on the user's query and the provided context.",
        "Ensure all numbers, currency symbols (like NT$), and units (like billion) are clearly separated by single spaces and correctly written (e.g., 'NT$600 billion', not 'NT$600billion' or 'NT$ 600 b i l l i o n').",
        "Pay close attention to proper spacing between all words and ensure sentences are grammatically correct and flow naturally.",
        "Avoid any run-on words or jumbled phrases.",
        "User Query: " + user_query,
        "Retrieved Context:\n" + context_string,
        "\nBased on the query and context, provide the brief. If the context does not fully answer the query, state what you found. Do not make up information. Present the information clearly and professionally."
    ]
    prompt_text = "\n".join(prompt_parts)

    messages = [HumanMessage(content=prompt_text)]

    try:
        # Invoke the LangChain LLM
        response = llm.invoke(messages)
        
        # The response from llm.invoke is typically an AIMessage object,
        # and its content is in the 'content' attribute.
        if hasattr(response, 'content') and response.content:
            return response.content
        else:
            print(f"LangChain LLM returned an unexpected response structure or empty content: {response}")
            raise HTTPException(status_code=500, detail="LLM generated an empty or unreadable response via LangChain.")

    except Exception as e:
        print(f"Error during LangChain LLM call: {e}")
        # Consider more specific error handling for LangChain exceptions if needed
        raise HTTPException(status_code=500, detail=f"Error generating narrative with LangChain LLM: {str(e)}")

@app.post("/synthesize", response_model=SynthesisResponse)
async def synthesize_narrative(request: SynthesisRequest):
    if not llm: # Check if the LangChain llm object is initialized
        raise HTTPException(status_code=503, detail="Language model (LangChain) not initialized. Check API key and logs.")

    try:
        narrative_text = generate_llm_narrative_langchain(request.user_query, request.retrieved_context)
        return SynthesisResponse(narrative=narrative_text)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Unexpected error in /synthesize endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during synthesis: {str(e)}")

# To run this agent (from the root directory of your project):
# cd agents
# uvicorn language_agent:app --reload --port 8003
#
# Test with curl (same as before):
# curl -X POST -H "Content-Type: application/json" \
# -d '{"user_query": "What are the latest results for TSMC?", "retrieved_context": ["TSMC Q1 2025 revenue was NT$600 billion, beating expectations by 4%.", "Demand for AI and HPC is strong."]}' \
# http://127.0.0.1:8003/synthesize