"""Initial PostGIS and FoodBridge Core Schema

Revision ID: 001_initial_postgis_schema
Revises: None
Create Date: 2026-11-06

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_postgis_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # 2. Execute full schema DDL
    with open("database/schema.sql", "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Strip pure comment headers and execute
    op.execute(schema_sql)

def downgrade() -> None:
    tables = [
        "audit_logs",
        "tax_receipts",
        "custody_transfers",
        "temperature_logs",
        "dispatches",
        "manifest_items",
        "donations",
        "users",
        "facilities",
        "organizations"
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")

    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE;")
    op.execute("DROP EXTENSION IF EXISTS \"uuid-ossp\" CASCADE;")

