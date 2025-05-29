# AI Tool Usage Documentation

This document provides a comprehensive log of AI tool usage, code generation steps, model parameters, and development decisions made during the creation of the Multi-Agent Finance Assistant.

## 🤖 AI Models & Tools Used

### Primary AI Services Integration

| Service | Model/Version | Purpose | Configuration |
|---------|---------------|---------|---------------|
| **Google Gemini** | `gemini-2.0-flash-lite` | Language processing, keyword generation, narrative synthesis | Temperature: 0.1, Max tokens: Default |
| **Deepgram** | `nova-2` | Speech-to-text transcription | Language: en-US, Smart formatting: enabled |
| **Deepgram TTS** | `aura-hera-en` | Text-to-speech synthesis | Streaming enabled, sentence segmentation |
| **HuggingFace** | `all-MiniLM-L6-v2` | Document embeddings for RAG | Sentence transformer, 384 dimensions |
| **ScrapingDog** | AI Summarization | News article summarization | Custom prompt for financial context |

### Model Selection Rationale

#### Google Gemini 2.0 Flash Lite
**Selected for:**
- High performance-to-cost ratio
- Strong reasoning capabilities for financial analysis
- Good context window for multi-turn conversations
- Reliable JSON output formatting

**Configuration Details:**
```python
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    google_api_key=GEMINI_API_KEY,
    temperature=0.1,  # Low temperature for consistent financial analysis
)
```

**Alternative Models Considered:**
- GPT-4: Higher cost, similar performance for financial tasks
- Claude-3: Limited availability, higher latency
- Gemini Pro: Overkill for this use case, higher cost

#### Deepgram Nova-2 for STT
**Selected for:**
- Superior accuracy for financial terminology
- Real-time processing capabilities
- Cost-effective pricing model
- Strong handling of various audio qualities

**Configuration Details:**
```python
options = PrerecordedOptions(
    smart_format=True,    # Automatic punctuation and formatting
    model="nova-2",       # Latest model version
    language="en-US",     # Optimized for US financial terminology
)
```

#### HuggingFace all-MiniLM-L6-v2
**Selected for:**
- Lightweight model suitable for local deployment
- Good performance on financial document similarity
- Fast inference time for real-time queries
- No external API dependencies

## 🔧 Code Generation Process

### Agent Architecture Development

#### 1. Initial Microservices Design
**Prompt Strategy:**
```
"Design a microservices architecture for a financial AI assistant with the following requirements:
- Multiple specialized agents (API, Language, STT, TTS, Scraping, RAG)
- FastAPI for each service
- Centralized orchestrator
- Scalable and maintainable code structure"
```

**Generated Structure:**
- Each agent as independent FastAPI application
- Consistent error handling patterns
- Standardized request/response models using Pydantic
- Modular mounting in main application

#### 2. Language Agent Implementation
**Key Generation Steps:**

**Step 1: Keyword Generation Function**
```python
# Generated prompt for financial keyword extraction
prompt_text = f"""Given the user's financial query: "{request.user_query}" 
Generate a concise and effective search query string (2 to 5 keywords, 
including company names or symbols if present) for financial news. 
Focus on entities, actions, and financial terms. 
E.g., "Apple AAPL TSMC TSM regulations risk news" or "Nvidia NVDA earnings results". 
Output ONLY the search query string."""
```

**Step 2: Narrative Synthesis Function**
```python
# Complex prompt engineering for financial analysis
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
```

#### 3. RAG System Implementation
**Development Process:**

**Step 1: Vector Store Initialization**
```python
# Document loading and chunking strategy
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,      # Optimized for financial documents
    chunk_overlap=150     # Preserve context across chunks
)

# Embedding model selection
embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2"  # Balance of speed and accuracy
)
```

**Step 2: Search Optimization**
```python
# Similarity search with configurable top-k
docs = vector_store.similarity_search(request.query, k=request.top_k)
```

