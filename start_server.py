#!/usr/bin/env python3
"""
OTA Server Startup Script
Starts the FastAPI server with proper configuration
"""

import uvicorn
import sys
from pathlib import Path

def main():
    """Start the OTA server"""
    print("🚀 Starting OTA Update Server...")
    print("📊 Admin Interface: http://localhost:8000/admin/metadata")
    print("🔑 API Keys: http://localhost:8000/admin/api-keys")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("-" * 50)
    
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            access_log=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down OTA server...")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()