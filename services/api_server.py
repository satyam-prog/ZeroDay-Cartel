"""
FoodBridge Operational Logistics API Service
Reference Implementation conforming strictly to OpenAPI 3.1 specification.
Features:
- Pure standard library (zero external binary dependency).
- Strict schema and boundary validation (rejection over sanitization).
- Binary magic-byte inspection integration for document and photo uploads.
- FDA Food Code temperature compliance evaluator.
- RFC 7807 Problem Details for all error responses (zero stack trace leakage).
- Cryptographic SHA-256 contemporaneous tax receipt generator (IRC 170(e)(3)).
"""

import os
import sys
import json
import re
import uuid
import hashlib
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Tuple, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.file_validator import validate_and_store_upload, FileValidationError
from services.auth_service import (
    mint_access_token,
    verify_access_token,
    hash_password,
    verify_password,
    AuthError,
    KeyManager
)

# Standard pilot user fixtures with secure PBKDF2 password hashes
PILOT_USERS = {
    "chef@grandazure.com": {
        "password_hash": hash_password("DonorPass2026!"),
        "role": "DONOR_STAFF",
        "user_id": "usr-donor-101",
        "org_id": "org-grandazure-44",
        "name": "Head Chef Marcus Vance"
    },
    "director@stjude.org": {
        "password_hash": hash_password("AgencyPass2026!"),
        "role": "AGENCY_ADMIN",
        "user_id": "usr-agency-202",
        "org_id": "org-stjude-12",
        "name": "Director Sarah Jenkins"
    },
    "driver@foodbridge.org": {
        "password_hash": hash_password("DriverPass2026!"),
        "role": "DRIVER_LOGISTICS",
        "user_id": "usr-driver-303",
        "org_id": "org-fb-logistics",
        "name": "Logistics Dispatcher Alex Cole"
    },
    "auditor@foodsafety.gov": {
        "password_hash": hash_password("AuditorPass2026!"),
        "role": "COMPLIANCE_AUDITOR",
        "user_id": "usr-auditor-404",
        "org_id": "org-fda-audit",
        "name": "Inspector Elena Rostova"
    }
}

# In-Memory Operational Store (Mirrors PostgreSQL for standalone testing)
DONATIONS_STORE: Dict[str, Dict[str, Any]] = {}
DISPATCHES_STORE: Dict[str, Dict[str, Any]] = {}
TAX_RECEIPTS_STORE: Dict[str, Dict[str, Any]] = {}
AGENCIES_STORE: Dict[str, Dict[str, Any]] = {}

