#!/usr/bin/env python3
"""
Test script for the OTA Server API endpoints with Authentication
Demonstrates the new build and package management functionality
"""

import requests
import json

# Server configuration
BASE_URL = "http://localhost:8000"
# Replace with your actual API key generated from /admin/api-keys
API_KEY = "nTJIxqVrt5-oom8P_EQ-loHgJVCP4Ol_TA6hMpWvjGc"

# Headers for authenticated requests
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def test_authentication():
    """Test API key authentication"""
    print("=== Testing Authentication ===")
    
    if API_KEY == "YOUR_API_KEY_HERE":
        print("⚠️  Please set your API key in the script!")
        print("1. Start the server: python main.py")
        print("2. Go to http://localhost:8000/admin/api-keys")
        print("3. Generate an API key and update the API_KEY variable in this script")
        return False

    # Test with valid API key
    test_data = {"build_id": "build-1001"}
    try:
        response = requests.post(f"{BASE_URL}/api/check-update", json=test_data, headers=HEADERS)
        if response.status_code == 401:
            print("❌ Authentication failed - invalid API key")
            return False
        elif response.status_code in [200, 404]:
            print("✅ Authentication successful")
            return True
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
            return True
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return False

def test_check_update():
    """Test the update check endpoint"""
    print("=== Testing Update Check ===")
    
    # Test with existing build
    test_data = {"build_id": "build-1001"}
    
    try:
        response = requests.post(f"{BASE_URL}/api/check-update", json=test_data, headers=HEADERS)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
    print()

def test_checksum_validation():
    """Test the checksum validation endpoint"""
    print("=== Testing Checksum Validation ===")
    
    # First get the correct checksum
    try:
        builds_response = requests.get(f"{BASE_URL}/api/builds", headers=HEADERS)
        if builds_response.status_code == 200:
            builds = builds_response.json()
            
            # Find a build with an OTA package
            for build_id, build_data in builds.items():
                if build_data.get("ota_package"):
                    correct_checksum = build_data["ota_package"]["checksum"]
                    
                    # Test with correct checksum
                    test_data = {
                        "build_id": build_id,
                        "checksum": correct_checksum
                    }
                    
                    print(f"Testing build {build_id} with correct checksum...")
                    response = requests.post(f"{BASE_URL}/api/validate-checksum", json=test_data, headers=HEADERS)
                    print(f"Status Code: {response.status_code}")
                    print(f"Response: {json.dumps(response.json(), indent=2)}")
                    
                    # Test with incorrect checksum
                    test_data["checksum"] = "incorrect_checksum_123"
                    print(f"Testing build {build_id} with incorrect checksum...")
                    response = requests.post(f"{BASE_URL}/api/validate-checksum", json=test_data, headers=HEADERS)
                    print(f"Status Code: {response.status_code}")
                    print(f"Response: {json.dumps(response.json(), indent=2)}")
                    break
                    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
    print()

def test_get_builds():
    """Test getting all builds"""
    print("=== Testing Get All Builds ===")
    
    try:
        response = requests.get(f"{BASE_URL}/api/builds", headers=HEADERS)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
    print()

def test_get_specific_build():
    """Test getting a specific build"""
    print("=== Testing Get Specific Build ===")
    
    build_id = "build-1001"  # Test with existing build
    
    try:
        response = requests.get(f"{BASE_URL}/api/builds/{build_id}", headers=HEADERS)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
    print()

def main():
    """Run all tests"""
    print("OTA Server API Test Suite")
    print("=" * 40)
    
    # Test authentication first
    if not test_authentication():
        print("\n❌ Authentication test failed. Please check your API key.")
        return
    
    print()
    test_get_builds()
    test_get_specific_build()
    test_check_update()
    test_checksum_validation()
    
    print("✅ Test suite completed!")

if __name__ == "__main__":
    main()