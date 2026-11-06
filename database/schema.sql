-- ============================================================================
-- FoodBridge - Production Relational & Spatial Database Schema
-- Database Engine: PostgreSQL 16+ with PostGIS 3.4+
-- Compliance: 42 U.S.C. 1791 (Good Samaritan Act) & IRC 170(e)(3)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- ----------------------------------------------------------------------------
-- Enumerated Types
-- ----------------------------------------------------------------------------
CREATE TYPE organization_type AS ENUM (
    'commercial_donor',
    'recipient_agency',
    'logistics_partner',
    'regulatory_auditor'
);

CREATE TYPE food_category AS ENUM (
    'prepared_hot',
    'chilled_perishable',
    'commercial_bakery',
    'unprocessed_produce',
    'shelf_stable_dry'
);

CREATE TYPE dispatch_status AS ENUM (
    'manifested',
    'matched',
    'driver_assigned',
    'at_pickup',
    'in_transit',
    'delivered',
    'rejected_safety_failure',
    'cancelled'
);

CREATE TYPE user_role AS ENUM (
    'platform_admin',
    'donor_administrator',
    'kitchen_operator',
    'agency_director',
    'agency_receiving_staff',
    'transport_driver',
    'compliance_auditor'
);

CREATE TYPE refrigeration_capacity AS ENUM (
    'commercial_walk_in',
    'commercial_reach_in',
    'standard_residential',
    'ambient_dry_only'
);

-- ----------------------------------------------------------------------------
-- Core Entities: Organizations & Facilities
-- ----------------------------------------------------------------------------
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    legal_name VARCHAR(255) NOT NULL,
    trade_name VARCHAR(255),
    org_type organization_type NOT NULL,
    tax_identifier VARCHAR(64) NOT NULL, -- EIN / Business Registration
    is_501c3_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE facilities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    facility_name VARCHAR(255) NOT NULL,
    health_permit_number VARCHAR(128) NOT NULL,
    health_permit_expiry DATE NOT NULL,
    street_address TEXT NOT NULL,
    city VARCHAR(128) NOT NULL,
    state_province VARCHAR(64) NOT NULL,
    postal_code VARCHAR(32) NOT NULL,
    country_code CHAR(2) DEFAULT 'US',
    location GEOGRAPHY(Point, 4326) NOT NULL,
    loading_dock_instructions TEXT,
    refrigeration_type refrigeration_capacity NOT NULL DEFAULT 'ambient_dry_only',
    daily_meal_capacity INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Spatial index for sub-millisecond proximity matching
CREATE INDEX idx_facilities_location ON facilities USING GIST (location);
CREATE INDEX idx_facilities_org_id ON facilities(organization_id);

-- ----------------------------------------------------------------------------
-- Identity & Access Management (RBAC)
-- ----------------------------------------------------------------------------
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone_e164 VARCHAR(32) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    mfa_secret VARCHAR(128),
    is_mfa_enabled BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMPTZ,
    is_suspended BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_org_id ON users(organization_id);
CREATE INDEX idx_users_email ON users(email);

-- ----------------------------------------------------------------------------
-- Donations & Manifest Line Items
-- ----------------------------------------------------------------------------
CREATE TABLE donations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    donor_facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    created_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    manifest_reference VARCHAR(64) UNIQUE NOT NULL,
    available_from TIMESTAMPTZ NOT NULL,
    available_until TIMESTAMPTZ NOT NULL,
    total_gross_weight_lbs NUMERIC(10, 2) NOT NULL CHECK (total_gross_weight_lbs > 0),
    good_samaritan_certified BOOLEAN NOT NULL DEFAULT TRUE,
    certifier_full_name VARCHAR(255) NOT NULL,
    certifier_food_handler_cert VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_donations_facility ON donations(donor_facility_id);
CREATE INDEX idx_donations_created_at ON donations(created_at);

