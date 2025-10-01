# OTA Server API Documentation

This OTA (Over-The-Air) server provides secure endpoints for device firmware update management using a build-based system with SQLite database and API key authentication.

## Data Model

### Build Object
Each build has a unique `build_id` and can have an associated OTA package.

```json
{
  "build_id": "build-1001",
  "ota_package": {
    "timestamp": "2025-10-01T10:30:00",
    "package_url": "/packages/ota-build-1001.zip", 
    "checksum": "abc123def456...",
    "patch_notes": "Bug fixes and performance improvements"
  }
}
```

### OTA Package Attributes
- `timestamp`: When the package was created/uploaded
- `package_url`: URL to download the package 
- `checksum`: SHA256 checksum for integrity verification
- `patch_notes`: Human-readable release notes

## Quick Start

### 1. Install Dependencies
```bash
pip install fastapi uvicorn sqlite3 cryptography
```

### 2. Start the Server
```bash
python main.py
```

### 3. Generate API Key
1. Go to http://localhost:8000/admin/api-keys
2. Create a new API key (e.g., "production-device")
3. Copy the generated API key

### 4. Test the API
Update the API key in `test_api.py` and run:
```bash
python test_api.py
```

## Authentication

All API endpoints require authentication using Bearer tokens (API keys).

**Header Format:**
```
Authorization: Bearer YOUR_API_KEY_HERE
```

## Database

The server uses SQLite for data persistence with the following structure:
- `builds` table: Stores build metadata
- `ota_packages` table: Stores package information (one-to-one with builds)
- `api_keys` table: Stores API key information

Data is automatically migrated from `metadata.json` on first startup.

## API Endpoints

All endpoints require valid API key authentication.

### Device Endpoints

#### Check for Updates
**POST** `/api/check-update`

Device sends its current build ID to check for available updates.

**Request:**
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"build_id": "build-1001"}' \
     http://localhost:8000/api/check-update
```

**JSON Payload:**
```json
{
  "build_id": "build-1001"
}
```

**Response (Update Available):**
```json
{
  "status": "update-available",
  "package_url": "/packages/ota-build-1002.zip",
  "build_id": "build-1002", 
  "patch_notes": "New features and security updates"
}
```

**Response (Up to Date):**
```json
{
  "status": "up-to-date"
}
```

#### Validate Package Checksum
**POST** `/api/validate-checksum`

Device sends build ID and checksum to verify package integrity.

**Request:**
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"build_id": "build-1002", "checksum": "abc123def456789..."}' \
     http://localhost:8000/api/validate-checksum
```

**JSON Payload:**
```json
{
  "build_id": "build-1002",
  "checksum": "abc123def456789..."
}
```

**Response:**
```json
{
  "status": "success",
  "is_valid": true,
  "message": "Checksum valid"
}
```

### Information Endpoints

#### Get All Builds
**GET** `/api/builds`

Returns all builds with their OTA package information.

#### Get Specific Build  
**GET** `/api/builds/{build_id}`

Returns information for a specific build.

### Package Download
**GET** `/packages/{filename}`

Download the actual package file (e.g., `/packages/ota-build-1002.zip`).

## Admin Interface

Access the web admin interface at `/admin/metadata` to:
- View all builds and their details
- Add new builds with package uploads
- Manage patch notes and metadata
- Delete builds

## Usage Examples

### Device Update Flow

1. **Check for Update**: Device sends current build ID
2. **Download Package**: If update available, download from provided URL  
3. **Verify Integrity**: Validate downloaded package checksum
4. **Install Update**: Apply the firmware update
5. **Confirm**: Device now reports new build ID

### Test the API

Run the test script to verify all endpoints:

```bash
python test_api.py
```

**Note**: Install requests library first: `pip install requests`

## File Structure

```
packages/
├── ota-build-1001.zip    # Package files (auto-named)
├── ota-build-1002.zip
└── ota-build-1003.zip
metadata.json             # Build metadata database
keys/
├── private.pem          # Signing key
└── public.pem          # Verification key  
```

## Error Responses

All endpoints return appropriate HTTP status codes and error messages:

- `404`: Build or package not found
- `400`: Invalid request data
- `500`: Server error

Example error response:
```json
{
  "status": "error",
  "message": "Build ID not found"
}
```