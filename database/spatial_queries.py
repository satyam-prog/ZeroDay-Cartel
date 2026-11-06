"""
FoodBridge PostGIS Spatial & Logistics Query Service
Executes spatial indexing queries, distance calculations, and transactional ledger records.

Standards:
- PostGIS ST_DWithin and ST_Distance using WGS 84 (EPSG 4326) geography.
- GIST spatial index utilization on facilities.location.
- Fully parameterized SQL statements preventing SQL injection.
"""

from typing import List, Dict, Any, Optional
from database.db_pool import db_pool

METERS_PER_MILE = 1609.344

def query_agencies_within_dispatch_radius(
    donor_longitude: float,
    donor_latitude: float,
    radius_miles: float = 15.0
) -> List[Dict[str, Any]]:
    """
    Executes PostGIS ST_DWithin spatial query to match donor facilities with qualified
    recipient agencies within a transit radius under 45 minutes.
    """
    radius_meters = radius_miles * METERS_PER_MILE

    sql = """
        SELECT 
            f.id,
            f.organization_id,
            f.name,
            f.facility_type,
            f.street_address,
            f.city,
            f.postal_code,
            f.refrigeration_capacity_sqft,
            f.daily_meal_capacity,
            ST_Y(f.location::geometry) AS latitude,
            ST_X(f.location::geometry) AS longitude,
            ROUND((ST_Distance(f.location, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) / 1609.344)::numeric, 2) AS distance_miles
        FROM facilities f
        JOIN organizations o ON f.organization_id = o.id
        WHERE o.org_type IN ('FOOD_BANK', 'EMERGENCY_SHELTER', 'SOUP_KITCHEN')
          AND o.verification_status = 'VERIFIED'
          AND f.is_active = TRUE
          AND ST_DWithin(f.location, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
        ORDER BY distance_miles ASC
        LIMIT 25;
    """

    results = []
    with db_pool.get_connection() as conn:
        with conn.cursor() as cursor:
            # Pass coordinates: longitude, latitude, longitude, latitude, radius_meters
            cursor.execute(sql, (donor_longitude, donor_latitude, donor_longitude, donor_latitude, radius_meters))
            columns = [desc[0] for desc in cursor.description]
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

    return results

def insert_dispatch_record(
    donation_id: str,
    donor_facility_id: str,
    recipient_facility_id: str,
    transporter_user_id: Optional[str] = None
) -> str:
    """Inserts a new dispatch record transitioning donation to assigned transit."""
    sql = """
        INSERT INTO dispatches (
            donation_id,
            donor_facility_id,
            recipient_facility_id,
            transporter_user_id,
            dispatch_status
        ) VALUES (%s, %s, %s, %s, 'ASSIGNED')
        RETURNING id;
    """
    with db_pool.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (donation_id, donor_facility_id, recipient_facility_id, transporter_user_id))
            row = cursor.fetchone()
            return str(row[0])

def insert_temperature_audit_entry(
    dispatch_id: str,
    checkpoint: str,
    measured_temp_f: float,
    recorded_by_user_id: str,
    probe_device_serial: str,
    photo_evidence_url: Optional[str] = None
) -> Dict[str, Any]:
    """Inserts an immutable temperature checkpoint entry with compliance verification."""
    is_compliant = (measured_temp_f >= 135.0 or measured_temp_f <= 41.0)
    sql = """
        INSERT INTO temperature_logs (
            dispatch_id,
            checkpoint,
            measured_temp_fahrenheit,
            is_compliant,
            recorded_by,
            probe_device_serial,
            photo_evidence_url
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, recorded_at;
    """
    with db_pool.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (
                dispatch_id,
                checkpoint,
                measured_temp_f,
                is_compliant,
                recorded_by_user_id,
                probe_device_serial,
                photo_evidence_url
            ))
            row = cursor.fetchone()
            return {
                "id": str(row[0]),
                "recorded_at": row[1].isoformat() if hasattr(row[1], 'isoformat') else str(row[1]),
                "is_compliant": is_compliant
            }

