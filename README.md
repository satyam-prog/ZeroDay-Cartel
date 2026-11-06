# FoodBridge

FoodBridge is a Gurugram food-sharing pilot with public account registration, role-approved donor/kitchen/volunteer workspaces, Firebase Authentication, and Cloud Firestore. It is not yet a verified or fully operated logistics service. Do not announce a public launch until the Firebase setup, authorization rules, workflows, operational contacts, food-safety procedures, and local legal/privacy review have been completed.

## Set up Firebase

1. In the [Firebase Console](https://console.firebase.google.com/), create a project and register a **Web app**. Choose the Firestore location carefully (for example, `asia-south1`); the database location cannot be changed later.
2. Under **Authentication > Sign-in method**, enable **Email/Password**. This pilot does not require users to verify their email addresses; administrator role approval remains required before using role-specific tools.
3. Create a **Cloud Firestore** database in production mode.
4. Publish the security policy in `firestore.rules` using **Firestore Database > Rules**. Do not launch before these rules are published. To use the Firebase CLI instead, `firebase.json` maps the rules and indexes; run `firebase deploy --only firestore:rules,firestore:indexes` from the project root after selecting your Firebase project.
5. Add the composite index defined in `firestore.indexes.json`. The Firebase Console will also show a link to create it if the first kitchen listing query needs it.
6. Copy the Web app's `apiKey`, `authDomain`, `projectId`, and `appId` into `assets/js/firebase-config.js`. These browser configuration values are public; never put an Admin SDK key or service-account credentials in this file.
7. Under **Authentication > Settings > Authorized domains**, add the Render `onrender.com` hostname and any custom domain. Add `localhost` only for local testing.
8. Configure password policy and email templates in Firebase. Restrict the Firebase web API key to the site's HTTP referrers and required APIs where supported.

New users register from `login.html` and receive a pending role without an email verification step. An administrator must review and approve each role in Firestore by changing the user's `profiles/{uid}` fields `role` and `approvalStatus` to the approved role (`donor`, `kitchen`, or `volunteer`) and `approved`. Do not change `requestedRole` or allow users to approve themselves. There is no admin dashboard in this pilot.

## Deploy to Render

The included [render.yaml](./render.yaml) defines a Render Static Site. `scripts/build_static_site.py` copies only the allowlisted public pages and assets into `dist/`; it does not publish the separate API, database, test fixtures, or certificates.

1. Push the project to a Git provider connected to Render. If the repository root is the `OS code` folder, keep `rootDir: .`; otherwise set `rootDir` in `render.yaml` to the project subdirectory.
2. In Render, choose **New > Blueprint**, connect the repository, and select `render.yaml`. Review and create `foodbridge-public`. The build command is `python3 scripts/build_static_site.py` and the publish directory is `dist`.
3. In the static site's **Headers** settings, add `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy: geolocation=(), microphone=(), camera=()`. Set this Content Security Policy:

   ```text
   default-src 'self'; script-src 'self' https://www.gstatic.com; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://www.googleapis.com https://firebaseinstallations.googleapis.com https://firestore.googleapis.com; object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors 'none'
   ```

4. After the first deploy, add the exact Render hostname to Firebase **Authorized domains**. For a custom domain, add it in Render **Settings > Custom Domains**, configure DNS as Render instructs, and authorize that domain in Firebase. The repository's `CNAME` file does not configure Render DNS.
5. Test using separate donor, kitchen, and volunteer accounts. Verify registration, pending-role denial, administrator role approval, posting a listing, requesting and accepting it, claiming/completing a delivery, password reset, refresh persistence, and sign-out. Use disposable test data and remove it afterward.

Tailwind is compiled into `assets/css/tailwind.css`. The app loads the pinned Firebase JavaScript SDK from `www.gstatic.com`; Render serves the static site over TLS, while Firebase rules protect Firestore data. Static HTML is public, so do not put sensitive data in the site files. The app does not independently verify food safety, user organizations, or successful handoffs. Arrange real-world support, incident handling, data retention/deletion, and India-specific food-safety and privacy review before inviting the public.

## Checks

```bash
python scripts/build_static_site.py
python tests/test_system.py
python tests/test_api_endpoints.py
python tests/test_file_upload_and_errors.py
```

The repository also contains a separate reference Docker/API/PostGIS stack. It is not deployed by `render.yaml` and is not required by the Firebase-backed static pilot.

---

## 2. Platform Architecture & Repository Index

```text
.
|-- index.html                              # Public informational homepage
|-- login.html                              # Firebase email/password sign-in and password reset
|-- dashboard.html                          # Operations & dispatch telemetry registry (chain of custody)
|-- privacy.html                            # Privacy notice for the informational preview
|-- terms.html                              # Informational website limitations
|-- favicon.svg                             # Institutional vector favicon
|-- CNAME                                   # Legacy custom-domain file; not used by Render
|-- nginx.conf                              # Production reverse proxy gateway, rate limiter & error boundary
|-- Dockerfile                              # Hardened unprivileged Alpine Nginx web container
|-- docker-compose.yml                      # 4-tier microservice stack (Gateway, API, PostGIS, Redis)
|-- .env.example                            # Strict environment variable configuration template
|-- .gitignore                              # Production secret, key, and database volume exclusion rules
|-- api/
|   `-- openapi.yaml                        # OpenAPI 3.1 specification for operational logistics endpoints
|-- assets/
|   |-- css/styles.css                      # Accessible design system (zero purple gradients, rectangular geometry)
|   |-- js/main.js                          # Informational calculator, safety matrix, and navigation
|   |-- js/login.js                         # Firebase Authentication client interactions
|   `-- js/firebase-config.js               # Public Firebase web-app configuration (fill before deployment)
|-- certs/
|   |-- README.md                           # TLS certificate configuration & local self-signed guide
|   `-- .gitkeep                            # Git structure retention
|-- database/
|   |-- schema.sql                          # PostgreSQL 16 + PostGIS 3.4 DDL (10 tables, spatial indices)
|   `-- seeds/seed_pilot_data.sql           # Staging/QA seed fixtures for commercial kitchens & food banks
|-- docs/
|   |-- SYSTEM_ARCHITECTURE.md              # 20-pillar enterprise architectural specification
|   `-- RUNBOOK.md                          # SRE production operations manual & food safety incident SOPs
|-- scripts/
|   `-- audit_security.py                   # Automated secret scanner & container vulnerability auditor
|-- services/
|   |-- api_server.py                       # Python reference API implementing OpenAPI 3.1 & RFC 7807 problem details
|   `-- file_validator.py                   # Binary magic-byte inspection engine & filename neutralizer
`-- tests/
    |-- test_system.py                      # Master platform compliance & architectural test runner
    |-- test_api_endpoints.py               # In-memory contract tests for all operational endpoints
    `-- test_file_upload_and_errors.py      # Binary inspection, size bounds & zero information leakage tests
```

---

## 3. Reference Container Architecture (Not the Render Static Deployment)

The repository includes a local reference stack with four components communicating across a private bridge network (`foodbridge_net`). This stack is not deployed by `render.yaml` and is not production-ready:

1. **`gateway` (Nginx 1.27 Alpine)**: Reverse proxy terminating TLS 1.3, managing leaky-bucket rate limiting zones, resolving upstream microservices, and serving static portal assets.
2. **`api` (Python 3.11 Alpine)**: High-performance operational logistics backend enforcing OpenAPI 3.1 schemas, infrared temperature verification, and binary upload inspection.
3. **`db` (PostgreSQL 16 + PostGIS 3.4 Alpine)**: Spatial relational database storing facilities, dispatches, temperature logs, and tax substantiation records with spatial GIST indices. Port bound strictly to `127.0.0.1`.
4. **`redis` (Redis 7 Alpine)**: Distributed cache and rate limiting state store, running with password protection and bound strictly to `127.0.0.1`.

### Launching the Stack

```bash
# 1. Generate configuration from template
cp .env.example .env

# 2. Start container stack in detached mode
docker compose up -d

# 3. Verify health status of all four containers
docker compose ps
```

---

## 4. Verification & Automated Test Suites

The repository contains four dedicated verification and automated test suites:

```bash
# 1. Master System & Architecture Test (Verifies files, schemas, DDL, Nginx, Compose, bindings)
python tests/test_system.py

# 2. Security & Secret Scanner (Audits codebase for hardcoded credentials & base images)
python scripts/audit_security.py

# 3. Operational API Contract Tests (In-memory testing of endpoints, schemas, temperature gates)
python tests/test_api_endpoints.py

# 4. File Upload Safety & Error Defense (Verifies binary magic bytes, size limits, zero stack traces)
python tests/test_file_upload_and_errors.py
```

---

## 5. Security & Governance Standards

- **Zero Information Leakage**: Error handlers intercept all 4xx and 5xx conditions, returning standardized RFC 7807 JSON problem details without exposing stack traces, filesystem paths, or raw database messages.
- **Strict Input Validation**: Endpoints validate payload formats, numerical bounds, IRS EIN patterns, and string lengths, rejecting invalid submissions with HTTP 422.
- **Binary Magic-Byte Inspection**: Uploaded manifests and health inspection certificates are verified at the binary byte level (JPEG `FF D8 FF`, PNG `89 50 4E 47`, PDF `%PDF-`), rejecting extension-spoofed files (e.g. PHP scripts disguised as images).
- **Execution-Blocked Storage**: Uploaded files are neutralized with random UUIDv4 filenames and stored outside the web root (`/var/foodbridge/storage/uploads/`) with `0o640` non-executable permissions.
- **Rate Limiting**: Multi-tiered leaky-bucket throttling per IP address (30 requests/sec general API, 10 requests/min consignments, 5 requests/min uploads) with HTTP 429 and `Retry-After` headers.
- **Secret Protection**: Zero hardcoded credentials; database and cache ports are bound strictly to localhost loopback interfaces.
