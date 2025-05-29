# FinVoiceAgent


## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Getting Started](#getting-started)
4. [API Reference](#api-reference)
5. [Agent Details](#agent-details)
6. [Configuration](#configuration)
7. [Usage Examples](#usage-examples)
8. [Troubleshooting](#troubleshooting)

## Overview

The Multi-Agent Finance Assistant is a comprehensive financial analysis system that combines multiple AI agents to provide intelligent financial insights. The system can process both text and voice queries, scrape real-time financial news, perform vector-based document retrieval, and generate both text and audio responses.

### Key Features

- **Multi-modal input**: Text and voice queries
- **Real-time news scraping**: Financial news with AI-generated summaries
- **Stock data retrieval**: Real-time stock prices via Alpha Vantage API
- **RAG (Retrieval-Augmented Generation)**: Document-based context retrieval using FAISS
- **Voice synthesis**: Text-to-speech responses
- **Chat interface**: Streamlit-based web interface with conversation history
- **Portfolio analysis**: CSV-based portfolio data integration

## System Architecture

The system follows a microservices architecture with multiple specialized agents:

```
┌─────────────────┐
│   Streamlit     │
│   Frontend      │
└────────┬────────┘
         │ User Input (Text or Speech)
         ▼
┌─────────────────┐
│  Orchestrator   │
│  (Main Controller)  
└────────┬────────┘
         │
         ▼
 ┌───────┴────────┐
 │ Input Handling │
 └───────┬────────┘
         │
         ▼
 ┌───────▼──────┐
 │ STT Agent    │◄────── Speech input
 │ (Speech-to-  │
 │  Text)       │
 └──────────────┘
         │
         ▼
 ┌─────────────────┐
 │ Language Agent  │
 │ (LLM - Query     │
 │ Understanding)   │
 └────────┬────────┘
          │
   ┌──────┼────────────┬─────────────────┐
   │      │            │                 │
   ▼      ▼            ▼                 ▼
┌────┐ ┌────────────┐ ┌──────────────┐ ┌─────────────────┐
│ API│ │ Scraping   │ │ Retriever    │ │ (Optional Other │
│Agent│ │ Agent (News)│ │ Agent (RAG) │ │ Agents / Tools) │
└────┘ └────────────┘ └──────────────┘ └─────────────────┘
   \__________________________________________/
                     │
                     ▼
         ┌─────────────────────┐
         │  Response Text Gen  │
         └────────┬────────────┘
                  │
        ┌─────────▼─────────┐
        │ TTS Agent         │────► Speech Output
        │ (Text-to-Speech)  │
        └───────────────────┘
                  │
                  ▼
         ┌─────────────────┐
         │   Streamlit     │
         │   Frontend      │
         └─────────────────┘

```

## Getting Started

### Prerequisites

- Python 3.8+
- Required API keys:
  - Alpha Vantage API key (for stock data)
  - Google Gemini API key (for LLM processing)
  - ScrapingDog API key (for news scraping)
  - Deepgram API key (for STT/TTS)

### Installation

1. Clone the repository and install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables in `.env` file:
```env
ALPHAVANTAGE_API_KEY=your_alpha_vantage_key
GEMINI_API_KEY=your_gemini_key
SCRAPINGDOG_API_KEY=your_scrapingdog_key
DEEPGRAM_API_KEY=your_deepgram_key
```

3. Start the application:
```bash
python run.py
```

The system will be available at:
- **Main API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Streamlit Interface**: http://localhost:8501

## API Reference

### Base URL
```
http://localhost:8000
```

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "message": "All services are running"
}
```

### Main Endpoints

#### Process Text Query
```http
POST /orchestrator/process_full_brief_query/
```

**Request Body:**
```json
{
  "user_query": "What's the current sentiment on tech stocks?",
  "chat_history": [
    {
      "role": "user",
      "content": "Previous user message"
    },
    {
      "role": "assistant", 
      "content": "Previous assistant response"
    }
  ]
}
```

**Response:**
```json
{
  "narrative_text": "Generated financial analysis text...",
  "audio_base64": "base64_encoded_audio_data"
}
```

#### Process Voice Query
```http
POST /orchestrator/process_voice_query/
```

**Request:** Multipart form data with audio file

**Response:**
```json
{
  "narrative_text": "Generated financial analysis text...",
  "audio_base64": "base64_encoded_audio_data"
}
```

## Agent Details

### 1. API Agent (`/api`)

Handles stock data retrieval using Alpha Vantage API.

#### Endpoints:
- `GET /api/stock/{symbol}` - Get stock data

**Example:**
```http
GET /api/stock/AAPL
```

**Response:**
```json
{
  "symbol": "AAPL",
  "latest_trading_day": "2024-05-29",
  "latest_close": "189.25",
  "previous_trading_day": "2024-05-28", 
  "previous_close": "187.43"
}
```

### 2. Language Agent (`/language`)

Handles LLM processing using Google Gemini.

#### Endpoints:
- `POST /language/generate_keywords` - Generate search keywords
- `POST /language/synthesize` - Generate narrative from context

**Generate Keywords Example:**
```http
POST /language/generate_keywords
```
```json
{
  "user_query": "Apple earnings results"
}
```

**Response:**
```json
{
  "keywords": "Apple AAPL earnings results"
}
```

### 3. Retriever Agent (`/retriever`)

Handles document retrieval using FAISS vector search.

#### Endpoints:
- `POST /retriever/build_index` - Build/rebuild FAISS index
- `POST /retriever/search` - Search documents

**Search Example:**
```http
POST /retriever/search
```
```json
{
  "query": "market volatility",
  "top_k": 3
}
```

### 4. Scraping Agent (`/scraping`)

Handles news scraping and summarization.

#### Endpoints:
- `POST /scraping/scrape_summarized_news` - Scrape and summarize news

**Example:**
```http
POST /scraping/scrape_summarized_news
```
```json
{
  "query": "tech stocks earnings",
  "results_limit": 10,
  "summary_limit": 4
}
```

### 5. STT Agent (`/stt`)

Handles speech-to-text conversion using Deepgram.

#### Endpoints:
- `POST /stt/transcribe_audio` - Transcribe audio to text

**Example:**
```http
POST /stt/transcribe_audio
Content-Type: multipart/form-data

audio_file: [audio_file.wav]
```

### 6. TTS Agent (`/tts`)

Handles text-to-speech conversion using Deepgram.

#### Endpoints:
- `POST /tts/synthesize_speech` - Convert text to speech

**Example:**
```http
POST /tts/synthesize_speech
```
```json
{
  "text": "The market is showing positive sentiment today..."
}
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ALPHAVANTAGE_API_KEY` | Alpha Vantage API key for stock data | Yes |
| `GEMINI_API_KEY` | Google Gemini API key for LLM | Yes |
| `SCRAPINGDOG_API_KEY` | ScrapingDog API key for news scraping | Yes |
| `DEEPGRAM_API_KEY` | Deepgram API key for STT/TTS | Yes |

### File Paths

- **Portfolio CSV**: `data_ingestion/mock_portfolio_multi_day_real_companies.csv`
- **Documents**: `data_ingestion/sample_docs/` (for RAG)
- **Embedding Model**: `all-MiniLM-L6-v2` (HuggingFace)

### Model Configuration

- **LLM Model**: `gemini-2.0-flash-lite`
- **TTS Model**: `aura-hera-en`
- **STT Model**: `nova-2`

## Usage Examples

### Basic Text Query

```python
import requests

response = requests.post('http://localhost:8000/orchestrator/process_full_brief_query/', 
                        json={
                            "user_query": "How is Apple performing today?"
                        })
print(response.json())
```

### Query with Chat History

```python
import requests

response = requests.post('http://localhost:8000/orchestrator/process_full_brief_query/', 
                        json={
                            "user_query": "What about Microsoft?",
                            "chat_history": [
                                {"role": "user", "content": "How is Apple performing today?"},
                                {"role": "assistant", "content": "Apple is up 2.1% today..."}
                            ]
                        })
```

### Voice Query

```python
import requests

with open('query.wav', 'rb') as audio_file:
    response = requests.post('http://localhost:8000/orchestrator/process_voice_query/',
                           files={'audio_file': audio_file})
```

### Using Individual Agents

```python
# Get stock data
stock_response = requests.get('http://localhost:8000/api/stock/TSLA')

# Search documents
search_response = requests.post('http://localhost:8000/retriever/search',
                               json={"query": "market trends", "top_k": 5})

# Scrape news
news_response = requests.post('http://localhost:8000/scraping/scrape_summarized_news',
                             json={"query": "Tesla earnings", "results_limit": 5})
```

## Troubleshooting

### Common Issues

#### 1. API Key Errors
**Error:** `API key not configured` or `503 Service Unavailable`

**Solution:** 
- Verify all required API keys are set in your `.env` file
- Restart the application after adding API keys

#### 2. Vector Store Not Initialized
**Error:** `Vector store not initialized. Call /build_index first.`

**Solution:**
```http
POST /retriever/build_index
```

#### 3. Audio Processing Issues
**Error:** `STT service not available` or `TTS service not available`

**Solution:**
- Check Deepgram API key is valid
- Ensure audio file format is supported (WAV, MP3, etc.)
- Check file size limits

#### 4. News Scraping Timeouts
**Error:** `Request timeout` or `ScrapingDog API error`

**Solution:**
- Check ScrapingDog API quota and limits
- Reduce `results_limit` and `summary_limit` parameters
- Verify internet connection

#### 5. LLM Processing Errors
**Error:** `Language model not initialized` or `LLM synthesis error`

**Solution:**
- Verify Gemini API key is valid and has quota
- Check if the model `gemini-2.0-flash-lite` is available
- Reduce input text length if hitting token limits

### Debug Mode

To enable detailed logging, set environment variable:
```bash
export DEBUG=1
```

### Health Checks

Monitor individual agent health:
```bash
# Check main system
curl http://localhost:8000/health

# Check individual endpoints
curl http://localhost:8000/endpoints
```

### Performance Tips

1. **Reduce timeout values** for faster responses in development
2. **Limit news article processing** by reducing `summary_limit`
3. **Cache responses** for repeated queries
4. **Use smaller embedding models** for faster RAG retrieval
5. **Optimize portfolio CSV size** for faster processing

### Support

For issues not covered in this documentation:

1. Check the API documentation at `http://localhost:8000/docs`
2. Review individual agent logs in the console output
3. Verify all dependencies are installed correctly
4. Test individual agents separately to isolate issues

---

**Last Updated:** May 29, 2025  
**Version:** 1.0.0
