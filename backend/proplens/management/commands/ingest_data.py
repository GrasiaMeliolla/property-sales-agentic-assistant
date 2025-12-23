"""Management command to ingest property data from CSV."""
import csv
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from proplens.models import Project


class Command(BaseCommand):
    """Ingest property data from CSV file."""

    help = "Ingest property data from CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="/app/data/properties.csv",
            help="Path to CSV file"
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before import"
        )

    def handle(self, *args, **options):
        csv_path = Path(options["file"])

        if not csv_path.exists():
            self.stderr.write(f"File not found: {csv_path}")
            return

        if options["clear"]:
            count = Project.objects.count()
            Project.objects.all().delete()
            self.stdout.write(f"Cleared {count} existing projects")

        projects_created = 0
        projects_updated = 0

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):
                try:
                    price = None
                    price_str = row.get("Price (USD)", "") or row.get("Price", "")
                    if price_str:
                        price_str = str(price_str).replace(",", "").replace("$", "").strip()
                        if price_str:
                            try:
                                price = float(price_str)
                            except ValueError:
                                pass

                    bedrooms = None
                    bed_str = row.get("No of bedrooms", "") or row.get("Bedrooms", "")
                    if bed_str:
                        try:
                            bedrooms = int(bed_str)
                        except ValueError:
                            pass

                    bathrooms = None
                    bath_str = row.get("bathrooms", "") or row.get("Bathrooms", "")
                    if bath_str:
                        try:
                            bathrooms = int(bath_str)
                        except ValueError:
                            pass

                    area = None
                    area_str = row.get("Area (sq mtrs)", "") or row.get("Area (sqm)", "")
                    if area_str:
                        try:
                            area = float(area_str)
                        except ValueError:
                            pass

                    features = []
                    feat_str = row.get("features", "") or row.get("Features", "")
                    if feat_str:
                        try:
                            features = json.loads(feat_str)
                        except json.JSONDecodeError:
                            features = [f.strip() for f in feat_str.split(",") if f.strip()]

                    facilities = []
                    fac_str = row.get("facilities", "") or row.get("Facilities", "")
                    if fac_str:
                        try:
                            facilities = json.loads(fac_str)
                        except json.JSONDecodeError:
                            facilities = [f.strip() for f in fac_str.split(",") if f.strip()]

                    project_name = (row.get("Project name", "") or row.get("Project Name", "")).strip()

                    # If no project name, try to generate from city/developer
                    if not project_name:
                        city = (row.get("city", "") or row.get("City", "")).strip()
                        developer = (row.get("developer name", "") or row.get("Developer Name", "")).strip()
                        if city and developer:
                            project_name = f"{developer} - {city}"
                        elif city:
                            project_name = f"Property in {city} (Row {row_num})"
                        else:
                            continue

                    completion_status = (row.get("Completion status (off plan/available)", "") or row.get("Completion Status", "")).strip()
                    unit_type = (row.get("unit type", "") or row.get("Unit Type", "")).strip()
                    developer_name = (row.get("developer name", "") or row.get("Developer Name", "")).strip()
                    property_type = (row.get("Property type (apartment/villa)", "") or row.get("Property Type", "")).strip().lower()
                    city = (row.get("city", "") or row.get("City", "")).strip()
                    country = (row.get("country", "") or row.get("Country", "")).strip()
                    completion_date = (row.get("completion_date", "") or row.get("Completion Date", "")).strip()
                    description = (row.get("Project description", "") or row.get("Description", "")).strip()

                    project, created = Project.objects.update_or_create(
                        project_name=project_name,
                        defaults={
                            "bedrooms": bedrooms,
                            "bathrooms": bathrooms,
                            "completion_status": completion_status or None,
                            "unit_type": unit_type or None,
                            "developer_name": developer_name or None,
                            "price_usd": price,
                            "area_sqm": area,
                            "property_type": property_type or None,
                            "city": city or None,
                            "country": country or None,
                            "completion_date": completion_date or None,
                            "features": features,
                            "facilities": facilities,
                            "description": description or None,
                        }
                    )

                    if created:
                        projects_created += 1
                    else:
                        projects_updated += 1

                except Exception as e:
                    self.stderr.write(f"Error processing row: {e}")
                    continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Data ingestion complete: {projects_created} created, {projects_updated} updated"
            )
        )
