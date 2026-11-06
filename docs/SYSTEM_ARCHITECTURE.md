# FoodBridge - Enterprise System Architecture & Production Specification

This document details the complete production architecture, backend engineering, security controls, data pipelines, and infrastructure specifications for the FoodBridge Commercial Surplus Redistribution Platform.

---

## 1. System Design & Architectural Overview

FoodBridge is engineered as an event-driven, service-oriented logistics platform. It separates high-throughput dispatch ingestion from asynchronous spatial matching, cold-chain telemetry verification, and regulatory compliance reporting.

```
+-----------------------------------------------------------------------------------+
|                                 Edge Layer (CDN / WAF)                            |
|                     Cloudflare / Fastly (DDoS, SSL Termination, Caching)          |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------+-----------------------------------------+
|                               API Gateway / Reverse Proxy                         |
|             Nginx Ingress (Rate Limiting, TLS 1.3, Request Correlation IDs)       |
+-----------------------------------------+-----------------------------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                                                   |
        v                                                                   v
+-------------------------------+                         +---------------------------------+
|      Core Web Frontend        |                         |         Logistics API           |
| (Static HTML5/Tailwind/Inter) |                         |      (FastAPI / Go Gin / Node)   |
+-------------------------------+                         +----------------+----------------+
                                                                           |
                         +-------------------------------------------------+
                         |
                         +------------------------+------------------------+
                         |                        |                        |
                         v                        v                        v
             +-----------------------+ +--------------------+ +--------------------+
             | Spatial Match Engine  | | Telemetry & Safety | | Tax & Compliance   |
             |   (PostGIS Nearest)   | | (Temp Verification)| | (IRC 170e3 Hash)   |
             +-----------+-----------+ +----------+---------+ +----------+---------+
                         |                        |                      |
                         +------------------------+----------------------+
                                                  |
                                                  v
                      +---------------------------+---------------------------+
                      |               Asynchronous Message Broker             |
                      |            Redis Streams / RabbitMQ / SQS             |
                      +---------------------------+---------------------------+
                                                  |
                         +------------------------+------------------------+
                         |                                                 |
                         v                                                 v
             +-----------------------+                         +-----------------------+
             |   Worker Service 1    |                         |   Worker Service 2    |
             | (SMS/Push Dispatch)   |                         | (PDF & Hash Receipts) |
             +-----------------------+                         +-----------------------+
                                                  |
                                                  v
             +------------------------------------+------------------------------------+
             |                               Persistence                               |
             |  PostgreSQL 16 + PostGIS (Spatial Primary) | PgBouncer Connection Pool  |
             |  Redis 7 Cluster (L2 Cache, Rate Limits)  | S3 Object Storage (Manifests)|
             +-------------------------------------------------------------------------+
```

---

## 2. Backend Logic & Dispatch Lifecycle

The core dispatch lifecycle is governed by a deterministic state machine:

```
[ Manifested ] ---> [ Matched ] ---> [ Driver Assigned ] ---> [ At Pickup ]
                                                                    |
[ Rejected: Safety Failure ] <--- [ Safety Checked ] <--------------+
                                         |
                                         v
                                  [ In Transit ] ---> [ Delivered & Signed ] ---> [ Tax Receipt Generated ]
```

1. **Manifest Intake:** The donor registers item types, weights, container formats, and holding temperatures.
2. **Spatial Capacity Allocation:** The engine executes a PostGIS k-Nearest Neighbors (`<->`) spatial query against verified 501(c)(3) agencies within a maximum 10-mile travel radius having active cold storage.
3. **Safety Gatekeeper:** If holding temperatures fail FDA criteria (< 135 deg F for hot foods; > 41 deg F for chilled perishables), the lot is rejected immediately from redistribution.
4. **Custody Transfer:** Digital signatures and tare-adjusted gross weight confirmations are gathered electronically at handoff.
5. **Contemporaneous Receipt Generation:** System generates an immutable SHA-256 cryptographic receipt compliant with Treasury Regulation Section 1.170A-4A.

---

## 3. APIs & Interface Specifications

The platform exposes an **OpenAPI 3.1** compliant REST interface located at `api/openapi.yaml`.

- **Protocol:** HTTPS / TLS 1.3 exclusively.
- **Payload Format:** Strict JSON (`application/json`).
- **Idempotency:** Modifying calls (`POST /v1/donations`, `POST /v1/dispatches/transfer`) require an `Idempotency-Key` header (UUIDv4) stored in Redis with a 24-hour TTL to eliminate duplicate dispatches.
- **Pagination:** Cursor-based pagination (`limit`, `starting_after`, `ending_before`) for deterministic list queries.
- **Traceability:** Every response carries an `X-Request-ID` or `X-Correlation-ID` header.

---

## 4. Databases & Persistence

The persistence layer uses **PostgreSQL 16+** with the **PostGIS 3.4+** spatial extension.

