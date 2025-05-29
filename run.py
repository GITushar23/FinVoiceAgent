#!/usr/bin/env python3
"""
Simple startup script for the Multi-Agent Finance Assistant
Run this to start the entire application stack
"""

import subprocess
import sys
import os
from pathlib import Path

def start_backend():
    """Start the FastAPI backend server"""
    print("🚀 Starting Multi-Agent Finance Assistant Backend...")
    try:
        # Start the main FastAPI application
        subprocess.run([
            sys.executable, "-m", "uvicorn", "main_app:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Backend server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting backend: {e}")
        sys.exit(1)

def start_streamlit():
    """Start the Streamlit frontend"""
    print("🚀 Starting Streamlit Frontend...")
    streamlit_app_dir = Path(__file__).parent / "streamlit_app"
    
    if not streamlit_app_dir.exists():
        print(f"❌ Streamlit app directory not found: {streamlit_app_dir}")
        sys.exit(1)
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "app.py"
        ], cwd=streamlit_app_dir, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Streamlit server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting Streamlit: {e}")
        sys.exit(1)

def main():
    """Main startup function"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "backend":
            start_backend()
        elif command == "frontend":
            start_streamlit()
        elif command == "help":
            print("""
Multi-Agent Finance Assistant Startup Script

Usage:
    python startup.py [command]

Commands:
    backend     - Start only the FastAPI backend server
    frontend    - Start only the Streamlit frontend
    help        - Show this help message

If no command is provided, starts the backend server by default.

Development Setup:
1. Start backend: python startup.py backend
2. In another terminal, start frontend: python startup.py frontend

The backend will be available at: http://localhost:8000
The frontend will be available at: http://localhost:8501
            """)
        else:
            print(f"❌ Unknown command: {command}")
            print("Use 'python startup.py help' for usage information")
            sys.exit(1)
    else:
        # Default to starting backend
        start_backend()

if __name__ == "__main__":
    main()