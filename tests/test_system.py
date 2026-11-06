#!/usr/bin/env python3
"""
FoodBridge Platform Automated Test Suite
Verifies schema, API contracts, security configurations, and design compliance.
"""

import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlsplit

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_file_existence():
    required_files = [
        'index.html',
        'login.html',
        'account.html',
        'share-food.html',
        'find-food.html',
        'volunteer.html',
        'dashboard.html',
        'privacy.html',
        'terms.html',
        'favicon.svg',
        'assets/css/tailwind.css',
        'CNAME',
        '.env.example',
        '.gitignore',
        'nginx.conf',
        'Dockerfile',
        'docker-compose.yml',
        'database/schema.sql',
        'api/openapi.yaml',
        'services/file_validator.py',
        'services/auth_service.py',
        'database/repository.py',
        'database/db_pool.py',
        'database/spatial_queries.py',
        'alembic.ini',
        'database/alembic/versions/001_initial_postgis_schema.py',
        'scripts/run_migrations.py',
        'scripts/audit_security.py',
        'scripts/build_static_site.py',
        'firestore.rules',
        'firestore.indexes.json',
        'firebase.json',
        'render.yaml',
        'tests/test_file_upload_and_errors.py',
        'tests/test_auth_and_database.py',
        'assets/css/styles.css',
        'assets/js/main.js',
        'assets/js/login.js',
        'assets/js/firebase-client.js',
        'assets/js/firebase-config.js',
        'assets/js/account-nav.js',
        'assets/js/page-auth.js',
        'assets/js/account.js',
        'assets/js/share-food.js',
        'assets/js/find-food.js',
        'assets/js/volunteer.js',
        'assets/js/icons.js',
        'README.md'
    ]
    for rel_path in required_files:
        assert os.path.exists(rel_path), f"Missing required file: {rel_path}"
    print("[PASS] All required architectural files exist.")

def test_code_compliance():
    files = [
        'index.html', 'login.html', 'account.html', 'share-food.html',
        'find-food.html', 'volunteer.html', 'dashboard.html', 'privacy.html',
        'terms.html', 'assets/css/styles.css', 'assets/js/main.js', 'README.md'
    ]
    
    # 1. Zero em dashes
    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        assert '—' not in content, f"Found em dash in {fpath}"
        assert '&mdash;' not in content, f"Found &mdash; in {fpath}"
    print("[PASS] Zero em dashes across all code and documentation.")

    # 2. Zero emojis
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        matches = emoji_pattern.findall(content)
        assert not matches, f"Found emojis in {fpath}: {matches[:3]}"
    print("[PASS] Zero emojis across all code and documentation.")

    # 3. Zero purple classes or gradients
    for fpath in ['index.html', 'login.html', 'privacy.html', 'terms.html', 'assets/css/styles.css']:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read().lower()
        assert 'purple' not in content, f"Found purple reference in {fpath}"
        assert 'violet' not in content, f"Found violet reference in {fpath}"
        assert 'fuchsia' not in content, f"Found fuchsia reference in {fpath}"
    print("[PASS] Zero purple/violet gradients or classes.")

    # 4. Zero pill buttons
    for fpath in ['index.html', 'login.html', 'privacy.html', 'terms.html']:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        pill_buttons = re.findall(r'<(?:button|a)[^>]*class=["\'][^"\']*rounded-full[^"\']*["\']', content)
        assert not pill_buttons, f"Found rounded-full pill buttons in {fpath}: {pill_buttons}"
    print("[PASS] Zero pill-shaped buttons.")

    # 5. Zero AI branding or watermarks
    ai_phrases = ['made with ai', 'built with ai', 'powered by ai', 'ai generated', 'ai tool', 'ai-powered']
    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read().lower()
        for phrase in ai_phrases:
            assert phrase not in content, f"Found '{phrase}' in {fpath}"
    print("[PASS] Zero 'Made with AI' tags or marketing watermarks.")

