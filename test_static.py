#!/usr/bin/env python3
"""
Quick test for static file serving
"""

import requests
import time

def test_static_servers():
    """Test both static server options"""
    base_url = "http://localhost:8000"
    
    print("🧪 Testing Static File Serving")
    print("=" * 40)
    
    # Test if main server is running
    try:
        response = requests.get(f"{base_url}/admin/metadata", timeout=5)
        print(f"✅ Main server running (HTTP {response.status_code})")
    except Exception as e:
        print(f"❌ Main server not running: {str(e)}")
        return
    
    # Test dedicated static server
    try:
        response = requests.head("http://localhost:8001/", timeout=2)
        print(f"✅ Dedicated static server running (HTTP {response.status_code})")
    except Exception as e:
        print(f"⚠️ Dedicated static server not available: {str(e)}")
    
    # Test package download redirect
    try:
        response = requests.get(f"{base_url}/packages/ota-nfc.zip", allow_redirects=False, timeout=5)
        if response.status_code == 302:
            redirect_url = response.headers.get('Location')
            print(f"✅ Package redirect working: {redirect_url}")
            
            # Test the actual file download
            print("🔄 Testing actual file download...")
            start_time = time.time()
            
            download_response = requests.get(redirect_url, stream=True, timeout=30)
            if download_response.status_code == 200:
                # Download first 1MB to test
                downloaded = 0
                for chunk in download_response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded += len(chunk)
                        if downloaded >= 1024 * 1024:  # 1MB
                            break
                
                elapsed = time.time() - start_time
                speed = downloaded / elapsed / 1024 / 1024
                
                print(f"✅ Download test successful!")
                print(f"📊 Downloaded: {downloaded:,} bytes in {elapsed:.1f}s")
                print(f"🚀 Speed: {speed:.1f} MB/s")
            else:
                print(f"❌ Download failed: HTTP {download_response.status_code}")
        else:
            print(f"❌ Redirect failed: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Package download test failed: {str(e)}")

if __name__ == "__main__":
    test_static_servers()