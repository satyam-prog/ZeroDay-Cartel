-- ============================================================================
-- FoodBridge - Realistic Operational Seed Data
-- Intended for Staging, Quality Assurance, and Spatial Query Verification
-- ============================================================================

-- 1. Organizations
INSERT INTO organizations (id, legal_name, trade_name, org_type, tax_identifier, is_501c3_verified, is_active)
VALUES
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Grand Azure Hospitality LLC', 'Grand Azure Hotel & Suites', 'commercial_donor', '13-5829104', FALSE, TRUE),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Metro Convention Services Inc', 'Metro Center Catering', 'commercial_donor', '11-4920194', FALSE, TRUE),
    ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'St Jude Community Food Foundation', 'St Jude Relief Center', 'recipient_agency', '13-9821049', TRUE, TRUE),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'Downtown Family Shelter Alliance', 'Hope Outreach Kitchen', 'recipient_agency', '14-3829105', TRUE, TRUE);

-- 2. Facilities with PostGIS Point Geography (New York Metro Region)
INSERT INTO facilities (id, organization_id, facility_name, health_permit_number, health_permit_expiry, street_address, city, state_province, postal_code, country_code, location, loading_dock_instructions, refrigeration_type, daily_meal_capacity)
VALUES
    (
        'f1eebc99-9c0b-4ef8-bb6d-6bb9bd380b11',
        'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        'Grand Azure Main Culinary Kitchen',
        'DOH-NYC-81920',
        '2027-12-31',
        '450 Lexington Ave',
        'New York',
        'NY',
        '10017',
        'US',
        ST_SetSRID(ST_MakePoint(-73.9744, 40.7527), 4326),
        'Enter through Loading Dock 2 on 45th Street. Ring culinary expediter bell.',
        'commercial_walk_in',
        0
    ),
    (
        'f2eebc99-9c0b-4ef8-bb6d-6bb9bd380b22',
        'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
        'Metro Center Banquet Commissary',
        'DOH-NYC-74821',
        '2028-06-30',
        '655 West 34th St',
        'New York',
        'NY',
        '10001',
        'US',
        ST_SetSRID(ST_MakePoint(-74.0026, 40.7578), 4326),
        'Freight elevator B to Lower Level Kitchen. Security clearance required at gate.',
        'commercial_walk_in',
        0
    ),
    (
        'f3eebc99-9c0b-4ef8-bb6d-6bb9bd380b33',
        'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33',
        'St Jude Emergency Meal Kitchen',
        'DOH-NYC-38291',
        '2027-09-30',
        '315 West 43rd St',
        'New York',
        'NY',
        '10036',
        'US',
        ST_SetSRID(ST_MakePoint(-73.9892, 40.7584), 4326),
        'Kitchen entrance on alleyway behind main chapel. Staff on duty until 22:00.',
        'commercial_walk_in',
        350
    ),
    (
        'f4eebc99-9c0b-4ef8-bb6d-6bb9bd380b44',
        'd0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44',
        'Hope Outreach Family Food Pantry',
        'DOH-NYC-92814',
        '2028-03-31',
        '120 West 14th St',
        'New York',
        'NY',
        '10011',
        'US',
        ST_SetSRID(ST_MakePoint(-73.9961, 40.7371), 4326),
        'Curbside delivery zone in front of entrance. Ring buzzer 1B.',
        'commercial_reach_in',
        180
    );

