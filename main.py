import json
import hashlib
import os
from pathlib import Path
from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

# ====== Config ======
PACKAGES_DIR = Path("packages")
METADATA_FILE = Path("metadata.json")
PRIVATE_KEY_FILE = Path("keys/private.pem")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ====== Load private key ======
with open(PRIVATE_KEY_FILE, "rb") as f:
    private_key = serialization.load_pem_private_key(
        f.read(), password=None, backend=default_backend()
    )

# ====== FastAPI App ======
app = FastAPI(title="OTA Update Server")

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

def calculate_checksum(build_id: str) -> str:
    """Calculate SHA256 checksum for a package file using standardized naming."""
    filename = f"ota-{build_id}.zip"
    file_path = PACKAGES_DIR / filename
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def get_file_creation_time(build_id: str) -> str:
    """Get formatted creation time for a package file using standardized naming."""
    from datetime import datetime
    
    filename = f"ota-{build_id}.zip"
    file_path = PACKAGES_DIR / filename
    if not file_path.exists():
        return "File not found"
    
    try:
        timestamp = os.path.getctime(file_path)
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except OSError:
        return "Error reading file"

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

@app.post("/check-update")
def check_update(req: UpdateRequest):
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


# --- API Endpoints (device-facing) ---
@app.get("/metadata")
def get_metadata():
    return load_metadata()


@app.get("/update")
def get_update(build_id: str):
    metadata = load_metadata()
    return metadata.get(build_id, {"error": "No update found"})


# --- Admin Web UI ---
@app.get("/admin/metadata", response_class=HTMLResponse)
def admin_metadata(request: Request, message: str = None):
    metadata = load_metadata()
    
    # Add creation timestamps and filenames to metadata for display
    enhanced_metadata = {}
    for build_id, entry in metadata.items():
        enhanced_entry = entry.copy()
        enhanced_entry['creation_time'] = get_file_creation_time(build_id)
        enhanced_entry['filename'] = f"ota-{build_id}.zip"
        enhanced_metadata[build_id] = enhanced_entry
    
    return templates.TemplateResponse(
        "metadata.html", {"request": request, "metadata": enhanced_metadata, "message": message}
    )


@app.post("/admin/metadata/add")
async def add_metadata(
    build_id: str = Form(...), 
    version: str = Form(...), 
    upload_file: UploadFile = File(None),
    overwrite: bool = Form(False)
):
    metadata = load_metadata()
    
    # Check if build ID already exists
    if build_id in metadata and not overwrite:
        existing_version = metadata[build_id].get("version", "unknown")
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
    
    # Add or update metadata
    action = "updated" if build_id in metadata else "added"
    metadata[build_id] = {
        "version": version
    }
    save_metadata(metadata)
    
    # Redirect with success message
    return RedirectResponse(url=f"/admin/metadata?message=Build {build_id} {action} successfully", status_code=303)


@app.post("/admin/metadata/delete")
def delete_metadata(build_id: str = Form(...)):
    metadata = load_metadata()
    if build_id in metadata:
        del metadata[build_id]
        save_metadata(metadata)
    return RedirectResponse(url="/admin/metadata", status_code=303)