#!/usr/bin/env python3
"""
Migration script to update existing metadata.json to the new format
Adds timestamp, package_url, checksum, and patch_notes fields
"""

import json
import hashlib
import os
from pathlib import Path
from datetime import datetime

# ====== Config ======
PACKAGES_DIR = Path("packages")
METADATA_FILE = Path("metadata.json")

def calculate_checksum(build_id: str) -> str:
    """Calculate SHA256 checksum for a package file."""
    filename = f"ota-{build_id}.zip"
    file_path = PACKAGES_DIR / filename
    
    if not file_path.exists():
        print(f"Warning: Package file {filename} not found for build {build_id}")
        return ""
    
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def get_file_timestamp(build_id: str) -> str:
    """Get formatted creation time for a package file."""
    filename = f"ota-{build_id}.zip"
    file_path = PACKAGES_DIR / filename
    
    if not file_path.exists():
        return datetime.now().isoformat()
    
    try:
        timestamp = os.path.getctime(file_path)
        return datetime.fromtimestamp(timestamp).isoformat()
    except OSError:
        return datetime.now().isoformat()

def migrate_metadata():
    """Migrate existing metadata to new format."""
    print("Starting metadata migration...")
    
    # Load existing metadata
    if not METADATA_FILE.exists():
        print("No metadata.json found. Nothing to migrate.")
        return
    
    with open(METADATA_FILE, "r") as f:
        metadata = json.load(f)
    
    # Backup original
    backup_file = METADATA_FILE.with_suffix('.json.backup')
    with open(backup_file, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Created backup: {backup_file}")
    
    # Migrate each build
    updated_metadata = {}
    
    for build_id, entry in metadata.items():
        print(f"Migrating build: {build_id}")
        
        # Keep existing fields
        updated_entry = entry.copy()
        
        # Add new fields if not present
        if "timestamp" not in updated_entry:
            updated_entry["timestamp"] = get_file_timestamp(build_id)
        
        if "package_url" not in updated_entry:
            updated_entry["package_url"] = f"/packages/ota-{build_id}.zip"
        
        if "checksum" not in updated_entry:
            updated_entry["checksum"] = calculate_checksum(build_id)
        
        if "patch_notes" not in updated_entry:
            version = entry.get("version", "unknown")
            updated_entry["patch_notes"] = f"Update to version {version}"
        
        updated_metadata[build_id] = updated_entry
        print(f"  Added: timestamp, package_url, checksum, patch_notes")
    
    # Save updated metadata
    with open(METADATA_FILE, "w") as f:
        json.dump(updated_metadata, f, indent=2)
    
    print(f"\nMigration completed! Updated {len(updated_metadata)} builds.")
    print("Original metadata backed up to metadata.json.backup")

def show_migration_preview():
    """Show what the migration will do without making changes."""
    print("Migration Preview:")
    print("=" * 50)
    
    if not METADATA_FILE.exists():
        print("No metadata.json found.")
        return
    
    with open(METADATA_FILE, "r") as f:
        metadata = json.load(f)
    
    for build_id, entry in metadata.items():
        print(f"\nBuild: {build_id}")
        print(f"  Current fields: {list(entry.keys())}")
        
        missing_fields = []
        if "timestamp" not in entry:
            missing_fields.append("timestamp")
        if "package_url" not in entry:
            missing_fields.append("package_url")
        if "checksum" not in entry:
            missing_fields.append("checksum")
        if "patch_notes" not in entry:
            missing_fields.append("patch_notes")
        
        if missing_fields:
            print(f"  Will add: {', '.join(missing_fields)}")
        else:
            print("  Already up to date")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        show_migration_preview()
    else:
        migrate_metadata()