# FoodBridge - Production Operational Runbook & SOP

This runbook documents standard operational procedures for site reliability engineers (SREs), system administrators, and compliance officers maintaining the FoodBridge platform.

---

## 1. System Startup & Container Orchestration

### Prerequisites
- Docker Engine 24.0+ and Docker Compose v2.20+
- Verified `.env` file generated from `.env.example`

### Starting the Production Stack
```bash
# Verify environment configuration
docker compose config

# Launch services in detached mode
docker compose up -d

# Verify container health checks
docker compose ps
```

### Stopping Services Gracefully
```bash
docker compose down
```

---

## 2. Database Maintenance & PostGIS Reindexing

### Checking Database Health
```bash
docker compose exec db psql -U foodbridge_app -d foodbridge -c "SELECT COUNT(*) FROM donations;"
```

### Monthly PostGIS Spatial Re-indexing
Over time, spatial GIST indices experience bloat as facility coordinates and dispatch points are added:
```sql
-- Connect via psql
REINDEX TABLE CONCURRENTLY facilities;
VACUUM ANALYZE facilities;
```

### Point-in-Time Recovery (PITR) & Backups
Daily physical backups are executed via `pg_dump`:
```bash
# Automated backup script
docker compose exec db pg_dump -U foodbridge_app -F c foodbridge > /var/backups/foodbridge_$(date +%Y%m%d).dump
```

---

## 3. SSL / TLS Certificate Lifecycle Management

Production uses Let's Encrypt with automated renewal via Certbot:
```bash
# Dry-run renewal verification
certbot renew --dry-run

# Force reload Nginx upon certificate renewal
nginx -s reload
```

---

## 4. Rate Limit Throttling Adjustments

Rate limit zones are declared in `nginx.conf`:
- To adjust general API rate limits, update line 66:
  `limit_req_zone $binary_remote_addr zone=api_general_limit:20m rate=45r/s;`
- Test Nginx syntax prior to reloading:
  `nginx -t`
- Reload configuration with zero downtime:
  `nginx -s reload`

---

## 5. Security Incident Response Protocol

### Scenario A: Potential Food Adulteration or Health Department Inquiry
1. Retrieve the manifest identifier (e.g. `FB-DSP-2849`).
2. Query the complete immutable chain-of-custody log:
   ```sql
   SELECT * FROM dispatches d
   JOIN temperature_logs t ON d.id = t.dispatch_id
   JOIN custody_transfers c ON d.id = c.dispatch_id
   WHERE d.donation_id = 'd1eebc99-9c0b-4ef8-bb6d-6bb9bd380d11';
   ```
3. Export the time-stamped infrared probe readings and signature SVGs.
4. Notify the designated food safety officer at `compliance@foodbridge.org`.

### Scenario B: Suspected API Key Compromise
1. Revoke the API key immediately in the database:
   ```sql
   UPDATE users SET is_suspended = TRUE WHERE id = '<user_uuid>';
   ```
2. Blacklist active JWT tokens in Redis:
   ```bash
   docker compose exec redis redis-cli -a "$REDIS_PASSWORD" SET "blacklist:<token_jti>" 1 EX 86400
   ```

---

## 6. Audit Log Export for IRS Tax Verification

Pursuant to Treasury Regulation Section 1.170A-4A, corporate donors may require verified contemporaneous tax receipts during an IRS audit:
```sql
SELECT
    tr.receipt_reference_number,
    tr.issued_date,
    o_donor.legal_name AS donor_entity,
    o_donor.tax_identifier AS donor_ein,
    o_recip.legal_name AS recipient_agency,
    o_recip.tax_identifier AS recipient_501c3_ein,
    tr.total_eligible_weight_lbs,
    tr.cryptographic_sha256_hash
FROM tax_receipts tr
JOIN organizations o_donor ON tr.donor_organization_id = o_donor.id
JOIN organizations o_recip ON tr.recipient_organization_id = o_recip.id
WHERE tr.receipt_reference_number = 'TAX-2026-FB-8942';
```
The resulting record matches the SHA-256 hash generated at the time of delivery signoff.

