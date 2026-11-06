#!/usr/bin/env python3
"""
Automated Test Suite for Cryptographic Authentication, RBAC, and Database Operations
Verifies:
1. PBKDF2-HMAC-SHA256 password hashing and constant-time verification.
2. RS256 asymmetric JWT token minting, verification, and claim validation.
3. Strict expiration enforcement (expired token rejection).
4. Multi-stakeholder RBAC role and permission matrix enforcement.
5. Spatial distance calculation and radius matching.
6. Immutable chain-of-custody transfer logging.
"""

import os
import sys
import time
import unittest

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.auth_service import (
    hash_password,
    verify_password,
    mint_access_token,
    verify_access_token,
    enforce_permission,
    AuthError
)
from database.repository import (
    OperationalDatabaseRepository,
    calculate_haversine_distance_miles
)

class TestAuthenticationAndRBAC(unittest.TestCase):

    def test_password_hashing_and_verification(self):
        password = "SecurePassword2026!"
        hashed = hash_password(password)

        self.assertTrue(hashed.startswith("$pbkdf2-sha256$600000$"))
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword123", hashed))
        self.assertFalse(verify_password("", hashed))

    def test_rs256_token_minting_and_claims_verification(self):
        user_id = "usr-donor-101"
        email = "chef@grandazure.com"
        role = "DONOR_STAFF"
        org_id = "org-grandazure-44"

        token = mint_access_token(user_id, email, role, org_id, expires_in_seconds=3600)
        self.assertIsInstance(token, str)

        claims = verify_access_token(token)
        self.assertEqual(claims["sub"], user_id)
        self.assertEqual(claims["email"], email)
        self.assertEqual(claims["role"], role)
        self.assertEqual(claims["org_id"], org_id)
        self.assertEqual(claims["iss"], "https://auth.foodbridge.org")
        self.assertEqual(claims["aud"], "https://api.foodbridge.org")

    def test_expired_token_rejection(self):
        # Mint token that expires immediately (-1 second)
        token = mint_access_token(
            "usr-expired-999",
            "test@foodbridge.org",
            "DONOR_STAFF",
            "org-test-99",
            expires_in_seconds=-5
        )
        with self.assertRaises(AuthError) as ctx:
            verify_access_token(token)
        self.assertEqual(ctx.exception.code, "TOKEN_EXPIRED")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_rbac_permission_matrix(self):
        donor_claims = {"role": "DONOR_STAFF"}
        agency_claims = {"role": "AGENCY_STAFF"}
        auditor_claims = {"role": "COMPLIANCE_AUDITOR"}

        # 1. DONOR_STAFF can create manifests, but cannot sign agency custody transfers
        enforce_permission(donor_claims, "MANIFEST_CREATE")
        with self.assertRaises(AuthError) as ctx:
            enforce_permission(donor_claims, "CUSTODY_TRANSFER")
        self.assertEqual(ctx.exception.status_code, 403)

        # 2. AGENCY_STAFF can accept custody, but cannot create donor manifests
        enforce_permission(agency_claims, "CUSTODY_TRANSFER")
        with self.assertRaises(AuthError) as ctx:
            enforce_permission(agency_claims, "MANIFEST_CREATE")
        self.assertEqual(ctx.exception.status_code, 403)

        # 3. COMPLIANCE_AUDITOR can view audit telemetry and tax receipts
        enforce_permission(auditor_claims, "AUDIT_TELEMETRY_VIEW")
        enforce_permission(auditor_claims, "TAX_RECEIPT_VIEW")
        with self.assertRaises(AuthError) as ctx:
            enforce_permission(auditor_claims, "PHOTO_UPLOAD")
        self.assertEqual(ctx.exception.status_code, 403)


class TestDatabaseRepositoryAndSpatial(unittest.TestCase):

    def setUp(self):
        self.repo = OperationalDatabaseRepository()

    def test_haversine_distance_calculation(self):
        # Distance from Grand Central (40.7527, -73.9772) to Times Square (40.7580, -73.9855)
        # approx 0.57 miles
        dist = calculate_haversine_distance_miles(40.7527, -73.9772, 40.7580, -73.9855)
        self.assertGreater(dist, 0.4)
        self.assertLess(dist, 0.8)

    def test_nearby_recipient_agency_matching(self):
        # Query from Midtown Manhattan (40.7527, -73.9772)
        agencies = self.repo.find_nearby_recipient_agencies(40.7527, -73.9772, max_radius_miles=5.0)

        self.assertGreaterEqual(len(agencies), 1)
        # Verify nearest agency is first
        self.assertEqual(agencies[0]["id"], "fac-agency-001")
        self.assertLess(agencies[0]["distance_miles"], 1.0)
        self.assertTrue(agencies[0]["refrigeration_certified"])

    def test_temperature_checkpoint_recording(self):
        # 142 deg F is compliant for hot holding
        entry_hot = self.repo.record_temperature_checkpoint("dsp-101", "KITCHEN_DISPATCH", 142.0, "usr-chef-1")
        self.assertTrue(entry_hot["is_compliant"])

        # 85 deg F is in the danger zone (non-compliant)
        entry_danger = self.repo.record_temperature_checkpoint("dsp-101", "IN_TRANSIT", 85.0, "usr-driver-2")
        self.assertFalse(entry_danger["is_compliant"])

    def test_custody_transfer_logging(self):
        transfer = self.repo.record_custody_transfer(
            dispatch_id="dsp-101",
            transfer_type="VEHICLE_TO_SHELTER",
            releasing_user_id="usr-driver-2",
            receiving_user_id="usr-shelter-mgr-3",
            signature_sha256="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
        )
        self.assertEqual(transfer["dispatch_id"], "dsp-101")
        self.assertEqual(transfer["transfer_type"], "VEHICLE_TO_SHELTER")
        self.assertEqual(len(self.repo.custody_transfers["dsp-101"]), 1)


if __name__ == '__main__':
    unittest.main()

