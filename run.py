import subprocess
import os
import signal
import sys
from fastapi import FastAPI
from threading import Thread

app = FastAPI()

# Base path
base_path = os.path.dirname(os.path.abspath(__file__))

# Define all services to run
commands = [
    ["uvicorn", "stt_agent:app", "--port", "8005"],
    ["uvicorn", "tts_agent:app", "--port", "8006"],
    ["uvicorn", "retriever_agent:app", "--port", "8002"],
    ["uvicorn", "language_agent:app", "--port", "8003"],
    ["uvicorn", "scraping_agent:app", "--port", "8004"],
    ["uvicorn", "orchestrator:app", "--port", "8000"],
    ["streamlit", "run", "app.py"],
]

# Corresponding working directories
working_dirs = [
    os.path.join(base_path, "agents"),
    os.path.join(base_path, "agents"),
    os.path.join(base_path, "agents"),
    os.path.join(base_path, "agents"),
    os.path.join(base_path, "agents"),
    os.path.join(base_path, "orchestrator"),
    os.path.join(base_path, "streamlit_app"),
]

# Track subprocesses
processes = []

@app.on_event("shutdown")
def shutdown_event():
    stop_all_services()

def run_services():
    for cmd, cwd in zip(commands, working_dirs):
        print(f"🚀 Starting: {' '.join(cmd)} in {cwd}")
        proc = subprocess.Popen(cmd, cwd=cwd)
        processes.append(proc)
    print("✅ All services started.")

def stop_all_services():
    print("🛑 Stopping all services...")
    for proc in processes:
        try:
            proc.terminate()
        except Exception as e:
            print(f"Error terminating process: {e}")
    processes.clear()

@app.get("/")
def read_root():
    return {"message": "Service Orchestrator is Running"}

@app.post("/start")
def start_services():
    if processes:
        return {"message": "⚠️ Services are already running."}
    Thread(target=run_services, daemon=True).start()
    return {"message": "✅ Services started."}

@app.post("/stop")
def stop_services():
    if not processes:
        return {"message": "⚠️ No running services to stop."}
    stop_all_services()
    return {"message": "🛑 Services stopped."}
