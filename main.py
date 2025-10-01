import json
import hashlib
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, File, Depends, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import sqlite3
from contextlib import contextmanager

# ====== Config ======
PACKAGES_DIR = Path("packages")
METADATA_FILE = Path("metadata.json")
PRIVATE_KEY_FILE = Path("keys/private.pem")
DB_FILE = Path("ota_server.db")
API_KEYS_FILE = Path("api_keys.json")

# Create directories if they don't exist
PACKAGES_DIR.mkdir(exist_ok=True)
Path("keys").mkdir(exist_ok=True)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ====== FastAPI App ======
app = FastAPI(title="OTA Update Server")
security = HTTPBearer()

# ====== Authentication ======
def load_api_keys() -> Dict[str, str]:
    """Load API keys from file"""
    if API_KEYS_FILE.exists():
        return json.loads(API_KEYS_FILE.read_text())
    return {}

def save_api_keys(api_keys: Dict[str, str]):
    """Save API keys to file"""
    API_KEYS_FILE.write_text(json.dumps(api_keys, indent=2))

def generate_api_key() -> str:
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify API key authentication"""
    api_keys = load_api_keys()
    token = credentials.credentials
    
    # Check if token exists in our API keys
    for key_name, key_value in api_keys.items():
        if key_value == token:
            return key_name
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )

# ====== Database Setup ======
@contextmanager
def get_db_connection():
    """Get database connection with context manager"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    """Initialize SQLite database with tables"""
    with get_db_connection() as conn:
        # Builds table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS builds (
                build_id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # OTA Packages table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ota_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                build_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                package_url TEXT NOT NULL,
                checksum TEXT NOT NULL,
                patch_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (build_id) REFERENCES builds (build_id) ON DELETE CASCADE
            )
        ''')
        
        # API Keys table (for management)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT NOT NULL UNIQUE,
                key_value TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        conn.commit()

# Initialize database on startup
init_database()

# ====== Database Operations ======
def create_build_in_db(build_id: str, version: str, timestamp: str, package_url: str, checksum: str, patch_notes: str):
    """Create a new build and OTA package in database"""
    with get_db_connection() as conn:
        # Insert build
        conn.execute(
            "INSERT OR REPLACE INTO builds (build_id, version) VALUES (?, ?)",
            (build_id, version)
        )
        
        # Insert OTA package
        conn.execute(
            "INSERT OR REPLACE INTO ota_packages (build_id, timestamp, package_url, checksum, patch_notes) VALUES (?, ?, ?, ?, ?)",
            (build_id, timestamp, package_url, checksum, patch_notes)
        )
        
        conn.commit()

def get_all_builds_from_db() -> Dict[str, Dict]:
    """Get all builds with their OTA packages from database"""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT b.build_id, b.version, p.timestamp, p.package_url, p.checksum, p.patch_notes
            FROM builds b
            LEFT JOIN ota_packages p ON b.build_id = p.build_id
            ORDER BY b.build_id
        ''')
        
        builds = {}
        for row in cursor.fetchall():
            builds[row['build_id']] = {
                'version': row['version'],
                'timestamp': row['timestamp'],
                'package_url': row['package_url'],
                'checksum': row['checksum'],
                'patch_notes': row['patch_notes']
            }
        
        return builds

def get_build_from_db(build_id: str) -> Optional[Dict]:
    """Get specific build from database"""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT b.build_id, b.version, p.timestamp, p.package_url, p.checksum, p.patch_notes
            FROM builds b
            LEFT JOIN ota_packages p ON b.build_id = p.build_id
            WHERE b.build_id = ?
        ''', (build_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'version': row['version'],
                'timestamp': row['timestamp'],
                'package_url': row['package_url'],
                'checksum': row['checksum'],
                'patch_notes': row['patch_notes']
            }
        return None

def delete_build_from_db(build_id: str):
    """Delete build and associated OTA package from database"""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM builds WHERE build_id = ?", (build_id,))
        conn.commit()

def migrate_json_to_db():
    """Migrate data from metadata.json to SQLite database"""
    if METADATA_FILE.exists():
        print("Migrating metadata.json to database...")
        metadata = json.loads(METADATA_FILE.read_text())
        
        for build_id, entry in metadata.items():
            version = entry.get('version', '1.0.0')
            timestamp = entry.get('timestamp', datetime.now().isoformat())
            package_url = entry.get('package_url', f'/packages/ota-{build_id}.zip')
            checksum = entry.get('checksum', '')
            patch_notes = entry.get('patch_notes', f'Update to version {version}')
            
            # Calculate checksum if missing
            if not checksum:
                try:
                    checksum = calculate_checksum(build_id)
                except:
                    checksum = 'unknown'
            
            create_build_in_db(build_id, version, timestamp, package_url, checksum, patch_notes)
        
        print(f"Migrated {len(metadata)} builds to database")

# Auto-migrate on startup if database is empty
def check_and_migrate():
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM builds")
        count = cursor.fetchone()[0]
        
        if count == 0 and METADATA_FILE.exists():
            migrate_json_to_db()

check_and_migrate()

# ====== Load private key ======
with open(PRIVATE_KEY_FILE, "rb") as f:
    private_key = serialization.load_pem_private_key(
        f.read(), password=None, backend=default_backend()
    )

# ====== FastAPI App ======
app = FastAPI(title="OTA Update Server")
security = HTTPBearer()

# ====== Data Models ======
class OTAPackage(BaseModel):
    timestamp: str
    package_url: str
    checksum: str
    patch_notes: str

class Build(BaseModel):
    build_id: str
    ota_package: Optional[OTAPackage] = None

class UpdateCheckRequest(BaseModel):
    build_id: str

class ChecksumValidationRequest(BaseModel):
    build_id: str
    checksum: str

class UpdateResponse(BaseModel):
    status: str
    package_url: Optional[str] = None
    build_id: Optional[str] = None
    patch_notes: Optional[str] = None
    message: Optional[str] = None

class ChecksumValidationResponse(BaseModel):
    status: str
    is_valid: bool
    message: Optional[str] = None

# Legacy model for backwards compatibility
class UpdateRequest(BaseModel):
    device_id: str
    build_id: str

def sign_data(data: bytes) -> str:
    """Sign data using private key and return hex signature."""
    signature = private_key.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return signature.hex()

def find_package_file(build_id: str) -> Path:
    """Find the actual package file for a build ID"""
    # Try different naming patterns
    patterns = [
        f"ota-{build_id}.zip",
        f"ota-build-{build_id}.zip", 
        f"{build_id}.zip"
    ]
    
    for pattern in patterns:
        file_path = PACKAGES_DIR / pattern
        if file_path.exists():
            return file_path
    
    return None

def calculate_checksum(build_id: str) -> str:
    """Calculate SHA256 checksum for a package file."""
    file_path = find_package_file(build_id)
    if not file_path:
        raise FileNotFoundError(f"Package file not found for build {build_id}")
    
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def get_file_creation_time(build_id: str) -> str:
    """Get formatted creation time for a package file."""
    file_path = find_package_file(build_id)
    if not file_path:
        return "File not found"
    
    try:
        timestamp = os.path.getctime(file_path)
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except OSError:
        return "Error reading file"

def get_build_info(build_id: str, metadata_entry: Dict[str, Any]) -> Build:
    """Convert metadata entry to Build object with OTA package info."""
    package_file = find_package_file(build_id)
    
    if package_file:
        # Use stored metadata or calculate checksum if not available
        checksum = metadata_entry.get("checksum")
        if not checksum:
            checksum = calculate_checksum(build_id)
            
        # Use stored timestamp or file creation time
        timestamp = metadata_entry.get("timestamp")
        if not timestamp:
            timestamp = get_file_creation_time(build_id)
            
        package_url = metadata_entry.get("package_url", f"/packages/{package_file.name}")
        patch_notes = metadata_entry.get("patch_notes", f"Update to version {metadata_entry.get('version', 'unknown')}")
        
        ota_package = OTAPackage(
            timestamp=timestamp,
            package_url=package_url,
            checksum=checksum,
            patch_notes=patch_notes
        )
    else:
        ota_package = None
    
    return Build(
        build_id=build_id,
        ota_package=ota_package
    )

def load_metadata() -> dict:
    if METADATA_FILE.exists():
        return json.loads(METADATA_FILE.read_text())
    return {}

def find_next_build(metadata: dict, current_build: str) -> str:
    """Find the next build ID in sequence based on package file creation timestamp.
    For files with the same timestamp, uses build ID as tiebreaker."""
    
    # Get current build's package file (using standardized naming)
    current_entry = metadata.get(current_build)
    if not current_entry:
        return None
    
    current_filename = f"ota-{current_build}.zip"
    current_file_path = PACKAGES_DIR / current_filename
    if not current_file_path.exists():
        return None
    
    try:
        current_timestamp = os.path.getctime(current_file_path)
    except OSError:
        return None
    
    # Find all builds with package files created after current build's file
    next_builds = []
    for build_id, entry in metadata.items():
        filename = f"ota-{build_id}.zip"
        file_path = PACKAGES_DIR / filename
        if not file_path.exists():
            continue
        
        try:
            file_timestamp = os.path.getctime(file_path)
            
            # Include builds with later creation timestamps
            if file_timestamp > current_timestamp:
                next_builds.append((file_timestamp, build_id))
            # Also include builds with same timestamp but lexicographically higher build ID
            elif file_timestamp == current_timestamp and build_id > current_build:
                next_builds.append((file_timestamp, build_id))
        except OSError:
            continue
    
    # Sort by creation timestamp first, then by build ID for consistent ordering
    if next_builds:
        next_builds.sort(key=lambda x: (x[0], x[1]))
        return next_builds[0][1]
    
    return None  # No next build found

# ====== New API Endpoints ======

@app.get("/api/builds", response_model=Dict[str, Build])
def get_all_builds(api_key: str = Depends(verify_api_key)):
    """Get all builds with their OTA package information."""
    builds_data = get_all_builds_from_db()
    builds = {}
    
    for build_id, metadata_entry in builds_data.items():
        builds[build_id] = get_build_info(build_id, metadata_entry)
    
    return builds

@app.get("/api/builds/{build_id}", response_model=Build)
def get_build(build_id: str, api_key: str = Depends(verify_api_key)):
    """Get specific build information."""
    build_data = get_build_from_db(build_id)
    
    if not build_data:
        raise HTTPException(status_code=404, detail="Build not found")
    
    return get_build_info(build_id, build_data)

@app.post("/api/check-update", response_model=UpdateResponse)
def check_for_update(request: UpdateCheckRequest, api_key: str = Depends(verify_api_key)):
    """
    Device sends build_id to check for updates.
    Returns update package info if available, otherwise indicates up-to-date.
    """
    # Check if current build exists in database
    current_build_data = get_build_from_db(request.build_id)
    if not current_build_data:
        return UpdateResponse(
            status="error",
            message="Build ID not found"
        )

    # Find the next build in sequence
    all_builds = get_all_builds_from_db()
    next_build = find_next_build(all_builds, request.build_id)
    
    if not next_build:
        return UpdateResponse(status="up-to-date")

    # Get next build info
    update_info = all_builds[next_build]
    package_filename = f"ota-{next_build}.zip"
    package_file = PACKAGES_DIR / package_filename

    if not package_file.exists():
        return UpdateResponse(
            status="error",
            message="Update package file not found on server"
        )

    # Build package URL
    package_url = f"/packages/{package_filename}"
    
    # Get patch notes from metadata (if available)
    patch_notes = update_info.get("patch_notes", f"Update to version {update_info.get('version', 'unknown')}")

    return UpdateResponse(
        status="update-available",
        package_url=package_url,
        build_id=next_build,
        patch_notes=patch_notes
    )

@app.post("/api/validate-checksum", response_model=ChecksumValidationResponse)
def validate_package_checksum(request: ChecksumValidationRequest, api_key: str = Depends(verify_api_key)):
    """
    Device sends build_id and checksum to validate package integrity.
    Returns whether the provided checksum matches the server's package checksum.
    """
    build_id = request.build_id
    provided_checksum = request.checksum

    # Check if build exists
    build_data = get_build_from_db(build_id)
    if not build_data:
        return ChecksumValidationResponse(
            status="error",
            is_valid=False,
            message="Build ID not found"
        )

    # Check if package file exists
    package_filename = f"ota-{build_id}.zip"
    package_file = PACKAGES_DIR / package_filename
    
    if not package_file.exists():
        return ChecksumValidationResponse(
            status="error",
            is_valid=False,
            message="Package file not found on server"
        )

    try:
        # Get server checksum from database or calculate it
        server_checksum = build_data.get('checksum')
        if not server_checksum:
            server_checksum = calculate_checksum(build_id)
        
        # Compare checksums
        is_valid = provided_checksum.lower() == server_checksum.lower()
        
        return ChecksumValidationResponse(
            status="success",
            is_valid=is_valid,
            message="Checksum valid" if is_valid else "Checksum mismatch"
        )
        
    except Exception as e:
        return ChecksumValidationResponse(
            status="error",
            is_valid=False,
            message=f"Error calculating checksum: {str(e)}"
        )

# ====== Legacy Endpoints (for backwards compatibility) ======

@app.post("/check-update")
def check_update_legacy(req: UpdateRequest):
    """Legacy endpoint - use /api/check-update instead"""
    metadata = load_metadata()
    current_build = req.build_id

    # Check if current build exists in metadata
    if current_build not in metadata:
        return {"status": "device-not-found", "message": "Current build ID not found"}

    # Find the next build in sequence
    next_build = find_next_build(metadata, current_build)
    
    if not next_build:
        return {"status": "up-to-date"}

    update_info = metadata[next_build]
    package_filename = f"ota-{next_build}.zip"
    package_file = PACKAGES_DIR / package_filename

    if not package_file.exists():
        raise HTTPException(status_code=404, detail="Update package not found")

    checksum = calculate_checksum(next_build)
    signed_checksum = sign_data(checksum.encode())

    return {
        "status": "update-available",
        "version": update_info["version"],
        "build_id": next_build,
        "url": f"/packages/{package_filename}",
        "checksum": checksum,
        "signature": signed_checksum,
    }

@app.get("/checksum/{build_id}")
def get_checksum(build_id: str):
    filename = f"ota-{build_id}.zip"
    file_path = PACKAGES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    checksum = calculate_checksum(build_id)
    signed_checksum = sign_data(checksum.encode())
    return {"build_id": build_id, "filename": filename, "checksum": checksum, "signature": signed_checksum}

@app.get("/packages/{filename}")
def get_package(filename: str):
    file_path = PACKAGES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Package not found")
    return FileResponse(file_path)

# Load metadata.json
def load_metadata():
    if not METADATA_FILE.exists():
        return {}
    with open(METADATA_FILE, "r") as f:
        return json.load(f)

# Save metadata.json
def save_metadata(data):
    with open(METADATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# --- Legacy API Endpoints (for backwards compatibility) ---
@app.get("/metadata")
def get_metadata_legacy():
    """Legacy endpoint - returns data in old JSON format"""
    builds_data = get_all_builds_from_db()
    # Convert to old format for backwards compatibility
    legacy_format = {}
    for build_id, data in builds_data.items():
        if data:
            legacy_format[build_id] = {
                "version": data.get("version"),
                "filename": f"ota-{build_id}.zip",
                "release_date": data.get("timestamp", "").split("T")[0] if data.get("timestamp") else ""
            }
    return legacy_format

@app.get("/update")
def get_update_legacy(build_id: str):
    """Legacy endpoint - use /api/builds/{build_id} instead"""
    build_data = get_build_from_db(build_id)
    if build_data:
        return {
            "version": build_data.get("version"),
            "filename": f"ota-{build_id}.zip",
            "release_date": build_data.get("timestamp", "").split("T")[0] if build_data.get("timestamp") else ""
        }
    return {"error": "No update found"}


# --- Admin Web UI ---
@app.get("/admin/metadata", response_class=HTMLResponse)
def admin_metadata(request: Request, message: str = None):
    builds_data = get_all_builds_from_db()
    
    # Add creation timestamps and filenames to builds data for display
    enhanced_metadata = {}
    for build_id, entry in builds_data.items():
        enhanced_entry = entry.copy() if entry else {}
        enhanced_entry['creation_time'] = enhanced_entry.get('timestamp', get_file_creation_time(build_id))
        enhanced_entry['filename'] = f"ota-{build_id}.zip"
        enhanced_metadata[build_id] = enhanced_entry
    
    return templates.TemplateResponse(
        "metadata.html", {"request": request, "metadata": enhanced_metadata, "message": message}
    )


@app.post("/admin/metadata/add")
async def add_metadata(
    build_id: str = Form(...), 
    version: str = Form(...),
    patch_notes: str = Form(""),
    upload_file: UploadFile = File(None),
    overwrite: bool = Form(False)
):
    metadata = load_metadata()
    
    # Check if build ID already exists
    existing_build = get_build_from_db(build_id)
    if existing_build and not overwrite:
        existing_version = existing_build.get("version", "unknown")
        return HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>Build ID Conflict</title>
                <style>
                    body {{ font-family: 'Segoe UI', sans-serif; background: #f5f7fa; padding: 40px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
                    .alert {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                    .btn {{ padding: 12px 25px; margin: 10px; border: none; border-radius: 5px; cursor: pointer; font-size: 1em; }}
                    .btn-primary {{ background: #667eea; color: white; }}
                    .btn-danger {{ background: #ff6b6b; color: white; }}
                    .btn-secondary {{ background: #6c757d; color: white; }}
                    .form-group {{ margin-bottom: 15px; }}
                    .form-group label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>⚠️ Build ID Conflict</h2>
                    <div class="alert">
                        <strong>Build ID "{build_id}" already exists!</strong><br>
                        Current version: <code>{existing_version}</code><br>
                        New version: <code>{version}</code>
                    </div>
                    
                    <h3>What would you like to do?</h3>
                    
                    <form method="post" action="/admin/metadata/add" enctype="multipart/form-data" style="margin-bottom: 20px;">
                        <input type="hidden" name="build_id" value="{build_id}">
                        <input type="hidden" name="version" value="{version}">
                        <input type="hidden" name="overwrite" value="true">
                        {"<input type='hidden' name='upload_file' value='temp'>" if upload_file and upload_file.filename else ""}
                        <button type="submit" class="btn btn-danger">🔄 Overwrite Existing Entry</button>
                    </form>
                    
                    <form method="get" action="/admin/metadata" style="display: inline;">
                        <button type="submit" class="btn btn-secondary">❌ Cancel and Go Back</button>
                    </form>
                    
                    <div style="margin-top: 20px; padding: 15px; background: #e3f2fd; border-radius: 5px;">
                        <h4>💡 Suggestions:</h4>
                        <ul>
                            <li>Use a different build ID like <code>{build_id}-v2</code> or <code>{build_id}-{version}</code></li>
                            <li>Update the version number if this is a newer release</li>
                            <li>Check if you really want to replace the existing firmware</li>
                        </ul>
                    </div>
                </div>
            </body>
            </html>
            """,
            status_code=409
        )
    
    # Use standardized filename: ota-{build_id}.zip
    standard_filename = f"ota-{build_id}.zip"
    file_path = PACKAGES_DIR / standard_filename
    
    # Handle file upload if provided
    if upload_file and upload_file.filename:
        try:
            with open(file_path, "wb") as buffer:
                content = await upload_file.read()
                buffer.write(content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    else:
        # Check if file already exists with standard naming
        if not file_path.exists():
            raise HTTPException(status_code=400, detail=f"No file uploaded and {standard_filename} does not exist in packages directory")
    
        # Calculate checksum and timestamp for the package
        try:
            checksum = calculate_checksum(build_id)
            timestamp = datetime.now().isoformat()
            # Use actual filename that was uploaded
            actual_file = find_package_file(build_id)
            package_url = f"/packages/{actual_file.name if actual_file else standard_filename}"
            
            # Add or update build in database
            existing_build = get_build_from_db(build_id)
            action = "updated" if existing_build else "added"
            
            create_build_in_db(
                build_id=build_id,
                version=version,
                timestamp=timestamp,
                package_url=package_url,
                checksum=checksum,
                patch_notes=patch_notes or f"Update to version {version}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process package: {str(e)}")
    
    # Redirect with success message
    return RedirectResponse(url=f"/admin/metadata?message=Build {build_id} {action} successfully", status_code=303)


@app.post("/admin/metadata/delete")
def delete_metadata(build_id: str = Form(...)):
    delete_build_from_db(build_id)
    return RedirectResponse(url="/admin/metadata", status_code=303)

# ====== API Key Management ======
@app.get("/admin/api-keys", response_class=HTMLResponse)
def admin_api_keys(request: Request, message: str = None):
    """Admin interface for API key management"""
    api_keys = load_api_keys()
    return templates.TemplateResponse(
        "api_keys.html", {"request": request, "api_keys": api_keys, "message": message}
    )

@app.post("/admin/api-keys/generate")
def generate_new_api_key(key_name: str = Form(...)):
    """Generate a new API key"""
    api_keys = load_api_keys()
    
    if key_name in api_keys:
        return RedirectResponse(
            url=f"/admin/api-keys?message=API key '{key_name}' already exists", 
            status_code=303
        )
    
    new_key = generate_api_key()
    api_keys[key_name] = new_key
    save_api_keys(api_keys)
    
    return RedirectResponse(
        url=f"/admin/api-keys?message=API key '{key_name}' generated successfully: {new_key}", 
        status_code=303
    )

@app.post("/admin/api-keys/delete")
def delete_api_key(key_name: str = Form(...)):
    """Delete an API key"""
    api_keys = load_api_keys()
    
    if key_name in api_keys:
        del api_keys[key_name]
        save_api_keys(api_keys)
    
    return RedirectResponse(url="/admin/api-keys", status_code=303)