- **Primary Schema:** Complete relational schema implemented in `database/schema.sql`.
- **Spatial Indexing:** GIST index on `facilities.location` enables sub-millisecond distance computations:
  ```sql
  SELECT id, facility_name, ST_Distance(location, donor_loc) AS distance_meters
  FROM facilities
  WHERE refrigeration_type IN ('commercial_walk_in', 'commercial_reach_in')
    AND ST_DWithin(location, donor_loc, 16093.4) -- 10-mile radius
  ORDER BY location <-> donor_loc
  LIMIT 5;
  ```
- **Connection Pooling:** PgBouncer deployed in transaction-pooling mode (`max_client_conn = 5000`, `default_pool_size = 50`).
- **Data Protection:** Point-in-time recovery (PITR) with continuous Write-Ahead Log (WAL) archiving to S3; automated daily physical snapshots.

---

## 5. Multi-Tier Caching

- **Tier 1 (Application Memory):** In-process LRU cache for immutable lookup tables (food categories, health codes, metric conversion constants).
- **Tier 2 (Distributed Redis 7):**
  - **Spatial Geohash Cache:** Active regional recipient availability indexed by Geohash (precision 6, ~1.2 km).
  - **Session & Idempotency Store:** User JWT revocation blacklist and idempotency lock keys (`SET key val NX EX 86400`).
  - **Invalidation Strategy:** Cache-aside pattern with pub/sub event-driven invalidation when agency capacity shifts.

---

## 6. Content Delivery Network (CDN) & Edge Layer

- **Provider:** Cloudflare Enterprise or Fastly.
- **SSL / TLS:** Full strict SSL with TLS 1.3, OCSP stapling, and 0-RTT resumption.
- **Edge Caching Rules:**
  - Static Assets (`.css`, `.js`, `.svg`, web fonts): `Cache-Control: public, max-age=31536000, immutable`.
  - HTML Documents (`index.html`, `privacy.html`, `terms.html`): `Cache-Control: no-cache, must-revalidate` to ensure instant propagation of legal and operational revisions.
  - API Routes (`/v1/*`): `Cache-Control: no-store, private`.

---

## 7. Authentication, Permissions & Access Control (RBAC)

- **Authentication Protocol:** OAuth 2.0 / OpenID Connect (OIDC) with RS256 JWT tokens.
- **Token Lifecycle:** Short-lived access tokens (15 minutes), refresh tokens (7 days, rotated on use, stored in HTTP-only Secure SameSite=Strict cookies).
- **Granular Role-Based Access Control (RBAC):**
  - `donor_administrator`: Manage facilities, review corporate tax substantiation reports, manage kitchen users.
  - `kitchen_operator`: Submit surplus manifests, log packaging temperatures.
  - `agency_director`: Update receiving meal capacities, confirm compliance permits.
  - `agency_receiving_staff`: Acknowledge inbound shipments, sign custody transfers.
  - `transport_driver`: View assigned routes, submit transit temperature logs.
  - `compliance_auditor`: Read-only access to immutable chain-of-custody manifests and temperature logs.

---

## 8. Rate Limiting & Denial-of-Service Defense

- **Edge Layer:** Cloudflare Web Application Firewall (WAF) blocking OWASP Top 10 vulnerabilities, credential stuffing, and bot traffic.
- **Gateway Layer (Nginx):**
  - Standard API Gateway: 30 requests/second per IP (`burst=20, nodelay`).
  - Authentication Endpoints: 5 requests/second per IP (`burst=5, nodelay`).
  - Connection Concurrency: Max 50 active TCP connections per source IP.
- **Application Layer:** Redis sliding-window rate limiter per authenticated API key.

---

## 9. Error Tracking & Logging

- **Structured Logging:** All services output JSON logs conforming to the Elastic Common Schema (ECS):
  ```json
  {
    "@timestamp": "2026-11-06T14:15:00.000Z",
    "log.level": "info",
    "message": "Custody transfer completed",
    "trace.id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "transaction.id": "00f067aa0ba902b7",
    "http.request.method": "POST",
    "url.path": "/v1/dispatches/FB-2849/custody-transfer",
    "donor.id": "org_98214",
    "weight_lbs": 119.8
  }
  ```
- **Error Aggregation:** Sentry / DataDog integrated at API and client boundaries with source-mapped stack traces.
- **Distributed Tracing:** OpenTelemetry instrumentation propagating W3C Trace Context across edge proxies and microservices.

---

## 10. Frontend Architecture

- **Standards:** Clean HTML5, Tailwind CSS with customized tokens, and Vanilla ECMAScript (ES2022).
- **Accessibility:** 100% WCAG 2.1 Level AA compliance, zero-dependency screen reader landmarks, keyboard focus management, ARIA roles.
- **Performance:** Sub-100ms First Contentful Paint (FCP), zero render-blocking third-party tracking scripts, zero bloat libraries.
- **Design Tokens:** Strictly non-vibe-coded: standard rectangular button geometry, zero purple/fuchsia gradients, zero emojis, zero em dashes.

---

## 11. Scaling Strategy

- **Stateless Services:** All API application pods run statelessly in Kubernetes (EKS/GKE).
- **Horizontal Pod Autoscaling (HPA):** Scales pod replicas based on CPU utilization (> 70%) and incoming request rates via KEDA metrics.
- **Database Scaling:** Read-heavy analytics (annual corporate ESG reports and tax summary queries) offloaded to read replicas via PgBouncer routing.
- **Asynchronous Task Workers:** High-latency tasks (PDF receipt rendering, email dispatch, geographic geocoding) decoupled via Redis Streams worker pools.