-- 3. Users (Platform Personnel & Kitchen Directors)
INSERT INTO users (id, organization_id, email, phone_e164, full_name, role, password_hash)
VALUES
    ('u1eebc99-9c0b-4ef8-bb6d-6bb9bd380c11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'chef.marcus@grandazure.com', '+15550192834', 'Marcus Rivera', 'kitchen_operator', '$2b$12$e7/0qjJqM2F9W.y5bXzUFeaB6O7N0bF8zH3V4kL1nP9qW7eR5tY1u'),
    ('u2eebc99-9c0b-4ef8-bb6d-6bb9bd380c22', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'director@stjuderelief.org', '+15550184920', 'Sister Ananya Patel', 'agency_director', '$2b$12$e7/0qjJqM2F9W.y5bXzUFeaB6O7N0bF8zH3V4kL1nP9qW7eR5tY1u'),
    ('u3eebc99-9c0b-4ef8-bb6d-6bb9bd380c33', NULL, 'driver.tariq@foodbridge.org', '+15550173829', 'Tariq Al-Mansoor', 'transport_driver', '$2b$12$e7/0qjJqM2F9W.y5bXzUFeaB6O7N0bF8zH3V4kL1nP9qW7eR5tY1u');

-- 4. Initial Pilot Donation & Items
INSERT INTO donations (id, donor_facility_id, created_by_user_id, manifest_reference, available_from, available_until, total_gross_weight_lbs, good_samaritan_certified, certifier_full_name, certifier_food_handler_cert)
VALUES
    (
        'd1eebc99-9c0b-4ef8-bb6d-6bb9bd380d11',
        'f1eebc99-9c0b-4ef8-bb6d-6bb9bd380b11',
        'u1eebc99-9c0b-4ef8-bb6d-6bb9bd380c11',
        'FB-DSP-2849',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP + INTERVAL '3 hours',
        119.80,
        TRUE,
        'Marcus Rivera',
        'SERVSAFE-928104'
    );

INSERT INTO manifest_items (id, donation_id, category, item_description, estimated_weight_lbs, container_count, packaging_type, prepared_at, holding_temp_fahrenheit, contains_major_allergens, allergen_details)
VALUES
    (
        uuid_generate_v4(),
        'd1eebc99-9c0b-4ef8-bb6d-6bb9bd380d11',
        'prepared_hot',
        'Herb-roasted chicken breast in natural jus',
        52.40,
        4,
        'Full-size 4-inch deep aluminum hotel pans with sealed foil covers',
        CURRENT_TIMESTAMP - INTERVAL '45 minutes',
        142.50,
        FALSE,
        NULL
    ),
    (
        uuid_generate_v4(),
        'd1eebc99-9c0b-4ef8-bb6d-6bb9bd380d11',
        'prepared_hot',
        'Steamed seasonal medley (carrots, green beans, roasted potatoes)',
        41.20,
        3,
        'Full-size 4-inch deep aluminum hotel pans with sealed foil covers',
        CURRENT_TIMESTAMP - INTERVAL '40 minutes',
        138.80,
        FALSE,
        NULL
    ),
    (
        uuid_generate_v4(),
        'd1eebc99-9c0b-4ef8-bb6d-6bb9bd380d11',
        'commercial_bakery',
        'Artisan sourdough dinner rolls and baguettes',
        26.20,
        2,
        'Commercial food-grade bakery delivery cartons with poly liners',
        CURRENT_TIMESTAMP - INTERVAL '2 hours',
        70.00,
        TRUE,
        'Contains wheat gluten'
    );

-- 5. Dispatch Logistics Record
INSERT INTO dispatches (id, donation_id, recipient_facility_id, assigned_driver_user_id, status, matched_at, pickup_target_time, delivery_target_time, actual_pickup_time, actual_delivery_time, transit_distance_meters)
VALUES
    (
        'dsp-eebc99-9c0b-4ef8-bb6d-6bb9bd380e11',
        'd1eebc99-9c0b-4ef8-bb6d-6bb9bd380d11',
        'f3eebc99-9c0b-4ef8-bb6d-6bb9bd380b33',
        'u3eebc99-9c0b-4ef8-bb6d-6bb9bd380c33',
        'delivered',
        CURRENT_TIMESTAMP - INTERVAL '90 minutes',
        CURRENT_TIMESTAMP - INTERVAL '60 minutes',
        CURRENT_TIMESTAMP - INTERVAL '20 minutes',
        CURRENT_TIMESTAMP - INTERVAL '55 minutes',
        CURRENT_TIMESTAMP - INTERVAL '22 minutes',
        1850.50
    );

-- 6. Verified Telemetry Checkpoints
INSERT INTO temperature_logs (id, dispatch_id, checkpoint, measured_temp_fahrenheit, is_compliant, measurement_device_id, recorded_by_user_id)
VALUES
    (
        uuid_generate_v4(),
        'dsp-eebc99-9c0b-4ef8-bb6d-6bb9bd380e11',
        'pickup_verification',
        141.20,
        TRUE,
        'COOPER-ATKINS-IR-04',
        'u3eebc99-9c0b-4ef8-bb6d-6bb9bd380c33'
    ),
    (
        uuid_generate_v4(),
        'dsp-eebc99-9c0b-4ef8-bb6d-6bb9bd380e11',
        'delivery_intake',
        138.40,
        TRUE,
        'THERMAPEN-PROBE-01',
        'u2eebc99-9c0b-4ef8-bb6d-6bb9bd380c22'
    );

-- 7. Contemporaneous Tax Substantiation Receipt (IRC Section 170(e)(3))
INSERT INTO tax_receipts (id, donation_id, dispatch_id, donor_organization_id, recipient_organization_id, receipt_reference_number, issued_date, total_eligible_weight_lbs, estimated_fmv_usd, statutory_acknowledgment_text, cryptographic_sha256_hash)
VALUES
    (
        uuid_generate_v4(),
        'd1eebc99-9c0b-4ef8-bb6d-6bb9bd380d11',
        'dsp-eebc99-9c0b-4ef8-bb6d-6bb9bd380e11',
        'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33',
        'TAX-2026-FB-8942',
        CURRENT_DATE,
        119.80,
        359.40,
        'In compliance with Internal Revenue Code Section 170(e)(3) and Treasury Regulation Section 1.170A-4A, St. Jude Community Food Foundation certifies that the inventory items described in manifest FB-DSP-2849 were received in good faith solely for the care of the ill, the needy, or infants, and will not be transferred or exchanged for money, property, or services.',
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    );

