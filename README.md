# OTA Update Server

A secure Over-The-Air (OTA) update server built with FastAPI that provides cryptographically signed firmware updates for IoT devices.

## Features

- **Secure Updates**: All update packages are cryptographically signed using RSA-SHA256
- **Version Management**: Track different firmware versions and build IDs
- **Checksum Verification**: SHA256 checksums for integrity verification
- **Admin Web Interface**: Easy-to-use web UI for managing firmware metadata
- **RESTful API**: Simple REST endpoints for device integration
- **File Serving**: Direct download of update packages

## Project Structure

```
ota-server/
├── main.py                 # Main FastAPI application
├── metadata.json           # Firmware version metadata
├── keys/
│   ├── private.pem         # RSA private key for signing
│   └── public.pem          # RSA public key for verification
├── packages/               # Firmware update packages
│   ├── ota-1.0.0.zip
│   └── ota-1.1.0.zip
└── templates/
    └── metadata.html       # Admin web interface template
```

## Prerequisites

- Python 3.7+
- Required Python packages (install via pip):

```bash
pip install fastapi uvicorn cryptography jinja2 python-multipart
```

## Setup

### 1. Generate RSA Key Pair

First, generate the RSA key pair for signing updates:

```bash
# Create keys directory
mkdir keys

# Generate private key
openssl genrsa -out keys/private.pem 2048

# Generate public key
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

### 2. Create Directory Structure

```bash
# Create packages directory for firmware files
mkdir packages

# Create templates directory (if not exists)
mkdir templates
```

### 3. Initialize Metadata

Create an initial `metadata.json` file or let the server create it automatically:

```json
{
  "build-1001": {
    "version": "1.1.0",
    "filename": "ota-1.1.0.zip"
  }
}
```

## Usage

### Starting the Server

```bash
# Development mode (with auto-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will start on `http://localhost:8000`

### Admin Web Interface

Navigate to `http://localhost:8000/admin/metadata` to access the web-based admin interface where you can:

- View all firmware entries
- Add new firmware entries
- Delete existing entries

### API Endpoints

#### Device-Facing Endpoints

**Check for Updates**
```http
POST /check-update
Content-Type: application/json

{
  "device_id": "device123",
  "build_id": "build-1001"
}
```

Response:
```json
{
  "status": "update-available",
  "version": "1.2.0",
  "url": "/packages/ota-1.2.0.zip",
  "checksum": "sha256-hash-here",
  "signature": "signed-checksum-here"
}
```

**Download Package**
```http
GET /packages/{filename}
```

**Get Checksum**
```http
GET /checksum/{filename}
```

Response:
```json
{
  "filename": "ota-1.1.0.zip",
  "checksum": "sha256-hash",
  "signature": "signed-checksum"
}
```

**Get Metadata**
```http
GET /metadata
```

**Get Update Info**
```http
GET /update?build_id=build-1001
```

#### Admin Endpoints

**View Admin Interface**
```http
GET /admin/metadata
```

**Add Firmware Entry**
```http
POST /admin/metadata/add
Content-Type: application/x-www-form-urlencoded

build_id=build-1002&version=1.2.0&filename=ota-1.2.0.zip
```

**Delete Firmware Entry**
```http
POST /admin/metadata/delete
Content-Type: application/x-www-form-urlencoded

build_id=build-1001
```

### Device Integration Example

Here's how a device might check for and download updates:

```python
import requests
import hashlib
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# Load public key for verification
with open("public.pem", "rb") as f:
    public_key = serialization.load_pem_public_key(f.read())

# Check for update
response = requests.post("http://your-server:8000/check-update", json={
    "device_id": "device123",
    "build_id": "build-1001"
})

update_info = response.json()

if update_info["status"] == "update-available":
    # Download the update package
    package_url = f"http://your-server:8000{update_info['url']}"
    package_response = requests.get(package_url)
    
    # Verify checksum
    calculated_checksum = hashlib.sha256(package_response.content).hexdigest()
    
    if calculated_checksum == update_info["checksum"]:
        # Verify signature
        try:
            signature_bytes = bytes.fromhex(update_info["signature"])
            public_key.verify(
                signature_bytes,
                update_info["checksum"].encode(),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            print("Update verified successfully!")
            # Proceed with update installation
        except Exception as e:
            print(f"Signature verification failed: {e}")
    else:
        print("Checksum verification failed!")
```

## Security Features

1. **Digital Signatures**: All checksums are signed with RSA-SHA256 to prevent tampering
2. **Checksum Verification**: SHA256 checksums ensure file integrity
3. **Secure Key Management**: Private keys are stored securely on the server
4. **Build ID Tracking**: Prevents downgrade attacks by tracking device build versions

## Configuration

Key configuration options can be modified in `main.py`:

- `PACKAGES_DIR`: Directory containing firmware packages
- `METADATA_FILE`: Path to metadata JSON file
- `PRIVATE_KEY_FILE`: Path to RSA private key

## Development

### Adding New Firmware

1. Place your firmware file in the `packages/` directory
2. Use the admin web interface to add the metadata entry, or
3. Directly edit `metadata.json` and restart the server

### Testing

```bash
# Test the server is running
curl http://localhost:8000/metadata

# Test update check
curl -X POST http://localhost:8000/check-update \
  -H "Content-Type: application/json" \
  -d '{"device_id": "test", "build_id": "build-1001"}'
```

## Production Deployment

For production deployment:

1. Use a production ASGI server like Gunicorn with Uvicorn workers
2. Set up proper SSL/TLS certificates
3. Configure proper firewall rules
4. Implement rate limiting and authentication as needed
5. Set up monitoring and logging

```bash
# Example production command
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## License

This project is provided as-is for educational and development purposes.