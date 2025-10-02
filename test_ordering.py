#!/usr/bin/env python3
"""
Test script to verify timestamp-based build ordering functionality
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

# Test API key (you may need to generate this first)
API_KEY = "YOUR_API_KEY_HERE"
HEADERS = {"X-API-Key": API_KEY}

def test_build_ordering():
    """Test that builds are ordered correctly by timestamp"""
    print("Testing build ordering by timestamp...")
    
    # Get all builds to see current state
    response = requests.get(f"{BASE_URL}/api/builds", headers=HEADERS)
    if response.status_code == 200:
        builds = response.json()
        print(f"Current builds: {list(builds.keys())}")
        
        # Test update sequence
        for build_id in builds.keys():
            print(f"\nTesting from build: {build_id}")
            check_response = requests.post(
                f"{BASE_URL}/api/check-update",
                headers=HEADERS,
                json={"build_id": build_id}
            )
            
            if check_response.status_code == 200:
                update_info = check_response.json()
                print(f"  Status: {update_info['status']}")
                if update_info['status'] == 'update-available':
                    print(f"  Next build: {update_info['build_id']}")
                    print(f"  Package URL: {update_info['package_url']}")
                else:
                    print("  Device is up to date")
            else:
                print(f"  Error: {check_response.text}")
    else:
        print(f"Failed to get builds: {response.text}")

def show_timestamp_order():
    """Show builds in timestamp order"""
    print("\nShowing builds in timestamp order...")
    
    response = requests.get(f"{BASE_URL}/api/builds", headers=HEADERS)
    if response.status_code == 200:
        builds = response.json()
        
        # Sort by timestamp
        build_list = []
        for build_id, data in builds.items():
            timestamp = data.get('timestamp', '')
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                build_list.append((dt, build_id, data))
            except:
                print(f"Invalid timestamp for {build_id}: {timestamp}")
                continue
        
        build_list.sort(key=lambda x: x[0])
        
        print("\nChronological order (oldest to newest):")
        for i, (dt, build_id, data) in enumerate(build_list, 1):
            print(f"  {i}. {build_id} (v{data.get('version', '?')}) - {dt.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    try:
        show_timestamp_order()
        test_build_ordering()
    except requests.exceptions.ConnectionError:
        print("Error: Cannot connect to server. Make sure the OTA server is running on localhost:8000")
    except Exception as e:
        print(f"Error: {e}")