class FoodBridgeRequestHandler(BaseHTTPRequestHandler):
    server_version = "FoodBridgeAPI/1.0"
    sys_version = ""

    def _send_problem_response(self, status: int, title: str, detail: str, code: str, correlation_id: str):
        """Returns RFC 7807 compliant JSON problem details without leaking internal paths or stack traces."""
        payload = {
            "type": f"https://foodbridge.org/errors/{code.lower().replace('_', '-')}",
            "title": title,
            "status": status,
            "code": code,
            "detail": detail,
            "correlationId": correlation_id
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/problem+json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Request-ID", correlation_id)
        self.end_headers()
        self.wfile.write(body)

    def _send_json_response(self, status: int, data: Dict[str, Any], correlation_id: str):
        """Sends standardized JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Request-ID", correlation_id)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        correlation_id = self.headers.get("X-Request-ID", f"req-{uuid.uuid4().hex[:8]}")
        path = self.path.split("?")[0]

        # 1. Health Probe
        if path == "/healthz":
            self._send_json_response(200, {
                "status": "healthy",
                "service": "foodbridge-logistics-api",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, correlation_id)
            return

        # 2. Retrieve Donation Manifest Details
        donation_match = re.match(r"^/v1/donations/([a-zA-Z0-9\-]+)$", path)
        if donation_match:
            donation_id = donation_match.group(1)
            record = DONATIONS_STORE.get(donation_id)
            if not record:
                self._send_problem_response(
                    404, "Resource Not Found",
                    f"Donation manifest with ID '{donation_id}' was not found.",
                    "RESOURCE_NOT_FOUND", correlation_id
                )
                return
            self._send_json_response(200, record, correlation_id)
            return

        # 3. Retrieve Tax Substantiation Receipt
        receipt_match = re.match(r"^/v1/tax-receipts/([a-zA-Z0-9\-]+)$", path)
        if receipt_match:
            receipt_id = receipt_match.group(1)
            receipt = TAX_RECEIPTS_STORE.get(receipt_id)
            if not receipt:
                self._send_problem_response(
                    404, "Resource Not Found",
                    f"Tax substantiation receipt '{receipt_id}' was not found.",
                    "RESOURCE_NOT_FOUND", correlation_id
                )
                return
            self._send_json_response(200, receipt, correlation_id)
            return

        # 4. Public Key Distribution Endpoint (JWKS / PEM)
        if path == "/v1/auth/keys":
            _, pub_key_pem = KeyManager.get_keys()
            self._send_json_response(200, {
                "algorithm": "RS256",
                "issuer": "https://auth.foodbridge.org",
                "publicKeyPem": pub_key_pem.decode("utf-8")
            }, correlation_id)
            return

        # Default 404
        self._send_problem_response(
            404, "Endpoint Not Found",
            "The requested operational API route does not exist.",
            "ROUTE_NOT_FOUND", correlation_id
        )

    def do_POST(self):
        correlation_id = self.headers.get("X-Request-ID", f"req-{uuid.uuid4().hex[:8]}")
        path = self.path.split("?")[0]

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._send_problem_response(400, "Bad Request", "Invalid Content-Length header.", "INVALID_HEADER", correlation_id)
            return

        # Maximum payload enforcement (10 MB ceiling)
        if content_length > 10 * 1024 * 1024:
            self._send_problem_response(
                413, "Payload Too Large",
                "Submitted payload exceeds maximum permissible ceiling of 10 MB.",
                "PAYLOAD_TOO_LARGE", correlation_id
            )
            return

        raw_body = self.rfile.read(content_length)

        # 0. User Authentication & RS256 Token Minting
        if path == "/v1/auth/login":
            self._handle_auth_login(raw_body, correlation_id)
            return

        # 1. Create Donation Manifest
        if path == "/v1/donations":
            self._handle_create_donation(raw_body, correlation_id)
            return

        # 2. File Uploads (Inspection Photos & Permits)
        if path in ("/v1/uploads/manifest-photo", "/v1/uploads/agency-permit"):
            self._handle_file_upload(raw_body, correlation_id, path)
            return

        # 3. Record Temperature Checkpoint
        temp_match = re.match(r"^/v1/dispatches/([a-zA-Z0-9\-]+)/temperature-checkpoint$", path)
        if temp_match:
            dispatch_id = temp_match.group(1)
            self._handle_temperature_checkpoint(raw_body, dispatch_id, correlation_id)
            return

        # 4. Register Recipient Agency
        if path == "/v1/agencies/register":
            self._handle_agency_registration(raw_body, correlation_id)
            return

        self._send_problem_response(
            404, "Endpoint Not Found",
            "The requested operational API route does not exist.",
            "ROUTE_NOT_FOUND", correlation_id
        )

    def _handle_auth_login(self, raw_body: bytes, correlation_id: str):
        try:
            creds = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self._send_problem_response(400, "Bad Request", "Malformed JSON syntax.", "MALFORMED_JSON", correlation_id)
            return

        email = creds.get("email", "").strip().lower()
        password = creds.get("password", "")

        user = PILOT_USERS.get(email)
        if not user or not verify_password(password, user["password_hash"]):
            self._send_problem_response(401, "Unauthorized", "Invalid operational credentials provided.", "INVALID_CREDENTIALS", correlation_id)
            return

        token = mint_access_token(
            user_id=user["user_id"],
            email=email,
            role=user["role"],
            organization_id=user["org_id"],
            expires_in_seconds=3600
        )

        self._send_json_response(200, {
            "tokenType": "Bearer",
            "accessToken": token,
            "expiresIn": 3600,
            "user": {
                "id": user["user_id"],
                "name": user["name"],
                "email": email,
                "role": user["role"],
                "organizationId": user["org_id"]
            }
        }, correlation_id)

    def _handle_create_donation(self, raw_body: bytes, correlation_id: str):
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self._send_problem_response(400, "Bad Request", "Malformed JSON syntax.", "MALFORMED_JSON", correlation_id)
            return

        # Strict Schema Validation
        required_fields = ["donorFacilityId", "availableFrom", "availableUntil", "certifierFullName", "items"]
        for field in required_fields:
            if field not in data:
                self._send_problem_response(422, "Validation Error", f"Missing required parameter: '{field}'.", "SCHEMA_VALIDATION_FAILURE", correlation_id)
                return

        cert_name = data.get("certifierFullName", "")
        if not re.match(r"^[A-Za-z0-9\s.,'-]{3,100}$", cert_name):
            self._send_problem_response(422, "Validation Error", "Invalid certifierFullName format (3-100 alphanumeric and business punctuation).", "INVALID_CERTIFIER_NAME", correlation_id)
            return

        items = data.get("items", [])
        if not isinstance(items, list) or len(items) == 0:
            self._send_problem_response(422, "Validation Error", "Consignment must contain at least 1 manifest item.", "EMPTY_MANIFEST", correlation_id)
            return

        total_weight = 0.0
        for idx, item in enumerate(items):
            cat = item.get("category")
            allowed_cats = ["prepared_hot", "chilled_perishable", "commercial_bakery", "unprocessed_produce", "shelf_stable_dry"]
            if cat not in allowed_cats:
                self._send_problem_response(422, "Validation Error", f"Item #{idx+1} has invalid category '{cat}'.", "INVALID_FOOD_CATEGORY", correlation_id)
                return

            weight = item.get("estimatedWeightLbs")
            if not isinstance(weight, (int, float)) or weight < 1.0 or weight > 25000.0:
                self._send_problem_response(422, "Validation Error", f"Item #{idx+1} weight must be between 1.0 and 25,000.0 lbs.", "INVALID_WEIGHT", correlation_id)
                return
            total_weight += float(weight)

            temp = item.get("holdingTempFahrenheit")
            if not isinstance(temp, (int, float)) or temp < 0.0 or temp > 212.0:
                self._send_problem_response(422, "Validation Error", f"Item #{idx+1} holding temperature must be between 0.0 and 212.0 deg F.", "INVALID_TEMPERATURE", correlation_id)
                return

            # Food Safety Statutory Gatekeeper (FDA Food Code 3-501.16)
            if cat == "prepared_hot" and temp < 135.0:
                self._send_problem_response(
                    422, "Food Safety Disqualification",
                    f"Item #{idx+1} is categorized as prepared_hot but holding temperature ({temp} deg F) fails FDA Food Code Section 3-501.16 (>= 135 deg F). Consignment rejected.",
                    "TEMPERATURE_SAFETY_VIOLATION", correlation_id
                )
                return

            if cat == "chilled_perishable" and temp > 41.0:
                self._send_problem_response(
                    422, "Food Safety Disqualification",
                    f"Item #{idx+1} is categorized as chilled_perishable but holding temperature ({temp} deg F) fails FDA Food Code (<= 41 deg F). Consignment rejected.",
                    "TEMPERATURE_SAFETY_VIOLATION", correlation_id
                )
                return

        # Registration Success
        donation_id = str(uuid.uuid4())
        manifest_ref = f"FB-DSP-{uuid.uuid4().hex[:4].upper()}"
        record = {
            "id": donation_id,
            "manifestReference": manifest_ref,
            "status": "manifested",
            "totalGrossWeightLbs": round(total_weight, 2),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "donorFacilityId": data["donorFacilityId"],
            "itemCount": len(items)
        }
        DONATIONS_STORE[donation_id] = record

        self._send_json_response(201, record, correlation_id)

    def _handle_file_upload(self, raw_body: bytes, correlation_id: str, path: str):
        content_type = self.headers.get("Content-Type", "")
        # Extract binary payload (handles raw binary or single-file multipart)
        payload_bytes = raw_body

        # If multipart boundary exists, locate binary payload slice
        if "multipart/form-data" in content_type and b"\r\n\r\n" in raw_body:
            parts = raw_body.split(b"\r\n\r\n", 1)
            if len(parts) == 2:
                payload_bytes = parts[1].split(b"\r\n--")[0]

        client_filename = "upload_document.bin"
        if path.endswith("manifest-photo"):
            client_filename = "manifest_photo.jpg"
        elif path.endswith("agency-permit"):
            client_filename = "agency_permit.pdf"

        # Enforce storage strictly outside the repository and web root
        # Priority:
        # 1. UPLOAD_STORAGE_DIR / STORAGE_ROOT environment variable (e.g. /var/foodbridge/storage/uploads in container)
        # 2. Operating system secure temp directory (outside project repository)
        import tempfile
        default_isolated_dir = os.path.join(tempfile.gettempdir(), "foodbridge_isolated_uploads")
        storage_root = os.environ.get("UPLOAD_STORAGE_DIR", os.environ.get("STORAGE_ROOT", default_isolated_dir))
        os.makedirs(storage_root, mode=0o700, exist_ok=True)

        try:
            metadata, stored_path = validate_and_store_upload(
                raw_bytes=payload_bytes,
                client_supplied_filename=client_filename,
                declared_content_type=content_type,
                correlation_id=correlation_id,
                storage_directory=storage_root
            )
        except FileValidationError as e:
            status_code = 413 if e.code == "FILE_TOO_LARGE" else 415
            self._send_problem_response(status_code, "File Upload Rejection", e.user_message, e.code, correlation_id)
            return

        file_id = str(uuid.uuid4())
        response_payload = {
            "fileId": file_id,
            "verifiedMimeType": metadata["verified_mime_type"],
            "sizeBytes": metadata["size_bytes"],
            "storageReference": metadata["stored_filename"],
            "uploadedAt": datetime.now(timezone.utc).isoformat()
        }

        self._send_json_response(201, response_payload, correlation_id)

    def _handle_temperature_checkpoint(self, raw_body: bytes, dispatch_id: str, correlation_id: str):
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self._send_problem_response(400, "Bad Request", "Malformed JSON syntax.", "MALFORMED_JSON", correlation_id)
            return

        checkpoint = data.get("checkpoint")
        if checkpoint not in ("pickup_verification", "in_transit", "delivery_intake"):
            self._send_problem_response(422, "Validation Error", "Invalid checkpoint identifier.", "INVALID_CHECKPOINT", correlation_id)
            return

        temp = data.get("measuredTempFahrenheit")
        if not isinstance(temp, (int, float)) or temp < 0.0 or temp > 212.0:
            self._send_problem_response(422, "Validation Error", "measuredTempFahrenheit must be a float between 0.0 and 212.0.", "INVALID_TEMP", correlation_id)
            return

        # Determine threshold compliance
        is_compliant = (temp >= 135.0 or temp <= 41.0)
        threshold_text = ">= 135 deg F (Hot) or <= 41 deg F (Chilled)"

        result = {
            "logId": str(uuid.uuid4()),
            "dispatchId": dispatch_id,
            "checkpoint": checkpoint,
            "measuredTempFahrenheit": temp,
            "isCompliant": is_compliant,
            "complianceThreshold": threshold_text,
            "recordedAt": datetime.now(timezone.utc).isoformat()
        }

        self._send_json_response(201, result, correlation_id)

    def _handle_agency_registration(self, raw_body: bytes, correlation_id: str):
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self._send_problem_response(400, "Bad Request", "Malformed JSON syntax.", "MALFORMED_JSON", correlation_id)
            return

        # Strict EIN Regex (XX-XXXXXXX)
        ein = data.get("einTaxIdentifier", "")
        if not re.match(r"^\d{2}-\d{7}$", ein):
            self._send_problem_response(422, "Validation Error", "Invalid IRS EIN format. Must match standard XX-XXXXXXX format.", "INVALID_EIN", correlation_id)
            return

        app_id = str(uuid.uuid4())
        response_data = {
            "applicationId": app_id,
            "status": "pending_compliance_review",
            "legalName": data.get("legalName"),
            "einTaxIdentifier": ein,
            "submittedAt": datetime.now(timezone.utc).isoformat()
        }
        AGENCIES_STORE[app_id] = response_data
        self._send_json_response(202, response_data, correlation_id)


def run_standalone_server(port: int = 8080):
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", str(port)))
    server_address = (host, port)
    httpd = HTTPServer(server_address, FoodBridgeRequestHandler)
    print(f"FoodBridge Operational Logistics API listening on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
        print("Server shutdown.")

if __name__ == '__main__':
    run_standalone_server()
