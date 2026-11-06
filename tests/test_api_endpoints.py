#!/usr/bin/env python3
"""
Automated In-Memory Contract Tests for FoodBridge Operational Logistics API
Tests handler logic directly using mock I/O streams without socket binding.
"""

import os
import sys
import json
import io
from http.server import HTTPServer

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.api_server import FoodBridgeRequestHandler

class MockSocket:
    def makefile(self, *args, **kwargs):
        return io.BytesIO()

class MockServer:
    server_address = ('127.0.0.1', 8080)

def invoke_handler(method: str, path: str, body: bytes = b"", headers: dict = None):
    req_headers = {
        "Content-Length": str(len(body)),
        "Content-Type": "application/json",
        "X-Request-ID": "test-req-991"
    }
    if headers:
        req_headers.update(headers)

    header_lines = [f"{method} {path} HTTP/1.1"]
    for k, v in req_headers.items():
        header_lines.append(f"{k}: {v}")
    header_raw = "\r\n".join(header_lines) + "\r\n\r\n"

    rfile = io.BytesIO(header_raw.encode("utf-8") + body)
    wfile = io.BytesIO()

    # Instantiate handler with mock client address and server
    client_address = ('127.0.0.1', 54321)
    
    # Custom subclass to prevent network bind
    class DirectHandler(FoodBridgeRequestHandler):
        def __init__(self):
            self.rfile = rfile
            self.wfile = wfile
            self.client_address = client_address
            self.server = MockServer()
            self.close_connection = True
            self.handle_one_request()

    handler = DirectHandler()
    wfile.seek(0)
    raw_response = wfile.read().decode("utf-8", errors="replace")

    # Parse response
    parts = raw_response.split("\r\n\r\n", 1)
    status_line = parts[0].splitlines()[0]
    status_code = int(status_line.split()[1])
    response_body = parts[1] if len(parts) > 1 else ""

    try:
        parsed_json = json.loads(response_body)
    except Exception:
        parsed_json = response_body

    return status_code, parsed_json