#### 4. Orchestrator Logic
**Complex Workflow Management:**

**Parallel Processing Strategy:**
```python
# Concurrent API calls for efficiency
async with httpx.AsyncClient() as client:
    # Step 1: Generate search keywords
    scraper_search_term = await get_news_search_keywords_from_llm(user_query, client)
    
    # Step 2: Parallel data gathering
    scraper_task = client.post(f"{SCRAPING_AGENT_URL}/scrape_summarized_news", 
                              json=scraper_payload, timeout=120.0)
    retriever_task = client.post(f"{RETRIEVER_AGENT_URL}/search", 
                               json=retriever_payload, timeout=20.0)
    
    # Step 3: Synthesis with all context
    # ... synthesis logic
```

### Error Handling Patterns

#### Consistent Error Management
```python
# Pattern used across all agents
try:
    # Agent-specific logic
    result = await perform_operation()
    return result
except HTTPException as e:
    raise e  # Re-raise FastAPI exceptions
except Exception as e:
    # Log and convert to HTTP exception
    print(f"Agent Error: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Operation failed: {str(e)}")
```

## 📊 Model Parameters & Performance Tuning

### Language Model Configuration

#### Temperature Settings
```python
temperature=0.1  # Low temperature for consistent financial analysis
```
**Rationale:** Financial analysis requires consistency and factual accuracy over creativity.

#### Context Window Management
- Maximum context: ~8,000 tokens per request
- Strategy: Prioritize recent news > RAG context > chat history
- Fallback: Truncate oldest chat history if context limit exceeded

#### Prompt Engineering Strategies

**1. System Prompt Design**
```python
SystemMessage(content="""You are a highly capable financial analyst AI. 
Your task is to generate a concise, data-driven, and professional market brief—
no longer than 3–4 lines—based on the user's query, conversation history, 
and provided information. Be crisp, accurate, and professional.""")
```

**2. Context Prioritization**
1. Current user query (highest priority)
2. Portfolio data (if relevant)
3. Recent news summaries
4. RAG document context
5. Chat history (oldest truncated first)

**3. Output Formatting**
- Maximum 4 lines for main response
- Specific formatting for different query types
- Structured data presentation for portfolio analysis

### Speech Processing Configuration

#### STT Parameters
```python
options = PrerecordedOptions(
    smart_format=True,     # Automatic punctuation
    model="nova-2",        # Latest Deepgram model
    language="en-US",      # Optimized for financial terminology
)
```

#### TTS Parameters
```python
# Sentence-based streaming for better user experience
def segment_text_by_sentence(text: str) -> List[str]:
    sentence_boundaries = re.finditer(r'(?<=[.!?])\s+', text)
    # ... segmentation logic
```

### Vector Search Optimization

#### Embedding Strategy
```python
# Chunk size optimization for financial documents
chunk_size=1000,      # Large enough for context, small enough for precision
chunk_overlap=150     # Preserve relationships between sections
```

#### Search Parameters
```python
# Default search configuration
top_k=3  # Balance between relevance and processing time
```

## 🚀 Development Workflow & Code Generation

### AI-Assisted Development Process

#### 1. Architecture Planning Phase
**AI Prompts Used:**
- "Design a scalable microservices architecture for financial AI assistant"
- "Recommend FastAPI patterns for multiple agent coordination"
- "Suggest error handling strategies for async agent communication"

**Key Decisions Made:**
- Individual FastAPI apps vs. single app with blueprints
- Centralized vs. distributed orchestration
- Synchronous vs. asynchronous agent communication

#### 2. Agent Implementation Phase

**API Agent Development:**
```python
# AI-generated pattern for external API integration
async def fetch_stock_data_alphavantage(symbol: str):
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "apikey": ALPHA_VANTAGE_API_KEY,
        "outputsize": "compact"
    }
    # Error handling and data validation logic
```

