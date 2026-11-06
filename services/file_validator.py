"""
FoodBridge Secure File Upload Validation & Storage Engine
Enforces:
1. Binary Magic Number verification (Content inspection, not just file extensions).
2. Strict File Size thresholds (5MB for images, 10MB for PDFs).
3. Client filename neutralization (UUIDv4 replacement to prevent path traversal).
4. Storage outside web root with zero execution permissions (chmod 0o640).
5. Sanitized client errors with detailed server-side audit logging.
"""

import os
import uuid
import logging
from typing import Dict, Any, Tuple, Optional

# Structured Logger for Security Audit
logger = logging.getLogger("foodbridge.security.uploads")

# Magic Byte Signatures for Allowed Binary Types
MAGIC_SIGNATURES = {
    "image/jpeg": [
        b"\xFF\xD8\xFF\xDB",
        b"\xFF\xD8\xFF\xE0",
        b"\xFF\xD8\xFF\xE1",
        b"\xFF\xD8\xFF\xEE"
    ],
    "image/png": [
        b"\x89PNG\r\n\x1a\n"
    ],
    "application/pdf": [
        b"%PDF-"
    ]
}

# Strict File Size Limits
SIZE_LIMITS = {
    "image/jpeg": 5 * 1024 * 1024,      # 5 Megabytes
    "image/png": 5 * 1024 * 1024,       # 5 Megabytes
    "application/pdf": 10 * 1024 * 1024 # 10 Megabytes
}

EXTENSION_MAP = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "application/pdf": "pdf"
}

# Safe Storage Directory (Configured outside web root)
DEFAULT_STORAGE_ROOT = os.getenv("STORAGE_ROOT", "/var/foodbridge/storage/uploads")

class FileValidationError(Exception):
    """Sanitized application exception for upload rejections."""
    def __init__(self, code: str, user_message: str):
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message

def detect_mime_by_magic_bytes(header: bytes) -> Optional[str]:
    """Inspects raw leading binary bytes to determine genuine MIME type."""
    if len(header) < 8:
        return None

    # Check PDF
    if header.startswith(b"%PDF-"):
        return "application/pdf"

    # Check PNG
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    # Check JPEG (Standard SOI 0xFFD8 followed by marker)
    if header.startswith(b"\xFF\xD8\xFF"):
        return "image/jpeg"

    return None

def validate_and_store_upload(
    raw_bytes: bytes,
    client_supplied_filename: str,
    declared_content_type: str,
    correlation_id: str,
    storage_directory: str = DEFAULT_STORAGE_ROOT
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Validates binary content against magic bytes, size limits, and stores
    safely outside web root with zero execution permissions.
    """
    byte_count = len(raw_bytes)

    # 1. Minimum Content Size Check
    if byte_count < 16:
        logger.warning(
            "Upload rejected: payload too small or empty",
            extra={"correlation_id": correlation_id, "size": byte_count, "client_name": client_supplied_filename}
        )
        raise FileValidationError(
            "PAYLOAD_TOO_SMALL",
            "The submitted file is empty or corrupted."
        )

    # 2. Inspect Binary Magic Numbers
    detected_mime = detect_mime_by_magic_bytes(raw_bytes[:32])
    if not detected_mime:
        logger.warning(
            "Upload rejected: unapproved magic bytes",
            extra={
                "correlation_id": correlation_id,
                "first_8_bytes": raw_bytes[:8].hex(),
                "declared_mime": declared_content_type,
                "client_name": client_supplied_filename
            }
        )
        raise FileValidationError(
            "UNSUPPORTED_MEDIA_TYPE",
            "File format is not permitted. Only verified PDF, JPEG, and PNG files are accepted."
        )

    # 3. Disallow SVG, HTML, and script extensions entirely
    sanitized_client_name = client_supplied_filename.lower()
    prohibited_extensions = [".svg", ".html", ".htm", ".xhtml", ".php", ".phtml", ".jsp", ".exe", ".sh", ".py", ".js"]
    if any(sanitized_client_name.endswith(ext) for ext in prohibited_extensions):
        logger.error(
            "Upload rejected: prohibited executable extension detected",
            extra={"correlation_id": correlation_id, "client_name": client_supplied_filename}
        )
        raise FileValidationError(
            "PROHIBITED_FILE_EXTENSION",
            "Active script and executable file formats are strictly prohibited."
        )

    # 4. Strict File Size Check per Detected Type
    max_allowed = SIZE_LIMITS.get(detected_mime, 5 * 1024 * 1024)
    if byte_count > max_allowed:
        max_mb = max_allowed // (1024 * 1024)
        logger.warning(
            "Upload rejected: size exceeds threshold",
            extra={"correlation_id": correlation_id, "size": byte_count, "max_allowed": max_allowed}
        )
        raise FileValidationError(
            "FILE_TOO_LARGE",
            f"File exceeds maximum permissible size of {max_mb} MB."
        )

    # 5. Neutralize Filename via Cryptographic UUIDv4
    safe_ext = EXTENSION_MAP[detected_mime]
    stored_filename = f"{uuid.uuid4().hex}.{safe_ext}"
    destination_path = os.path.join(storage_directory, stored_filename)

    # Ensure storage directory exists
    os.makedirs(storage_directory, mode=0o750, exist_ok=True)

    # 6. Write File with Restrictive Permissions (0o640 - No Execution)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(destination_path, flags, 0o640)
        with os.fdopen(fd, "wb") as f:
            f.write(raw_bytes)
    except Exception as e:
        # Full stack trace logged internally; NEVER exposed to user
        logger.critical(
            "Storage write failure",
            exc_info=True,
            extra={"correlation_id": correlation_id, "destination": destination_path}
        )
        raise FileValidationError(
            "STORAGE_FAILURE",
            "An internal storage error occurred while processing the document."
        )

    logger.info(
        "Upload validated and stored successfully",
        extra={
            "correlation_id": correlation_id,
            "stored_name": stored_filename,
            "mime_type": detected_mime,
            "size_bytes": byte_count
        }
    )

    metadata = {
        "stored_filename": stored_filename,
        "verified_mime_type": detected_mime,
        "size_bytes": byte_count,
        "safe_extension": safe_ext
    }

    return metadata, destination_path

