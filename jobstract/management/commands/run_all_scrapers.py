from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from django.db import transaction
import logging
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run all job scrapers (SME, Reed, DWP) sequentially with error handling"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force run all scrapers even if they were recently run",
        )

        parser.add_argument(
            "--location",
            type=str,
            default="",
            help="Location to search for jobs (e.g., London)",
        )

        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="Number of days of jobs to scrape (for SME scraper)",
        )

        parser.add_argument(
            "--debug",
            action="store_true",
            help="Enable debug mode for verbose output",
        )

    def handle(self, *args, **options):
        force = options["force"]
        location = options["location"]
        days = options["days"]
        debug = options.get("debug", False)

        start_time = datetime.now()
        self.stdout.write(
            f"===== Starting all job scrapers at {start_time.strftime('%Y-%m-%d %H:%M:%S')} ====="
        )
        logger.info(
            f"Starting all job scrapers with force={force}, location={location}, days={days}, debug={debug}"
        )

        scrapers = [
            # SME Scraper temporarily disabled - SMEScraper service not implemented
            # {
            #     'name': 'SME Scraper',
            #     'command': 'scrape_jobs',
            #     'args': {
            #         'days': days,
            #         'force': force
            #     }
            # },
            {
                "name": "Reed Scraper",
                "command": "reed_scraper",
                "args": {
                    "location": location,
                    "distance": 10,  # Default distance
                    "debug": debug,
                },
            },
            {
                "name": "Adzuna Scraper",
                "command": "adzuna_scraper",
                "args": {
                    "location": location if location else "UK",
                    "days": days,
                    "results": 50,  # Max 50 per API call
                    "force": force,
                    "debug": debug,
                },
            },
            {
                "name": "DWP Scraper",
                "command": "dwp_scraper",
                "args": {
                    "location": location,
                    "distance": 20,  # Default distance
                    "debug": debug,
                },
            },
        ]

        results = []

        for scraper in scrapers:
            scraper_name = scraper["name"]
            command_name = scraper["command"]
            args = scraper["args"]

            self.stdout.write(f"\n----- Running {scraper_name} -----")
            logger.info(f"Starting {scraper_name}")

            try:
                # Start transaction for each scraper
                with transaction.atomic():
                    # Call the management command
                    call_command(command_name, **args)

                self.stdout.write(
                    self.style.SUCCESS(f"✓ {scraper_name} completed successfully")
                )
                logger.info(f"{scraper_name} completed successfully")
                results.append(
                    {
                        "scraper": scraper_name,
                        "status": "success",
                        "message": "Completed successfully",
                    }
                )
            except Exception as e:
                error_msg = str(e)
                trace = traceback.format_exc()
                self.stdout.write(
                    self.style.ERROR(f"✗ {scraper_name} failed: {error_msg}")
                )
                logger.error(f"{scraper_name} failed: {error_msg}")
                logger.error(trace)
                results.append(
                    {
                        "scraper": scraper_name,
                        "status": "error",
                        "message": error_msg,
                        "traceback": trace,
                    }
                )

        # Calculate runtime
        end_time = datetime.now()
        runtime = end_time - start_time

        # Print summary
        self.stdout.write("\n===== Job Scraper Summary =====")
        for result in results:
            status_symbol = "✓" if result["status"] == "success" else "✗"
            status_style = (
                self.style.SUCCESS
                if result["status"] == "success"
                else self.style.ERROR
            )
            self.stdout.write(
                status_style(
                    f"{status_symbol} {result['scraper']}: {result['message']}"
                )
            )

        self.stdout.write(f"\nTotal runtime: {runtime}")
        logger.info(f"All job scrapers completed. Total runtime: {runtime}")

        success_count = sum(1 for r in results if r["status"] == "success")
        if success_count == len(scrapers):
            self.stdout.write(
                self.style.SUCCESS("\nAll scrapers completed successfully!")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{success_count}/{len(scrapers)} scrapers completed successfully. Check logs for errors."
                )
            )