---

## 12. Security & Compliance Architecture

- **Encryption at Rest:** AES-256 for all PostgreSQL disk volumes, Redis append-only files, and S3 buckets.
- **Encryption in Transit:** TLS 1.3 enforced across all public endpoints and internal service meshes (mTLS via Istio / Linkerd).
- **Content Security Policy (CSP):** Strict CSP denying unsafe inline evaluation and disallowing frame embedding (`frame-ancestors 'none'`).
- **Cryptographic Receipt Integrity:** Every tax receipt incorporates a SHA-256 hash of donor EIN, recipient EIN, verified net weight, and timestamp to prevent alteration.

---

## 13. Object Storage & Document Archival

- **Storage Engine:** AWS S3 or Google Cloud Storage with Object Lock (WORM - Write Once, Read Many).
- **Buckets:**
  - `foodbridge-manifest-media`: Inspection photos, packaging labels (Lifecycle: Transition to Glacier Flexible Retrieval after 90 days).
  - `foodbridge-tax-receipts`: Cryptographically signed PDF records (Lifecycle: Retained for 7 years per IRS requirements).
- **Access Protocol:** Pre-signed URLs with 15-minute expiration windows for secure client uploads.

---

## 14. Continuous Integration & Continuous Deployment (CI/CD)

The automated pipeline is defined in `.github/workflows/ci-cd.yml`:

1. **Lint & Static Analysis:** Checks HTML/CSS/JS syntax, verifies zero em dashes, zero emojis, and zero pill buttons.
2. **Schema & API Validation:** Validates `api/openapi.yaml` and `database/schema.sql`.
3. **Automated Test Suite:** Executes `tests/test_system.py`.
4. **Container Build & Scanning:** Builds unprivileged Alpine container via `Dockerfile`, scanned via Trivy for CVEs.
5. **Zero-Downtime Deployment:** Rolling update deployment across Kubernetes clusters with automated health check verification.

---

## 15. Version Control Strategy

- **Branching Model:** Trunk-based development with short-lived feature branches (`feat/`, `fix/`, `compliance/`).
- **Commit Standards:** Conventional Commits (`feat(dispatch): add temperature threshold validator`).
- **Release Strategy:** Semantic Versioning (SemVer 2.0.0). Release tags (`v1.0.0`) trigger automated production deployments.

---

## 16. Testing Strategy & Quality Assurance

```
         /  E2E Smoke Tests (Cypress/Playwright)  \
        /-----------------------------------------\
       /    Integration & API Contract (Pytest)    \
      /---------------------------------------------\
     /       Database Schema & PostGIS Unit Tests    \
    /-------------------------------------------------\
   /       Code Compliance & Static Security Audits     \
  +-----------------------------------------------------+
```

- **Unit Tests:** Validates mathematical conversions (EPA WARM model, USDA meal equivalents).
- **Contract Tests:** Verifies API payload conformity against `api/openapi.yaml`.
- **System Suite:** Automated runner implemented in `tests/test_system.py`.

---

## 17. Monitoring, Metrics & Observability

- **Metrics Collection:** Prometheus scraping metrics at `/metrics` endpoints.
- **Four Golden Signals:**
  - **Latency:** HTTP request duration percentiles (p50 < 45ms, p95 < 120ms, p99 < 350ms).
  - **Traffic:** Requests per second categorized by route and status code.
  - **Errors:** 5xx error rate alert threshold set at > 0.05% of traffic over a 5-minute window.
  - **Saturation:** PostgreSQL connection pool saturation and Redis memory utilization.
- **Uptime Target:** 99.95% availability SLA.

---

## 18. Notification Pipeline

- **Urgent Driver Dispatch:** Low-latency SMS and WhatsApp notifications sent via Twilio REST API for urgent pickups within 45 minutes.
- **Kitchen Alerts:** Real-time WebSocket connection to active donor kitchen dashboards.
- **Formal Records:** Transactional email delivery of contemporaneous tax receipts and regulatory manifests via SendGrid with SPF, DKIM, and DMARC enforcement.

---

## 19. Cloud Hosting Infrastructure (AWS Reference)

- **Compute:** Amazon Elastic Kubernetes Service (EKS) spanning 3 Availability Zones (AZs).
- **Database:** Amazon RDS for PostgreSQL (Multi-AZ with read replica).
- **Cache:** Amazon ElastiCache for Redis (Cluster mode enabled).
- **Storage:** Amazon S3 with SSE-KMS encryption.
- **DNS & CDN:** Amazon Route 53 with Cloudflare Enterprise edge proxy.

---

## 20. Disaster Recovery & Business Continuity

- **Recovery Point Objective (RPO):** Under 5 minutes (via streaming PostgreSQL WAL logs).
- **Recovery Time Objective (RTO):** Under 30 minutes (via automated Terraform infrastructure reconstitution in secondary AWS region).
- **Failover Verification:** Semi-annual simulated regional evacuation drills.

