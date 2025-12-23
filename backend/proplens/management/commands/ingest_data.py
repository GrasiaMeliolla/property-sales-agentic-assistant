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

            for row in reader:
                try:
                    price = None
                    if row.get("Price"):
                        price_str = row["Price"].replace(",", "").replace("$", "").strip()
                        if price_str:
                            try:
                                price = float(price_str)
                            except ValueError:
                                pass

                    bedrooms = None
                    if row.get("Bedrooms"):
                        try:
                            bedrooms = int(row["Bedrooms"])
                        except ValueError:
                            pass

                    bathrooms = None
                    if row.get("Bathrooms"):
                        try:
                            bathrooms = int(row["Bathrooms"])
                        except ValueError:
                            pass

                    area = None
                    if row.get("Area (sqm)"):
                        try:
                            area = float(row["Area (sqm)"])
                        except ValueError:
                            pass

                    features = []
                    if row.get("Features"):
                        try:
                            features = json.loads(row["Features"])
                        except json.JSONDecodeError:
                            features = [f.strip() for f in row["Features"].split(",") if f.strip()]

                    facilities = []
                    if row.get("Facilities"):
                        try:
                            facilities = json.loads(row["Facilities"])
                        except json.JSONDecodeError:
                            facilities = [f.strip() for f in row["Facilities"].split(",") if f.strip()]

                    project_name = row.get("Project Name", "").strip()
                    if not project_name:
                        continue

                    project, created = Project.objects.update_or_create(
                        project_name=project_name,
                        defaults={
                            "bedrooms": bedrooms,
                            "bathrooms": bathrooms,
                            "completion_status": row.get("Completion Status", "").strip() or None,
                            "unit_type": row.get("Unit Type", "").strip() or None,
                            "developer_name": row.get("Developer Name", "").strip() or None,
                            "price_usd": price,
                            "area_sqm": area,
                            "property_type": row.get("Property Type", "").strip().lower() or None,
                            "city": row.get("City", "").strip() or None,
                            "country": row.get("Country", "").strip() or None,
                            "completion_date": row.get("Completion Date", "").strip() or None,
                            "features": features,
                            "facilities": facilities,
                            "description": row.get("Description", "").strip() or None,
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
