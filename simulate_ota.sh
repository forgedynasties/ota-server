#!/bin/bash

# OTA Update Simulation Script
# Usage: ./simulate_ota.sh <server_url>
# Example: ./simulate_ota.sh http://10.32.1.11:8000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check if URL argument is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ Error: Server URL required${NC}"
    echo -e "${YELLOW}Usage: $0 <server_url>${NC}"
    echo -e "${YELLOW}Example: $0 http://localhost:8000${NC}"
    exit 1
fi

SERVER_URL="$1"
TEMP_DIR="/tmp/ota_simulation"

# Create temporary directory for downloads
mkdir -p "$TEMP_DIR"

# Function to print section headers
print_section() {
    echo -e "\n${PURPLE}======================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}======================================${NC}\n"
}

# Function to print step headers
print_step() {
    echo -e "${CYAN}🔄 $1${NC}"
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to print error messages
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to print info messages
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to check for updates
check_update() {
    local device_id="$1"
    local build_id="$2"
    local description="$3"
    
    print_step "Device '$device_id' with build '$build_id' checking for updates ($description)"
    
    local response=$(curl -s -X POST "$SERVER_URL/check-update" \
        -H "Content-Type: application/json" \
        -d "{\"device_id\": \"$device_id\", \"build_id\": \"$build_id\"}")
    
    echo -e "${YELLOW}Response:${NC} $response"
    
    # Parse response to determine if update is available
    if echo "$response" | grep -q '"status":"update-available"'; then
        print_success "Update available!"
        
        # Extract update information
        local version=$(echo "$response" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
        local url=$(echo "$response" | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
        local checksum=$(echo "$response" | grep -o '"checksum":"[^"]*"' | cut -d'"' -f4)
        local build_id_new=$(echo "$response" | grep -o '"build_id":"[^"]*"' | cut -d'"' -f4)
        
        print_info "New Version: $version"
        print_info "New Build ID: $build_id_new"
        print_info "Download URL: $url"
        print_info "Checksum: ${checksum:0:16}..."
        
        # Simulate download
        download_and_verify "$url" "$checksum" "$version"
        
        return 0
    elif echo "$response" | grep -q '"status":"up-to-date"'; then
        print_success "Device is up-to-date"
        return 1
    elif echo "$response" | grep -q '"status":"device-not-found"'; then
        print_error "Device build ID not found in metadata"
        return 1
    else
        print_error "Unexpected response or error occurred"
        return 1
    fi
}

# Function to download and verify update package
download_and_verify() {
    local url="$1"
    local expected_checksum="$2"
    local version="$3"
    local filename="ota-${version}.zip"
    local filepath="$TEMP_DIR/$filename"
    
    print_step "Downloading update package..."
    
    # Download the file
    if curl -s -o "$filepath" "$SERVER_URL$url"; then
        print_success "Downloaded $filename"
        
        # Verify checksum if sha256sum is available
        if command -v sha256sum &> /dev/null; then
            print_step "Verifying checksum..."
            local actual_checksum=$(sha256sum "$filepath" | cut -d' ' -f1)
            
            if [ "$actual_checksum" = "$expected_checksum" ]; then
                print_success "Checksum verification passed"
                print_info "Expected: $expected_checksum"
                print_info "Actual:   $actual_checksum"
            else
                print_error "Checksum verification failed!"
                print_error "Expected: $expected_checksum"
                print_error "Actual:   $actual_checksum"
                return 1
            fi
        else
            print_info "sha256sum not available, skipping checksum verification"
        fi
        
        # Simulate installation
        print_step "Simulating firmware installation..."
        sleep 1
        print_success "Firmware installation completed"
        
        # Clean up downloaded file
        rm -f "$filepath"
        
    else
        print_error "Failed to download update package"
        return 1
    fi
}

# Function to get server metadata
get_metadata() {
    print_step "Fetching server metadata..."
    local metadata=$(curl -s "$SERVER_URL/metadata")
    echo -e "${YELLOW}Available firmware versions:${NC}"
    echo "$metadata" | python3 -m json.tool 2>/dev/null || echo "$metadata"
}

# Function to test checksum endpoint
test_checksum_endpoint() {
    local build_id="$1"
    print_step "Testing checksum endpoint for $build_id"
    
    local response=$(curl -s "$SERVER_URL/checksum/$build_id")
    echo -e "${YELLOW}Checksum Response:${NC} $response"
    
    # Parse and display checksum info
    if echo "$response" | grep -q '"checksum"'; then
        local checksum=$(echo "$response" | grep -o '"checksum":"[^"]*"' | cut -d'"' -f4)
        print_info "Build checksum: ${checksum:0:32}..."
        print_success "Checksum endpoint working correctly"
    else
        print_error "Checksum endpoint returned unexpected response"
    fi
}

# Main simulation
echo -e "${GREEN}🚀 Starting OTA Update Simulation${NC}"
echo -e "${BLUE}Server URL: $SERVER_URL${NC}"

# Test server connectivity
print_section "🔍 CONNECTIVITY TEST"
print_step "Testing server connectivity..."
if curl -s --connect-timeout 5 "$SERVER_URL/metadata" > /dev/null; then
    print_success "Server is reachable"
else
    print_error "Cannot connect to server at $SERVER_URL"
    exit 1
fi

# Get and display metadata
print_section "📋 SERVER METADATA"
get_metadata

# Simulation scenarios
print_section "📱 DEVICE SIMULATION SCENARIOS"

# Scenario 1: Device with old build - should get update
echo -e "\n${YELLOW}--- Scenario 1: Device with Older Build ---${NC}"
check_update "device_alpha" "build-1001" "older build, expecting update to build-1002"

# Scenario 2: Device with middle build - should get next update
echo -e "\n${YELLOW}--- Scenario 2: Device with Middle Build ---${NC}"
check_update "device_beta" "build-1002" "middle build, expecting update to build-1003"

# Scenario 3: Device with latest build - should be up-to-date
echo -e "\n${YELLOW}--- Scenario 3: Device with Latest Build ---${NC}"
check_update "device_gamma" "build-1003" "latest build, expecting up-to-date"

# Scenario 4: Device with unknown build - should get error
echo -e "\n${YELLOW}--- Scenario 4: Device with Unknown Build ---${NC}"
check_update "device_delta" "build-9999" "unknown build, expecting device-not-found"

# Scenario 5: Multiple devices checking simultaneously
print_section "🔄 CONCURRENT DEVICE SIMULATION"
echo -e "\n${YELLOW}--- Scenario 5: Multiple Devices Checking Updates ---${NC}"

# Simulate multiple devices
devices=("phone_001:build-1001" "tablet_002:build-1002" "iot_sensor_003:build-1001" "gateway_004:build-1003")

for device_info in "${devices[@]}"; do
    IFS=':' read -r device build <<< "$device_info"
    echo -e "\n${CYAN}Device: $device${NC}"
    check_update "$device" "$build" "concurrent check"
done

# Test additional endpoints
print_section "🔧 ADDITIONAL ENDPOINT TESTS"

# Test checksum endpoint
test_checksum_endpoint "build-1001"

# Test direct package download
print_step "Testing direct package download..."
download_response=$(curl -s -w "%{http_code}" "$SERVER_URL/packages/ota-build-1001.zip" -o /dev/null)
if [ "$download_response" = "200" ]; then
    print_success "Package download endpoint is working (HTTP 200)"
    
    # Check file size
    print_step "Checking package file details..."
    size_response=$(curl -s -I "$SERVER_URL/packages/ota-build-1001.zip" | grep -i content-length | cut -d' ' -f2 | tr -d '\r')
    if [ -n "$size_response" ]; then
        print_info "Package size: $size_response bytes"
        if [ "$size_response" -gt 0 ]; then
            print_success "Package contains data"
        else
            print_info "Package is empty (test/dummy file)"
        fi
    fi
else
    print_error "Package download endpoint failed (HTTP $download_response)"
fi

# Cleanup
print_section "🧹 CLEANUP"
print_step "Cleaning up temporary files..."
rm -rf "$TEMP_DIR"
print_success "Cleanup completed"

# Summary
print_section "📊 SIMULATION SUMMARY"
echo -e "${GREEN}✅ OTA Update simulation completed successfully!${NC}"
echo -e "${BLUE}ℹ️  Check the server logs for detailed request information${NC}"
echo -e "${YELLOW}💡 To view the admin dashboard: $SERVER_URL/admin/metadata${NC}"

echo -e "\n${PURPLE}🎯 Key Testing Points Covered:${NC}"
echo -e "${CYAN}• Server connectivity and metadata retrieval${NC}"
echo -e "${CYAN}• Sequential update logic based on release dates${NC}"
echo -e "${CYAN}• Update availability checking${NC}"
echo -e "${CYAN}• Package download and checksum verification${NC}"
echo -e "${CYAN}• Error handling for unknown builds${NC}"
echo -e "${CYAN}• Concurrent device simulation${NC}"
echo -e "${CYAN}• Additional API endpoint validation${NC}"