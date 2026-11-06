#!/usr/bin/env python3
"""
Automated Security Tests: File Upload Safety & Error Information Leakage Defense
Verifies:
1. Binary magic byte inspection rejects extension spoofing and active scripts.
2. File size limits are enforced.
3. Path traversal in filenames is neutralized via UUID renaming.
4. Storage is isolated outside web root with no-execution permissions.
5. Error responses are generic and contain zero stack traces or internal paths.
"""

import os
import sys
import tempfile

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.file_validator import (
    validate_and_store_upload,
    detect_mime_by_magic_bytes,
    FileValidationError
)

def test_magic_byte_detection():
    # 1. Authentic PNG
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 30
    assert detect_mime_by_magic_bytes(png_bytes) == "image/png"

    # 2. Authentic JPEG
    jpeg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 30
    assert detect_mime_by_magic_bytes(jpeg_bytes) == "image/jpeg"

    # 3. Authentic PDF
    pdf_bytes = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj" + b"\x00" * 30
    assert detect_mime_by_magic_bytes(pdf_bytes) == "application/pdf"

    # 4. Text / Script pretending to be an image
    fake_png = b"<?php phpinfo(); ?>\x00\x00\x00\x00"
    assert detect_mime_by_magic_bytes(fake_png) is None
    print("[PASS] Magic-byte detection correctly identifies binary headers.")

def test_rejection_of_extension_spoofing():
    # Attacker names file 'invoice.png' but payload is PHP script
    malicious_php_payload = b"<?php system($_GET['cmd']); ?>" + b"\x00" * 20
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            validate_and_store_upload(
                raw_bytes=malicious_php_payload,
                client_supplied_filename="invoice.png",
                declared_content_type="image/png",
                correlation_id="test-corr-01",
                storage_directory=tmpdir
            )
            assert False, "Failed to reject fake PNG containing PHP script!"
        except FileValidationError as e:
            assert e.code == "UNSUPPORTED_MEDIA_TYPE"
            assert "File format is not permitted" in e.user_message
    print("[PASS] Extension spoofing strictly rejected via content magic bytes.")

def test_rejection_of_dangerous_extensions():
    # Attacker tries SVG with valid XML or script extensions
    svg_payload = b"<?xml version='1.0'?><svg onload='alert(1)'></svg>"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            validate_and_store_upload(
                raw_bytes=svg_payload,
                client_supplied_filename="vector_icon.svg",
                declared_content_type="image/svg+xml",
                correlation_id="test-corr-02",
                storage_directory=tmpdir
            )
            assert False, "Failed to reject SVG upload!"
        except FileValidationError as e:
            assert e.code in ("UNSUPPORTED_MEDIA_TYPE", "PROHIBITED_FILE_EXTENSION")
    print("[PASS] Prohibited file extensions (SVG, scripts) strictly blocked.")

def test_file_size_enforcement():
    # Create oversized JPEG (> 5MB)
    oversized_jpeg = b"\xFF\xD8\xFF\xE0" + b"\xAA" * (6 * 1024 * 1024)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            validate_and_store_upload(
                raw_bytes=oversized_jpeg,
                client_supplied_filename="large_photo.jpg",
                declared_content_type="image/jpeg",
                correlation_id="test-corr-03",
                storage_directory=tmpdir
            )
            assert False, "Failed to enforce 5MB image size limit!"
        except FileValidationError as e:
            assert e.code == "FILE_TOO_LARGE"
            assert "exceeds maximum permissible size" in e.user_message
    print("[PASS] Strict file size boundaries enforced.")

def test_filename_neutralization_and_permissions():
    # Attacker submits path traversal in filename: ../../../../etc/cron.daily/exploit
    valid_pdf = b"%PDF-1.7\n" + b"\x00" * 100
    traversal_filename = "../../../../etc/cron.daily/exploit.pdf"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        meta, stored_path = validate_and_store_upload(
            raw_bytes=valid_pdf,
            client_supplied_filename=traversal_filename,
            declared_content_type="application/pdf",
            correlation_id="test-corr-04",
            storage_directory=tmpdir
        )
        
        # Verify stored path is strictly inside tmpdir
        assert os.path.dirname(stored_path) == tmpdir
        # Verify stored filename is random UUID hex, not client's traversal string
        assert "exploit" not in meta["stored_filename"]
        assert meta["stored_filename"].endswith(".pdf")
        assert len(meta["stored_filename"]) == 36 # 32 hex + .pdf
        
        # Verify file permissions on POSIX systems: non-executable
        if os.name != 'nt':
            mode = os.stat(stored_path).st_mode & 0o777
            assert mode & 0o111 == 0, "Uploaded file has executable bit set!"
    print("[PASS] Filenames neutralized with random UUIDs; zero execution permissions.")

def test_error_handling_and_information_leakage():
    # Inspect nginx.conf and ensure no raw server stack leaks
    with open('nginx.conf', 'r', encoding='utf-8') as f:
        conf = f.read()

    assert "server_tokens off;" in conf
    assert "error_page 500 502 503 504 = @err_5xx;" in conf
    assert "error_page 413 = @err_413;" in conf
    assert "error_page 415 = @err_415;" in conf
    
    # Extract only lines that return responses to clients
    return_lines = [line.strip() for line in conf.splitlines() if line.strip().startswith('return ')]
    forbidden_leak_strings = ["traceback", "stack", "psycopg", "pg_", "syntax error at or near", "/home/", "/var/www/"]
    for ret_line in return_lines:
        for term in forbidden_leak_strings:
            assert term not in ret_line.lower(), f"Nginx returned client response contains leak term '{term}': {ret_line}"
    print("[PASS] Error handling configuration returns sanitized JSON with zero stack or path leakage.")

if __name__ == '__main__':
    print("Running Security & Upload Validation Test Suite...\n")
    test_magic_byte_detection()
    test_rejection_of_extension_spoofing()
    test_rejection_of_dangerous_extensions()
    test_file_size_enforcement()
    test_filename_neutralization_and_permissions()
    test_error_handling_and_information_leakage()
    print("\nALL FILE UPLOAD & ERROR HANDLING TESTS PASSED (100% GREEN)")
    sys.exit(0)
