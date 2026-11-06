"""
FoodBridge Cryptographic Authentication & RBAC Service
Production identity, token verification, and permission enforcement engine.

Standards:
- Asymmetric RS256 JWT tokens (RFC 7519) with strict issuer and audience claims.
- OWASP-compliant password hashing via PBKDF2-HMAC-SHA256 (600,000 iterations).
- Granular Role-Based Access Control (RBAC) matrix for multi-stakeholder logistics.
- Zero hardcoded keys: dynamically generated dev keys with environment overrides.
"""

import os
import sys
import time
import uuid
import secrets
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# RBAC Role Definitions conforming to database/schema.sql
ROLES = {
    'DONOR_ADMIN': 'Full administration of donor facilities, personnel, and consignments',
    'DONOR_STAFF': 'Manifest creation, kitchen holding temperature logs, and photo uploads',
    'AGENCY_ADMIN': 'Recipient agency management, capacity declaration, and compliance reviews',
    'AGENCY_STAFF': 'Delivery acceptance, intake temperature inspection, and custody signatures',
    'DRIVER_LOGISTICS': 'Transit custody, vehicle refrigerated holding logs, and route handover',
    'COMPLIANCE_AUDITOR': 'Read-only access to immutable chain-of-custody, telemetry, and tax receipts',
    'SYSTEM_ADMIN': 'Global operations, rate limit management, and organization verification'
}

# Granular Operational Permissions
PERMISSIONS = {
    'MANIFEST_CREATE': {'DONOR_ADMIN', 'DONOR_STAFF', 'SYSTEM_ADMIN'},
    'PHOTO_UPLOAD': {'DONOR_ADMIN', 'DONOR_STAFF', 'DRIVER_LOGISTICS', 'SYSTEM_ADMIN'},
    'TEMP_LOG': {'DONOR_STAFF', 'DRIVER_LOGISTICS', 'AGENCY_STAFF', 'SYSTEM_ADMIN'},
    'CUSTODY_TRANSFER': {'DRIVER_LOGISTICS', 'AGENCY_ADMIN', 'AGENCY_STAFF', 'SYSTEM_ADMIN'},
    'TAX_RECEIPT_VIEW': {'DONOR_ADMIN', 'COMPLIANCE_AUDITOR', 'SYSTEM_ADMIN'},
    'AUDIT_TELEMETRY_VIEW': {'COMPLIANCE_AUDITOR', 'AGENCY_ADMIN', 'SYSTEM_ADMIN'}
}

ISSUER = "https://auth.foodbridge.org"
AUDIENCE = "https://api.foodbridge.org"

class KeyManager:
    """Manages RSA 2048-bit asymmetric keypairs for signing and verifying tokens."""
    _private_key_pem: Optional[bytes] = None
    _public_key_pem: Optional[bytes] = None

    @classmethod
    def get_keys(cls) -> Tuple[bytes, bytes]:
        if cls._private_key_pem and cls._public_key_pem:
            return cls._private_key_pem, cls._public_key_pem

        # 1. Attempt loading from environment or filesystem
        priv_path = os.environ.get('JWT_PRIVATE_KEY_PATH', 'certs/jwt_private.pem')
        pub_path = os.environ.get('JWT_PUBLIC_KEY_PATH', 'certs/jwt_public.pem')

        if os.path.exists(priv_path) and os.path.exists(pub_path):
            with open(priv_path, 'rb') as f:
                cls._private_key_pem = f.read()
            with open(pub_path, 'rb') as f:
                cls._public_key_pem = f.read()
            return cls._private_key_pem, cls._public_key_pem

        # 2. Generate secure ephemeral RSA 2048-bit keypair for development/test
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        cls._private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        cls._public_key_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return cls._private_key_pem, cls._public_key_pem


class AuthError(Exception):
    """Base exception for authentication and authorization failures."""
    def __init__(self, code: str, title: str, detail: str, status_code: int = 401):
        super().__init__(detail)
        self.code = code
        self.title = title
        self.detail = detail
        self.status_code = status_code


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """Hashes password using PBKDF2-HMAC-SHA256 with 600,000 iterations (OWASP standard)."""
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters in length.")
    if salt is None:
        salt = secrets.token_bytes(16)
    iterations = 600000
    derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f"$pbkdf2-sha256${iterations}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifies a plaintext password against a stored PBKDF2 hash using constant-time comparison."""
    try:
        parts = stored_hash.split('$')
        if len(parts) != 5 or parts[1] != 'pbkdf2-sha256':
            return False
        iterations = int(parts[2])
        salt = bytes.fromhex(parts[3])
        expected_derived = bytes.fromhex(parts[4])
        computed_derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
        return secrets.compare_digest(expected_derived, computed_derived)
    except Exception:
        return False


def mint_access_token(
    user_id: str,
    email: str,
    role: str,
    organization_id: str,
    expires_in_seconds: int = 3600
) -> str:
    """Mints an asymmetric RS256 JSON Web Token with strict logistics identity claims."""
    if role not in ROLES:
        raise ValueError(f"Unknown RBAC role: {role}")

    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "sub": user_id,
        "aud": AUDIENCE,
        "email": email,
        "role": role,
        "org_id": organization_id,
        "iat": now,
        "nbf": now,
        "exp": now + expires_in_seconds,
        "jti": str(uuid.uuid4())
    }

    private_key_pem, _ = KeyManager.get_keys()
    token = jwt.encode(payload, private_key_pem, algorithm="RS256")
    return token


def verify_access_token(token_string: str) -> Dict[str, Any]:
    """
    Verifies an RS256 token against the public key, checking signature, expiration,
    issuer, and audience.
    """
    if not token_string:
        raise AuthError("TOKEN_MISSING", "Unauthorized", "Authentication token is required.", 401)

    _, public_key_pem = KeyManager.get_keys()

    try:
        claims = jwt.decode(
            token_string,
            public_key_pem,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
                "require": ["exp", "iss", "aud", "sub", "role", "org_id"]
            }
        )
        return claims
    except jwt.ExpiredSignatureError:
        raise AuthError("TOKEN_EXPIRED", "Token Expired", "The supplied authentication token has expired.", 401)
    except jwt.InvalidIssuerError:
        raise AuthError("INVALID_ISSUER", "Invalid Token", "Token issuer does not match authorized authority.", 401)
    except jwt.InvalidAudienceError:
        raise AuthError("INVALID_AUDIENCE", "Invalid Token", "Token audience does not match this service.", 401)
    except jwt.PyJWTError as e:
        raise AuthError("TOKEN_INVALID", "Invalid Token", f"Token signature or format validation failed: {str(e)}", 401)


def enforce_permission(claims: Dict[str, Any], required_permission: str) -> None:
    """Verifies that the authenticated user possesses the role required for an operation."""
    user_role = claims.get('role', '')
    allowed_roles = PERMISSIONS.get(required_permission, set())

    if user_role not in allowed_roles:
        raise AuthError(
            "FORBIDDEN",
            "Forbidden",
            f"User role '{user_role}' lacks required permission '{required_permission}'.",
            403
        )

