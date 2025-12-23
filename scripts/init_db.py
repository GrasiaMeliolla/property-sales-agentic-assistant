#!/usr/bin/env python
"""Initialize database and ingest property data from CSV."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Base, Project

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).parent.parent / "Property sales agent - Challenge.csv"


def parse_price(value: str) -> float | None:
    if not value or value.strip() == "":
        return None
    try:
        cleaned = value.replace(",", "").replace("$", "").strip()
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def parse_int(value: str) -> int | None:
    if not value or value.strip() == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def parse_float(value: str) -> float | None:
    if not value or value.strip() == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_json_array(value: str) -> list:
    if not value or value.strip() in ("", "[]"):
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def parse_completion_status(value: str) -> str | None:
    if not value or value.strip() == "":
        return None
    value = value.strip().lower()
    if "available" in value:
        return "available"
    if "off" in value or "plan" in value:
        return "off_plan"
    return value


def init_database():
    """Create all tables."""
    logger.info("Creating database tables...")
    engine = create_engine(settings.sync_database_url)
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created successfully")
    return engine


def check_data_exists(engine) -> bool:
    """Check if projects table already has data."""
    with Session(engine) as session:
        result = session.execute(text("SELECT COUNT(*) FROM projects"))
        count = result.scalar()
        return count > 0


def ingest_csv_data(engine):
    """Ingest property data from CSV file."""
    if not CSV_PATH.exists():
        logger.warning(f"CSV file not found: {CSV_PATH}")
        return

    if check_data_exists(engine):
        logger.info("Data already exists in database, skipping ingestion")
        return

    logger.info(f"Reading CSV from {CSV_PATH}")

    projects = []
    skipped = 0

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            project_name = row.get("Project name", "").strip()

            # Skip rows without project name (these are continuation rows in the CSV)
            if not project_name:
                skipped += 1
                continue

            project = Project(
                project_name=project_name,
                bedrooms=parse_int(row.get("No of bedrooms")),
                bathrooms=parse_int(row.get("bathrooms")),
                completion_status=parse_completion_status(row.get("Completion status (off plan/available)")),
                unit_type=row.get("unit type", "").strip() or None,
                developer_name=row.get("developer name", "").strip() or None,
                price_usd=parse_price(row.get("Price (USD)")),
                area_sqm=parse_float(row.get("Area (sq mtrs)")),
                property_type=row.get("Property type (apartment/villa)", "").strip().lower() or None,
                city=row.get("city", "").strip() or None,
                country=row.get("country", "").strip() or None,
                completion_date=row.get("completion_date", "").strip() or None,
                features=parse_json_array(row.get("features", "[]")),
                facilities=parse_json_array(row.get("facilities", "[]")),
                description=row.get("Project description", "").strip() or None
            )
            projects.append(project)

    logger.info(f"Parsed {len(projects)} projects, skipped {skipped} rows")

    # Batch insert
    with Session(engine) as session:
        session.add_all(projects)
        session.commit()

    logger.info(f"Inserted {len(projects)} projects into database")


def main():
    engine = init_database()
    ingest_csv_data(engine)
    logger.info("Database initialization complete")


if __name__ == "__main__":
    main()
