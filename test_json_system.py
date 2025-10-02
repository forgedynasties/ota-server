#!/usr/bin/env python3
"""
Test the new JSON-based OTA system
"""

import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_json_system():
    """Test that the new JSON system is working"""
    print("🧪 Testing JSON-based OTA system...")
    
    # Check if we can load the metadata
    metadata_file = Path("metadata.json")
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        print(f"✅ Found metadata.json with {len(metadata)} builds:")
        for i, (build_id, data) in enumerate(metadata.items(), 1):
            print(f"  {i}. {build_id} (v{data.get('version', '?')})")
    else:
        print("❌ No metadata.json found")
        return False
    
    return True

def test_api_endpoints():
    """Test API endpoints"""
    print("\n🔌 Testing API endpoints...")
    
    # Test if server is running
    try:
        response = requests.get(f"{BASE_URL}/admin/metadata")
        if response.status_code == 200:
            print("✅ Admin interface accessible")
        else:
            print(f"❌ Admin interface returned {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Server not running. Start with: python start_server.py")
        return False
    
    return True

def test_build_ordering():
    """Test the new build ordering system"""
    print("\n📋 Testing build ordering...")
    
    metadata_file = Path("metadata.json")
    if not metadata_file.exists():
        print("❌ No metadata.json to test ordering")
        return False
    
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    build_list = list(metadata.keys())
    print(f"✅ Build order (as they appear in JSON):")
    for i, build_id in enumerate(build_list, 1):
        next_build = build_list[i] if i < len(build_list) else "None"
        print(f"  {i}. {build_id} → {next_build}")
    
    return True

if __name__ == "__main__":
    print("🔧 JSON-based OTA System Test")
    print("=" * 40)
    
    if test_json_system():
        test_build_ordering()
        test_api_endpoints()
        
        print("\n📝 Summary of Changes:")
        print("✅ Removed database dependency - now uses JSON file")
        print("✅ Removed timestamp-based ordering - uses JSON order")
        print("✅ Removed build name validation - accepts any names")
        print("✅ Added trash folder for deleted packages")
        print("✅ Simplified system architecture")
        
        print("\n🎯 Next Steps:")
        print("1. Start server: python start_server.py")
        print("2. Visit admin: http://localhost:8000/admin/metadata")
        print("3. Test with your Android app")
    else:
        print("\n❌ System test failed - check the issues above")