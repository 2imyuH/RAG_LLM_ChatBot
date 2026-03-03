import os
# FORCE ONLINE MODE: Disable offline restrictions at the code level
# to prevent OfflineModeIsEnabled errors during model metadata checks.
os.environ["TRANSFORMERS_OFFLINE"] = "0"
os.environ["HF_HUB_OFFLINE"] = "0"

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import uvicorn
import logging
import sys
import os
import time
import asyncio
import anyio
import threading

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.generation.rag import RAGEngine
from src import config

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Enterprise RAG API",
    version="1.0.0",
    description="RAG Microservice for document querying"
)

# CORS Middleware (for Node.js backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Engine (loaded once at startup)
rag_engine = None

class ChatRequest(BaseModel):
    query: str
    chat_history: List[Dict[str, str]] = []

class ChatResponse(BaseModel):
    answer: str
    decision_trace: Dict = {}
    latency_ms: float

class HealthResponse(BaseModel):
    status: str
    rag_engine_ready: bool
    ollama_connected: bool

@app.on_event("startup")
async def startup_event():
    global rag_engine
    logger.info("=" * 50)
    logger.info("Starting up RAG API Server...")
    logger.info(f"API Host: {config.API_HOST}")
    logger.info(f"API Port: {config.API_PORT}")
    logger.info("=" * 50)
    
    logger.info("Initializing RAG Engine (loading models)...")
    logger.info("This may take several minutes on first run...")
    
    try:
        rag_engine = RAGEngine()
        logger.info("✓ RAG Engine initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize RAG Engine: {e}")
        raise
    
    # Check Ollama connection
    if rag_engine.orchestrator.llm.check_connection():
        logger.info("✓ Ollama connection verified")
    else:
        logger.warning("⚠ Ollama connection check failed - ensure Ollama is running")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down RAG API Server...")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with detailed status"""
    ollama_connected = False
    if rag_engine:
        ollama_connected = rag_engine.orchestrator.llm.check_connection()
    
    return HealthResponse(
        status="ok" if rag_engine else "not_ready",
        rag_engine_ready=rag_engine is not None,
        ollama_connected=ollama_connected
    )

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: Request, chat_req: ChatRequest):
    """
    Main RAG query endpoint with abortion support.
    """
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not ready")
    
    if not chat_req.query or not chat_req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    start_time = time.time()
    stop_event = threading.Event()

    # Background task to monitor if the client (Node.js worker) closes the connection
    async def monitor_disconnect():
        try:
            while not stop_event.is_set():
                if await request.is_disconnected():
                    logger.warning("Client disconnected detected in server.py. Signaling orchestrator...")
                    stop_event.set()
                    break
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error in disconnect monitor: {e}")

    monitor_task = asyncio.create_task(monitor_disconnect())

    try:
        logger.info(f"Processing query: {chat_req.query[:100]}...")
        
        # Run the synchronous/CPU-bound RAG logic in a separate thread
        # Pass a lambda that checks the stop_event
        final_answer = await anyio.to_thread.run_sync(
            rag_engine.orchestrator.handle_query,
            chat_req.query,
            chat_req.chat_history,
            lambda: stop_event.is_set()
        )
        
        trace = getattr(rag_engine.orchestrator, 'last_decision_trace', {})
        latency = (time.time() - start_time) * 1000
        logger.info(f"Query completed in {latency:.2f}ms")
        
        return ChatResponse(answer=final_answer, decision_trace=trace, latency_ms=latency)
        
    except InterruptedError:
        logger.warning("Query processing was successfully aborted.")
        # 499 is a standard non-standard code for Client Closed Request
        raise HTTPException(status_code=499, detail="Request aborted by client")
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        logger.error(f"Error processing query after {latency:.2f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        # Signal the monitor task to stop and clean up
        stop_event.set()
        await monitor_task

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Enterprise RAG API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "chat": "/chat (POST)"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        log_level="info"
    )