def test_database_schema():
    with open('database/schema.sql', 'r', encoding='utf-8') as f:
        schema = f.read()
    
    required_tables = [
        'organizations',
        'facilities',
        'users',
        'donations',
        'manifest_items',
        'dispatches',
        'temperature_logs',
        'custody_transfers',
        'tax_receipts',
        'audit_logs'
    ]
    for table in required_tables:
        assert f"CREATE TABLE {table}" in schema, f"Missing table {table} in schema.sql"
    assert "GEOGRAPHY(Point, 4326)" in schema, "Missing PostGIS spatial point definition"
    assert "idx_facilities_location" in schema, "Missing spatial GIST index"
    print("[PASS] PostgreSQL + PostGIS schema verified with all 10 core tables and spatial indices.")

def test_security_and_proxy():
    with open('nginx.conf', 'r', encoding='utf-8') as f:
        conf = f.read()
    
    assert "Strict-Transport-Security" in conf, "Missing HSTS header"
    assert "Content-Security-Policy" in conf, "Missing CSP header"
    assert "X-Frame-Options" in conf, "Missing X-Frame-Options header"
    assert "limit_req_zone" in conf, "Missing rate limiting zones"
    assert "TLSv1.3" in conf, "Missing TLS 1.3 configuration"
    print("[PASS] Nginx security headers, rate limiting, and TLS configuration verified.")

def test_docker_compose_architecture():
    with open('docker-compose.yml', 'r', encoding='utf-8') as f:
        compose = f.read()

    assert "api-service-1" in compose and "api-service-2" in compose, "docker-compose.yml missing upstream API aliases"
    assert "./certs:/etc/letsencrypt:ro" in compose, "docker-compose.yml missing SSL certificate volume mount"
    assert "upload_data:/var/foodbridge/storage/uploads" in compose, "docker-compose.yml missing upload storage volume mount"
    assert "pg_isready" in compose, "docker-compose.yml missing PostgreSQL health check"
    assert "redis-cli" in compose, "docker-compose.yml missing Redis health check"
    assert "127.0.0.1:5432:5432" in compose, "PostgreSQL port must be bound strictly to 127.0.0.1"
    assert "127.0.0.1:6379:6379" in compose, "Redis port must be bound strictly to 127.0.0.1"
    print("[PASS] Docker Compose microservice architecture, aliases, and volumes verified.")

def test_js_element_binding():
    with open('assets/js/main.js', 'r', encoding='utf-8') as f:
        js_code = f.read()
    with open('index.html', 'r', encoding='utf-8') as f:
        html_code = f.read()

    active_functions = ('initNavigation', 'initFaqAccordion')
    function_bodies = []
    for function_name in active_functions:
        match = re.search(
            r'function ' + function_name + r'\(\)\s*\{.*?(?=\nfunction |\Z)',
            js_code,
            flags=re.DOTALL
        )
        assert match, f"Missing active JavaScript function: {function_name}"
        function_bodies.append(match.group(0))

    active_js = '\n'.join(function_bodies)
    js_ids = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", active_js))
    html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html_code))
    
    for element_id in js_ids:
        assert element_id in html_ids, f"JavaScript references ID '{element_id}' not found in index.html"
    print(f"[PASS] All {len(js_ids)} JavaScript element IDs match index.html elements.")

