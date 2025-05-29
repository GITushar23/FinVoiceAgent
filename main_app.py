# main_app.py
import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add the agents directory to Python path so we can import the agent modules
current_dir = Path(__file__).resolve().parent
agents_dir = current_dir / "agents"
orchestrator_dir = current_dir / "orchestrator"

sys.path.append(str(agents_dir))
sys.path.append(str(orchestrator_dir))

# Import all the individual FastAPI apps
try:
    from api_agent import app as api_app
    print("✅ API Agent imported successfully")
except Exception as e:
    print(f"❌ Failed to import API Agent: {e}")
    api_app = FastAPI()

try:
    from language_agent import app as language_app
    print("✅ Language Agent imported successfully")
except Exception as e:
    print(f"❌ Failed to import Language Agent: {e}")
    language_app = FastAPI()

try:
    from retriever_agent import app as retriever_app
    print("✅ Retriever Agent imported successfully")
except Exception as e:
    print(f"❌ Failed to import Retriever Agent: {e}")
    retriever_app = FastAPI()

try:
    from scraping_agent import app as scraping_app
    print("✅ Scraping Agent imported successfully")
except Exception as e:
    print(f"❌ Failed to import Scraping Agent: {e}")
    scraping_app = FastAPI()

try:
    from stt_agent import app as stt_app
    print("✅ STT Agent imported successfully")
except Exception as e:
    print(f"❌ Failed to import STT Agent: {e}")
    stt_app = FastAPI()

try:
    from tts_agent import app as tts_app
    print("✅ TTS Agent imported successfully")
except Exception as e:
    print(f"❌ Failed to import TTS Agent: {e}")
    tts_app = FastAPI()

try:
    from orchestrator import app as orchestrator_app
    print("✅ Orchestrator imported successfully")
except Exception as e:
    print(f"❌ Failed to import Orchestrator: {e}")
    orchestrator_app = FastAPI()

# Create the main FastAPI application
app = FastAPI(
    title="Multi-Agent Finance Assistant",
    description="Combined FastAPI application with all agents on different endpoints",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all the individual apps on different paths
app.mount("/api", api_app)
app.mount("/language", language_app)  
app.mount("/retriever", retriever_app)
app.mount("/scraping", scraping_app)
app.mount("/stt", stt_app)
app.mount("/tts", tts_app)
app.mount("/orchestrator", orchestrator_app)

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Multi-Agent Finance Assistant API",
        "version": "1.0.0",
        "endpoints": {
            "api_agent": "/api",
            "language_agent": "/language", 
            "retriever_agent": "/retriever",
            "scraping_agent": "/scraping",
            "stt_agent": "/stt",
            "tts_agent": "/tts",
            "orchestrator": "/orchestrator"
        },
        "health_check": "/health"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "All services are running"}

@app.get("/endpoints")
async def list_endpoints():
    """List all available endpoints"""
    endpoints = {
        "API Agent (Stock Data)": {
            "base_path": "/api",
            "endpoints": [
                "GET /stock/{symbol} - Get stock data for a symbol"
            ]
        },
        "Language Agent (LLM Processing)": {
            "base_path": "/language",
            "endpoints": [
                "POST /generate_keywords - Generate search keywords",
                "POST /synthesize - Synthesize narrative from context"
            ]
        },
        "Retriever Agent (RAG/Vector Search)": {
            "base_path": "/retriever", 
            "endpoints": [
                "POST /build_index - Build/rebuild FAISS index",
                "POST /search - Search documents"
            ]
        },
        "Scraping Agent (News Scraping)": {
            "base_path": "/scraping",
            "endpoints": [
                "POST /scrape_summarized_news - Scrape and summarize news"
            ]
        },
        "STT Agent (Speech-to-Text)": {
            "base_path": "/stt",
            "endpoints": [
                "POST /transcribe_audio - Transcribe audio to text"
            ]
        },
        "TTS Agent (Text-to-Speech)": {
            "base_path": "/tts",
            "endpoints": [
                "POST /synthesize_speech - Convert text to speech"
            ]
        },
        "Orchestrator (Main Logic)": {
            "base_path": "/orchestrator",
            "endpoints": [
                "POST /process_full_brief_query/ - Process text query",
                "POST /process_voice_query/ - Process voice query"
            ]
        }
    }
    return endpoints

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Multi-Agent Finance Assistant...")
    print("📍 Main application will be available at: http://localhost:8000")
    print("📋 Endpoints documentation: http://localhost:8000/docs")
    print("🏥 Health check: http://localhost:8000/health")
    
    uvicorn.run(
        "main_app:app",  # Changed from "main_app:main_app" to "main_app:app"
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_includes=["*.py"],
        reload_dirs=["agents", "orchestrator"]
    )