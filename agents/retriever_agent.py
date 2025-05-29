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
            pass # vector_store will remain None or be an empty store

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        texts = text_splitter.split_documents(documents)

        if not texts:
            print("No text chunks to index after splitting. FAISS index will effectively be empty.")

            vector_store = None # Or some representation of an empty store
            return {"message": "No documents found or processed. Index is empty."}


        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        
        # Check if texts is not empty before creating FAISS index
        if texts:
            vector_store = FAISS.from_documents(texts, embeddings)
            print("FAISS index built successfully from documents.")
            return {"message": "FAISS index built successfully."}
        else:
            print("No text chunks available to build FAISS index.")

            vector_store = None # Explicitly state it's not built with data
            return {"message": "No text chunks to index. Index is empty."}

    except Exception as e:
        print(f"Error initializing vector store: {e}")
        vector_store = None # Ensure it's None on error
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
        print(f"Startup error during vector store initialization: {e}")

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
        docs = current_vector_store.similarity_search(request.query, k=request.top_k)
        return {"results": [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in docs]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during search: {str(e)}")