def run_tests():
    print("Executing In-Memory API Endpoint Contract Tests...\n")

    # 1. Health Probe
    status, data = invoke_handler("GET", "/healthz")
    assert status == 200, f"Expected 200, got {status}: {data}"
    assert data["status"] == "healthy"
    print("[PASS] GET /healthz returned 200 OK.")

    # 2. Positive Donation Manifest Ingestion
    valid_donation = {
        "donorFacilityId": "f1eebc99-9c0b-4ef8-bb6d-6bb9bd380b11",
        "availableFrom": "2026-11-06T15:00:00Z",
        "availableUntil": "2026-11-06T18:00:00Z",
        "certifierFullName": "Chef Marcus Rivera",
        "certifierFoodHandlerCert": "SERVSAFE-928104",
        "items": [
            {
                "category": "prepared_hot",
                "itemDescription": "Roast chicken and root vegetables",
                "estimatedWeightLbs": 85.5,
                "containerCount": 4,
                "packagingType": "Full-size aluminum hotel pans",
                "holdingTempFahrenheit": 142.5
            }
        ]
    }
    status, data = invoke_handler("POST", "/v1/donations", body=json.dumps(valid_donation).encode("utf-8"))
    assert status == 201, f"Expected 201, got {status}: {data}"
    assert "manifestReference" in data
    assert data["manifestReference"].startswith("FB-DSP-")
    assert data["totalGrossWeightLbs"] == 85.5
    donation_id = data["id"]
    print("[PASS] POST /v1/donations accepted valid manifest and returned reference.")

    # 3. Retrieve Donation
    status, data = invoke_handler("GET", f"/v1/donations/{donation_id}")
    assert status == 200
    assert data["id"] == donation_id
    print("[PASS] GET /v1/donations/{id} retrieved created manifest.")

    # 4. Food Safety Gatekeeper: Reject Hot Food < 135 deg F (FDA Food Code 3-501.16)
    invalid_temp_donation = {
        "donorFacilityId": "f1eebc99-9c0b-4ef8-bb6d-6bb9bd380b11",
        "availableFrom": "2026-11-06T15:00:00Z",
        "availableUntil": "2026-11-06T18:00:00Z",
        "certifierFullName": "Chef Marcus Rivera",
        "items": [
            {
                "category": "prepared_hot",
                "itemDescription": "Lukewarm pasta tray",
                "estimatedWeightLbs": 40.0,
                "containerCount": 2,
                "packagingType": "Hotel pan",
                "holdingTempFahrenheit": 118.0 # Dangerous: Below 135 F threshold
            }
        ]
    }
    status, data = invoke_handler("POST", "/v1/donations", body=json.dumps(invalid_temp_donation).encode("utf-8"))
    assert status == 422, f"Expected 422, got {status}: {data}"
    assert data["code"] == "TEMPERATURE_SAFETY_VIOLATION"
    assert "FDA Food Code" in data["detail"]
    print("[PASS] POST /v1/donations strictly rejected sub-temperature hot food (118 deg F < 135 deg F).")

    # 5. File Upload: Authentic JPEG Magic Bytes
    valid_jpeg_payload = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 1024
    status, data = invoke_handler(
        "POST", "/v1/uploads/manifest-photo",
        body=valid_jpeg_payload,
        headers={"Content-Type": "image/jpeg"}
    )
    assert status == 201, f"Expected 201, got {status}: {data}"
    assert data["verifiedMimeType"] == "image/jpeg"
    assert data["storageReference"].endswith(".jpg")
    print("[PASS] POST /v1/uploads/manifest-photo verified authentic JPEG magic bytes and stored safely.")

    # 6. File Upload: Spoofed Extension Rejection
    fake_payload = b"<?php system('whoami'); ?>" + b"\x00" * 32
    status, data = invoke_handler(
        "POST", "/v1/uploads/manifest-photo",
        body=fake_payload,
        headers={"Content-Type": "image/jpeg"}
    )
    assert status == 415, f"Expected 415, got {status}: {data}"
    assert data["code"] == "UNSUPPORTED_MEDIA_TYPE"
    print("[PASS] POST /v1/uploads/manifest-photo strictly rejected spoofed file content.")

    # 7. Agency Registration with Valid EIN
    valid_agency = {
        "legalName": "City Relief Emergency Food Kitchen",
        "einTaxIdentifier": "12-3456789",
        "streetAddress": "410 West 42nd St, New York, NY",
        "healthPermitNumber": "DOH-2024-NYC-8192",
        "dailyMealCapacity": 250,
        "refrigerationType": "commercial_walk_in",
        "directorEmail": "director@cityrelief.org"
    }
    status, data = invoke_handler("POST", "/v1/agencies/register", body=json.dumps(valid_agency).encode("utf-8"))
    assert status == 202, f"Expected 202, got {status}: {data}"
    assert data["status"] == "pending_compliance_review"
    print("[PASS] POST /v1/agencies/register accepted valid 501(c)(3) registration.")

    # 8. Agency Registration with Invalid EIN (Schema Rejection)
    invalid_agency = valid_agency.copy()
    invalid_agency["einTaxIdentifier"] = "12345" # Malformed EIN
    status, data = invoke_handler("POST", "/v1/agencies/register", body=json.dumps(invalid_agency).encode("utf-8"))
    assert status == 422, f"Expected 422, got {status}: {data}"
    assert data["code"] == "INVALID_EIN"
    print("[PASS] POST /v1/agencies/register strictly rejected non-conforming EIN.")

    # 9. Verify RFC 7807 Error Responses Leak Zero Stack Traces
    status, data = invoke_handler("GET", "/v1/donations/non-existent-uuid")
    assert status == 404
    assert "correlationId" in data
    assert "traceback" not in json.dumps(data).lower()
    assert "/var/" not in json.dumps(data)
    print("[PASS] RFC 7807 problem details contain zero internal stack traces or paths.")

    # 10. Public Key Discovery Endpoint
    status, data = invoke_handler("GET", "/v1/auth/keys")
    assert status == 200, f"Expected 200, got {status}: {data}"
    assert data["algorithm"] == "RS256"
    assert "BEGIN PUBLIC KEY" in data["publicKeyPem"]
    print("[PASS] GET /v1/auth/keys distributed valid RS256 public key.")

    # 11. Authentication Login with Valid Credentials
    login_payload = {
        "email": "chef@grandazure.com",
        "password": "DonorPass2026!"
    }
    status, data = invoke_handler("POST", "/v1/auth/login", body=json.dumps(login_payload).encode("utf-8"))
    assert status == 200, f"Expected 200, got {status}: {data}"
    assert data["tokenType"] == "Bearer"
    assert "accessToken" in data
    assert data["user"]["role"] == "DONOR_STAFF"
    print("[PASS] POST /v1/auth/login issued valid RS256 JWT access token.")

    # 12. Authentication Login with Invalid Credentials
    bad_login = {
        "email": "chef@grandazure.com",
        "password": "IncorrectPassword!"
    }
    status, data = invoke_handler("POST", "/v1/auth/login", body=json.dumps(bad_login).encode("utf-8"))
    assert status == 401, f"Expected 401, got {status}: {data}"
    assert data["code"] == "INVALID_CREDENTIALS"
    print("[PASS] POST /v1/auth/login rejected unauthorized credentials.")

    print("\nALL IN-MEMORY API ENDPOINT TESTS PASSED SUCCESSFULLY (100% GREEN)")

if __name__ == '__main__':
    run_tests()
    sys.exit(0)