CREATE TABLE manifest_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    donation_id UUID NOT NULL REFERENCES donations(id) ON DELETE CASCADE,
    category food_category NOT NULL,
    item_description VARCHAR(255) NOT NULL,
    estimated_weight_lbs NUMERIC(8, 2) NOT NULL,
    container_count INTEGER NOT NULL CHECK (container_count > 0),
    packaging_type VARCHAR(128) NOT NULL, -- Aluminum pan, cambro, crate, carton
    prepared_at TIMESTAMPTZ,
    holding_temp_fahrenheit NUMERIC(5, 2) NOT NULL,
    contains_major_allergens BOOLEAN DEFAULT FALSE,
    allergen_details TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_manifest_items_donation ON manifest_items(donation_id);

-- ----------------------------------------------------------------------------
-- Logistics, Dispatch & Spatial Routing
-- ----------------------------------------------------------------------------
CREATE TABLE dispatches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    donation_id UUID NOT NULL REFERENCES donations(id) ON DELETE RESTRICT,
    recipient_facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    assigned_driver_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status dispatch_status NOT NULL DEFAULT 'manifested',
    matched_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    pickup_target_time TIMESTAMPTZ NOT NULL,
    delivery_target_time TIMESTAMPTZ NOT NULL,
    actual_pickup_time TIMESTAMPTZ,
    actual_delivery_time TIMESTAMPTZ,
    transit_distance_meters NUMERIC(10, 2),
    route_polyline_geojson JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dispatches_status ON dispatches(status);
CREATE INDEX idx_dispatches_donation ON dispatches(donation_id);
CREATE INDEX idx_dispatches_recipient ON dispatches(recipient_facility_id);
CREATE INDEX idx_dispatches_driver ON dispatches(assigned_driver_user_id);

-- ----------------------------------------------------------------------------
-- Telemetry & Cold-Chain Temperature Logs
-- ----------------------------------------------------------------------------
CREATE TABLE temperature_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dispatch_id UUID NOT NULL REFERENCES dispatches(id) ON DELETE CASCADE,
    checkpoint VARCHAR(64) NOT NULL, -- 'pickup_verification', 'in_transit', 'delivery_intake'
    measured_temp_fahrenheit NUMERIC(5, 2) NOT NULL,
    is_compliant BOOLEAN NOT NULL,
    measurement_device_id VARCHAR(128),
    recorded_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    location GEOGRAPHY(Point, 4326)
);

CREATE INDEX idx_temp_logs_dispatch ON temperature_logs(dispatch_id);

-- ----------------------------------------------------------------------------
-- Chain of Custody & Compliance Records
-- ----------------------------------------------------------------------------
CREATE TABLE custody_transfers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dispatch_id UUID NOT NULL REFERENCES dispatches(id) ON DELETE RESTRICT,
    transfer_stage VARCHAR(32) NOT NULL, -- 'donor_to_driver', 'driver_to_agency'
    releasing_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    receiving_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    signature_svg_data TEXT,
    verified_gross_weight_lbs NUMERIC(10, 2) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX idx_custody_transfers_dispatch ON custody_transfers(dispatch_id);

-- ----------------------------------------------------------------------------
-- Tax Substantiation Receipts (IRC Section 170(e)(3))
-- ----------------------------------------------------------------------------
CREATE TABLE tax_receipts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    donation_id UUID UNIQUE NOT NULL REFERENCES donations(id) ON DELETE RESTRICT,
    dispatch_id UUID NOT NULL REFERENCES dispatches(id) ON DELETE RESTRICT,
    donor_organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    recipient_organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    receipt_reference_number VARCHAR(128) UNIQUE NOT NULL,
    issued_date DATE NOT NULL DEFAULT CURRENT_DATE,
    total_eligible_weight_lbs NUMERIC(10, 2) NOT NULL,
    estimated_fmv_usd NUMERIC(12, 2),
    statutory_acknowledgment_text TEXT NOT NULL,
    cryptographic_sha256_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tax_receipts_donor ON tax_receipts(donor_organization_id);

-- ----------------------------------------------------------------------------
-- Immutable System Audit Trail (Security & SOC 2)
-- ----------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action_type VARCHAR(64) NOT NULL, -- 'CREATE_DONATION', 'CONFIRM_INTAKE', 'EXPORT_TAX_REPORT'
    entity_name VARCHAR(64) NOT NULL,
    entity_id UUID NOT NULL,
    client_ip INET,
    user_agent TEXT,
    payload_snapshot JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_user_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_name, entity_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