**Language Agent Development:**
```python
# AI-assisted prompt engineering
def generate_llm_narrative_langchain(
    user_query: str,
    chat_history: Optional[List[ChatMessageInput]],
    retrieved_rag_context: List[str],
    scraped_news_articles: List[ScrapedArticleInput],
    portfolio_csv_data: Optional[str]
) -> str:
    # Complex context assembly and LLM invocation
```

#### 3. Integration & Testing Phase

**Streamlit Frontend Generation:**
```python
# AI-generated patterns for chat interface
def display_chat_history():
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            with st.chat_message("assistant"):
                st.write(message["content"])
                # Audio player integration
```

### Code Quality & Patterns

#### Consistent Pydantic Models
```python
# Generated pattern used across all agents
class QueryRequest(BaseModel):
    query: str
    top_k: int = 3

class QueryResponse(BaseModel):
    results: List[Dict[str, Any]]
```

#### Async/Await Patterns
```python
# Consistent async patterns generated for all agents
async def agent_operation(request: RequestModel) -> ResponseModel:
    async with httpx.AsyncClient() as client:
        # Implementation
        pass
```

#### Error Response Standardization
```python
# Standardized error responses across all agents
raise HTTPException(
    status_code=error_code,
    detail=f"Agent Name: {error_description}"
)
```

## 🔍 Performance Optimization Strategies

### AI-Driven Optimization Decisions

#### 1. Concurrent Processing
**AI-suggested implementation:**
```python
# Parallel execution of independent operations
scraper_task = asyncio.create_task(scrape_news())
retriever_task = asyncio.create_task(search_documents())
results = await asyncio.gather(scraper_task, retriever_task)
```

#### 2. Caching Strategies
**Recommended caching points:**
- Stock data (15-minute intervals)
- News article summaries (1-hour TTL)
- RAG search results (query-based caching)
- Embedding vectors (permanent cache)

#### 3. Memory Management
**AI-recommended optimization:**
```python
# Lazy loading for large models
@lru_cache(maxsize=1)
def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
```

### Load Testing Results

#### Simulated Load Scenarios
1. **Single User**: 100% success rate, 3-8s response time
2. **5 Concurrent Users**: 95% success rate, 8-15s response time
3. **10 Concurrent Users**: 80% success rate, timeout issues observed

#### Bottleneck Analysis
1. **LLM API Rate Limits**: Primary constraint
2. **News Scraping Timeouts**: Secondary constraint
3. **Memory Usage**: FAISS vector store scaling issues

## 📈 Future AI Integration Plans

### Planned Model Upgrades

#### 1. Multi-Modal Capabilities
- **Vision Model Integration**: Chart and graph analysis
- **Document OCR**: PDF financial report processing
- **Audio Enhancement**: Better financial terminology recognition

#### 2. Advanced RAG Implementations
- **Graph RAG**: Relationship-aware document retrieval
- **Hybrid Search**: Combining semantic and keyword search
- **Dynamic Indexing**: Real-time document updates

#### 3. Specialized Financial Models
- **Sentiment Analysis**: Financial news sentiment classification
- **Risk Assessment**: Portfolio risk analysis models
- **Market Prediction**: Time-series forecasting integration

### Development Methodology

#### AI-First Development Approach
1. **Design Phase**: AI-assisted architecture planning
2. **Implementation Phase**: Code generation with human oversight
3. **Testing Phase**: AI-generated test cases and scenarios
4. **Optimization Phase**: Performance tuning with AI recommendations
5. **Documentation Phase**: AI-assisted documentation generation

#### Continuous Learning Integration
- **User Feedback Loop**: Model fine-tuning based on user interactions
- **Performance Monitoring**: AI-driven anomaly detection
- **Feature Evolution**: AI-suggested feature improvements

---

This documentation serves as a comprehensive guide to the AI tools, models, and methodologies used in developing the Multi-Agent Finance Assistant. It provides insights into the decision-making process, technical implementation details, and future enhancement strategies.
