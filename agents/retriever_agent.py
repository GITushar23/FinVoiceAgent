# /agents/retriever_agent.py
import os
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from langchain.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader

# Configuration
DOCS_PATH = "../data_ingestion/sample_docs" # Path relative to this agent's file
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2" # A good, small sentence transformer

# Global variable to hold the FAISS index and retriever
# This is okay for a simple MVP; for production, consider a more robust way to manage this.
vector_store = None

def get_vector_store():
    global vector_store
    if vector_store is None:
        raise HTTPException(status_code=503, detail="Vector store not initialized. Call /build_index first.")
    return vector_store

def initialize_vector_store():
    global vector_store
    try:
        if not os.path.exists(DOCS_PATH) or not os.listdir(DOCS_PATH):
            print(f"WARNING: Document directory {DOCS_PATH} is empty or does not exist.")
            # Allow initialization with an empty store if no docs, or handle as error
            # For now, we'll let it proceed, and search will return empty.
            # A better approach might be to raise an error or ensure docs exist.
            loader = [] # No documents to load
            documents = []
        else:
            loader = DirectoryLoader(
                DOCS_PATH,
                glob="**/*.txt", # Load .txt files
                loader_cls=TextLoader,
                show_progress=True,
                use_multithreading=True
            )
            documents = loader.load()

        if not documents:
            print("No documents loaded. FAISS index will be empty.")
            # Create an empty FAISS index if no documents are found
            # This requires at least one dummy text and embedding if FAISS lib insists.
            # Or, handle this case more gracefully in the search endpoint.
            # For simplicity, we'll assume Langchain handles empty docs for FAISS creation or search.
            # If FAISS creation errors on empty docs, we'd need a workaround.
            # Let's proceed assuming it handles it or we handle empty search results.
            pass # vector_store will remain None or be an empty store

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        texts = text_splitter.split_documents(documents)

        if not texts:
            print("No text chunks to index after splitting. FAISS index will effectively be empty.")
            # If there are no texts, FAISS cannot be built with data.
            # vector_store will remain None or we need a way to represent an empty, valid FAISS store.
            # Langchain's FAISS.from_documents might handle this by creating an empty index.
            vector_store = None # Or some representation of an empty store
            return {"message": "No documents found or processed. Index is empty."}


        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        
        # Check if texts is not empty before creating FAISS index
        if texts:
            vector_store = FAISS.from_documents(texts, embeddings)
            print("FAISS index built successfully from documents.")
            return {"message": "FAISS index built successfully."}
        else:
            # If after splitting there are no texts, we can't build the index with data.
            # One way to handle this is to initialize FAISS with a dummy entry if the library requires it,
            # or simply ensure search operations return empty if the index is empty.
            # Langchain's FAISS might handle `texts=[]` gracefully. If not, this needs adjustment.
            # For now, let's assume `FAISS.from_documents` with empty `texts` results in an empty, searchable index.
            # If it errors, we'd need to handle that (e.g. by not setting vector_store or setting it to a dummy FAISS object).
            print("No text chunks available to build FAISS index.")
            # To ensure vector_store is not None but represents an empty, queryable state if FAISS allows:
            # This part is tricky as FAISS usually expects some data to initialize.
            # A robust way is to check vector_store before search.
            # For now, if `texts` is empty, `vector_store` might not be properly initialized by FAISS.from_documents.
            # We will rely on the search endpoint to handle a potentially uninitialized or empty vector_store.
            vector_store = None # Explicitly state it's not built with data
            return {"message": "No text chunks to index. Index is empty."}

    except Exception as e:
        print(f"Error initializing vector store: {e}")
        vector_store = None # Ensure it's None on error
        # Re-raise or raise HTTPException to signal failure more clearly
        raise HTTPException(status_code=500, detail=f"Failed to initialize vector store: {str(e)}")


app = FastAPI()

@app.on_event("startup")
async def startup_event():
    print("Retriever Agent starting up. Initializing vector store...")
    try:
        initialize_vector_store()
        if vector_store:
            print("Vector store initialized successfully on startup.")
        else:
            print("Vector store could not be initialized with data on startup (e.g. no documents found).")
    except Exception as e:
        # Log error, but don't prevent startup if initialization fails,
        # as /build_index can be called later.
        print(f"Startup error during vector store initialization: {e}")
        # vector_store will be None, and get_vector_store will raise HTTPException

class QueryRequest(BaseModel):
    query: str
    top_k: int = 3

@app.post("/build_index")
async def build_index_endpoint():
    """Manually trigger building or rebuilding the FAISS index."""
    try:
        result = initialize_vector_store()
        return result
    except HTTPException as e: # Catch HTTPExceptions from initialize_vector_store
        raise e
    except Exception as e: # Catch any other unexpected errors
        raise HTTPException(status_code=500, detail=f"Failed to build index: {str(e)}")

@app.post("/search")
async def search_documents(request: QueryRequest, current_vector_store: FAISS = Depends(get_vector_store)):
    """Search for relevant documents based on a query."""
    if current_vector_store is None: # Double check, though Depends(get_vector_store) should handle it
        raise HTTPException(status_code=503, detail="Vector store not available or empty. Try calling /build_index.")
    try:
        # FAISS.similarity_search handles empty index gracefully if initialized correctly (e.g., empty but valid)
        # If vector_store was never successfully initialized with FAISS.from_documents (e.g., texts was empty),
        # this line might error depending on how FAISS object behaves when empty.
        # Langchain's FAISS wrapper should ideally return [] if the index is empty.
        docs = current_vector_store.similarity_search(request.query, k=request.top_k)
        return {"results": [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in docs]}
    except Exception as e:
        # This might catch errors if the vector_store is in an unexpected state (e.g., None or not a FAISS object)
        # or if the search itself fails for other reasons.
        raise HTTPException(status_code=500, detail=f"Error during search: {str(e)}")

# To run this agent (from the root directory of your project):
# cd agents
# uvicorn retriever_agent:app --reload --port 8002
#
# First, you might want to ensure the index is built (though it tries on startup):
# curl -X POST http://127.0.0.1:8002/build_index
#
# Then test search:
# curl -X POST -H "Content-Type: application/json" -d '{"query": "TSMC earnings"}' http://127.0.0.1:8002/search
# curl -X POST -H "Content-Type: application/json" -d '{"query": "Samsung challenges", "top_k": 1}' http://127.0.0.1:8002/search