def test_render_public_bundle():
    import subprocess

    class PageInspector(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = set()
            self.references = []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if attributes.get('id'):
                self.ids.add(attributes['id'])
            for name in ('href', 'src'):
                if attributes.get(name):
                    self.references.append(attributes[name])

    subprocess.run([sys.executable, 'scripts/build_static_site.py'], check=True)
    expected_files = {
        'index.html',
        'login.html',
        'account.html',
        'share-food.html',
        'find-food.html',
        'volunteer.html',
        'privacy.html',
        'terms.html',
        'favicon.svg',
        'assets/images/foodbridge-illustration.svg',
        'assets/css/tailwind.css',
        'assets/css/styles.css',
        'assets/js/icons.js',
        'assets/js/main.js',
        'assets/js/login.js',
        'assets/js/firebase-config.js',
        'assets/js/firebase-client.js',
        'assets/js/account-nav.js',
        'assets/js/page-auth.js',
        'assets/js/account.js',
        'assets/js/share-food.js',
        'assets/js/find-food.js',
        'assets/js/volunteer.js'
    }
    actual_files = {
        os.path.relpath(os.path.join(root, filename), 'dist').replace(os.sep, '/')
        for root, _, filenames in os.walk('dist')
        for filename in filenames
    }
    assert actual_files == expected_files, f"Unexpected Render bundle contents: {actual_files}"
    for page_name in ('index.html', 'privacy.html', 'terms.html'):
        with open(os.path.join('dist', page_name), 'r', encoding='utf-8') as f:
            page = f.read().lower()
        assert '<form' not in page, f"Unexpected data collection form in {page_name}"
        assert 'dashboard.html' not in page, f"Dashboard linked from public page {page_name}"
        assert 'data-open-modal' not in page, f"Inactive submission modal in {page_name}"
        assert 'cdn.tailwindcss.com' not in page, f"External Tailwind runtime found in {page_name}"
        assert 'fonts.googleapis.com' not in page, f"External font request found in {page_name}"
        assert not re.search(r'<script(?![^>]*\bsrc=)', page), f"Inline script found in {page_name}"
        assert not re.search(r'\sstyle=', page), f"Inline style found in {page_name}"
    with open('dist/login.html', 'r', encoding='utf-8') as f:
        login_page = f.read()
    assert 'id="login-fields" disabled' in login_page, "Login fields must remain disabled until Firebase initializes."
    assert 'id="signup-fields" disabled' in login_page, "Sign-up fields must remain disabled until Firebase initializes."
    assert 'type="password"' in login_page, "Login page is missing its password field."
    assert 'type="module" src="assets/js/login.js"' in login_page, "Firebase login module is not loaded."
    assert 'verify your email' not in login_page.lower(), "Email verification UI must not appear on the login page."
    assert not re.search(r'<script(?![^>]*\bsrc=)', login_page.lower()), "Inline script found in login.html"
    with open('dist/assets/js/firebase-config.js', 'r', encoding='utf-8') as f:
        firebase_config = f.read().lower()
    for config_key in ('apikey', 'authdomain', 'projectid', 'appid'):
        assert config_key in firebase_config, f"Firebase configuration is missing {config_key}."
    assert 'private_key' not in firebase_config and 'service_account' not in firebase_config, "Admin credentials must never be shipped to the browser."
    with open('dist/assets/js/login.js', 'r', encoding='utf-8') as f:
        login_script = f.read()
    for required_auth_feature in (
        'signInWithEmailAndPassword', 'createUserWithEmailAndPassword',
        'sendPasswordResetEmail', 'browserLocalPersistence', 'finishSignIn'
    ):
        assert required_auth_feature in login_script, f"Firebase login is missing {required_auth_feature}."
    assert 'sendEmailVerification' not in login_script and 'emailVerified' not in login_script, "Email verification must not be required by the login flow."
    assert 'waitForProfileSave(profileWrite, 20000)' in login_script, "Sign-up must not wait indefinitely for the Firestore profile write."
    assert 'Saving your FoodBridge profile...' in login_script, "Sign-up must show profile-creation progress."
    referenced_login_ids = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", login_script))
    login_ids = set(re.findall(r'id=["\']([^"\']+)["\']', login_page))
    assert referenced_login_ids <= login_ids, "Firebase login script references a missing login page element."
    with open('dist/index.html', 'r', encoding='utf-8') as f:
        homepage = f.read()
    assert 'href="login.html"' in homepage, "Homepage is missing its login link."
    for section in ('id="why"', 'id="solution"', 'id="how-it-works"', 'id="features"', 'id="get-involved"', 'id="faq"'):
        assert section in homepage, f"Homepage is missing required challenge section {section}"
    assert 'id="impact"' not in homepage and 'id="stories"' not in homepage, "Removed illustrative impact/story content returned to the homepage."
    assert 'be a part of change' not in homepage.lower(), "Outdated showcase call-to-action returned to the homepage."

    workflow_scripts = {
        'account.html': ('account-nav.js', 'account.js'),
        'share-food.html': ('account-nav.js', 'share-food.js'),
        'find-food.html': ('account-nav.js', 'find-food.js'),
        'volunteer.html': ('account-nav.js', 'volunteer.js')
    }
    for page_name, script_names in workflow_scripts.items():
        with open(os.path.join('dist', page_name), 'r', encoding='utf-8') as f:
            page = f.read()
        page_ids = set(re.findall(r'id=["\']([^"\']+)["\']', page))
        for script_name in script_names:
            script_path = os.path.join('dist', 'assets', 'js', script_name)
            with open(script_path, 'r', encoding='utf-8') as f:
                script = f.read()
            referenced_ids = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", script))
            if script_name == 'account-nav.js':
                referenced_ids.discard('mobile-account-nav')
            assert referenced_ids <= page_ids, f"{script_name} references missing IDs in {page_name}: {referenced_ids - page_ids}"
            assert f'assets/js/{script_name}' in page, f"{page_name} does not load {script_name}."

    with open('firestore.rules', 'r', encoding='utf-8') as f:
        firestore_rules = f.read()
    for required_policy in (
        'approvalStatus', 'listingPrivate', 'deliveryTasks',
        'getAfter', 'allow list: if false',
        'request.resource.data.foodName == get(listingPath(request.resource.data.listingId)).data.foodName'
    ):
        assert required_policy in firestore_rules, f"Firestore policy is missing {required_policy}."
    assert 'email_verified' not in firestore_rules, "Firestore access must not require email verification."
    with open('assets/js/find-food.js', 'r', encoding='utf-8') as f:
        kitchen_script = f.read()
    assert 'foodName: item.foodName' in kitchen_script, "Kitchen requests must retain a listing name for history."
    assert 'if (request.status === "accepted")' in kitchen_script, "Kitchen history must only read listings after acceptance."
    with open('firestore.indexes.json', 'r', encoding='utf-8') as f:
        firestore_indexes = f.read()
    assert '"collectionGroup": "listings"' in firestore_indexes
    assert '"fieldPath": "expiresAt"' in firestore_indexes

    public_pages = (
        'index.html', 'login.html', 'account.html', 'share-food.html',
        'find-food.html', 'volunteer.html', 'privacy.html', 'terms.html'
    )
    for page_name in public_pages:
        with open(os.path.join('dist', page_name), 'r', encoding='utf-8') as f:
            inspector = PageInspector()
            inspector.feed(f.read())
        for reference in inspector.references:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc:
                continue
            target_page = parsed.path or page_name
            assert os.path.isfile(os.path.join('dist', target_page)), f"Broken local link in {page_name}: {reference}"
            if parsed.fragment:
                with open(os.path.join('dist', target_page), 'r', encoding='utf-8') as f:
                    target_inspector = PageInspector()
                    target_inspector.feed(f.read())
                assert parsed.fragment in target_inspector.ids, f"Broken fragment link in {page_name}: {reference}"
    print("[PASS] Render bundle includes the Firebase-backed workspaces and excludes private backend data.")

if __name__ == '__main__':
    print("Running FoodBridge Platform Verification Tests...\n")
    test_file_existence()
    test_code_compliance()
    test_database_schema()
    test_security_and_proxy()
    test_docker_compose_architecture()
    test_js_element_binding()
    test_render_public_bundle()
    
    # Run Upload & Error Information Leakage Defense Tests
    from tests.test_file_upload_and_errors import (
        test_magic_byte_detection,
        test_rejection_of_extension_spoofing,
        test_rejection_of_dangerous_extensions,
        test_file_size_enforcement,
        test_filename_neutralization_and_permissions,
        test_error_handling_and_information_leakage
    )
    test_magic_byte_detection()
    test_rejection_of_extension_spoofing()
    test_rejection_of_dangerous_extensions()
    test_file_size_enforcement()
    test_filename_neutralization_and_permissions()
    test_error_handling_and_information_leakage()
    
    # Run Cryptographic Auth, RBAC & Database Repository Tests
    from tests.test_auth_and_database import (
        TestAuthenticationAndRBAC,
        TestDatabaseRepositoryAndSpatial
    )
    import unittest
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestAuthenticationAndRBAC))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestDatabaseRepositoryAndSpatial))
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    assert result.wasSuccessful(), f"Auth and Database tests failed: {result.errors + result.failures}"
    print("[PASS] Cryptographic RS256 authentication, RBAC matrix, and spatial repository verified.")
    
    print("\nALL SYSTEM & SECURITY TESTS PASSED (100% GREEN)")
    sys.exit(0)
