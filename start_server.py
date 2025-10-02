#!/usr/bin/env python3
"""
OTA Server Startup Script
Starts the FastAPI server with static file serving
"""

import uvicorn
import sys
import threading
import time
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

class QuietHTTPRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler with minimal logging"""
    def log_message(self, format, *args):
        # Only log errors
        if '404' in str(args) or '500' in str(args):
            print(f"📁 Static file error: {format % args}")

def start_static_server():
    """Start static file server on port 8001"""
    os.chdir(".")  # Serve from current directory
    server = HTTPServer(("0.0.0.0", 8001), QuietHTTPRequestHandler)
    print("📁 Static file server started on port 8001")
    try:
        server.serve_forever()
    except:
        pass

def main():
    """Start the OTA server with static file server"""
    print("🚀 Starting OTA Update Server...")
    print("📊 Admin Interface: http://localhost:8000/admin/metadata")
    print("🔑 API Keys: http://localhost:8000/admin/api-keys")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("📁 Static Files: http://localhost:8001/packages/")
    print("-" * 50)
    
    # Start static file server in background thread
    static_thread = threading.Thread(target=start_static_server, daemon=True)
    static_thread.start()
    
    # Give static server time to start
    time.sleep(1)
    
    try:
        # Python 3.13 compatible server configuration
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,  # Disable reload to prevent thread issues
            access_log=True,
            log_level="info",
            # Conservative settings for Python 3.13 stability
            timeout_keep_alive=30,
            timeout_graceful_shutdown=5,
            # Reduced limits for stability
            limit_concurrency=50,
            limit_max_requests=200,
            # Use HTTP/1.1 only - more stable than HTTP/2
            server_header=False,
            date_header=False
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down OTA server...")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()