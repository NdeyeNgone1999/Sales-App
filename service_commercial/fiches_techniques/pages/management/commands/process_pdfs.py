from django.core.management.base import BaseCommand
from service_commercial.fiches_techniques.pages.services import process_all_pdfs_in_data
import logging


class Command(BaseCommand):
    help = "Process all PDFs in a given directory and update the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "data_folder", type=str, help="Path to the directory containing PDF files"
        )
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Enable verbose output with detailed error information",
        )
        parser.add_argument(
            "--debug", action="store_true", help="Enable debug logging to console"
        )

    def handle(self, *args, **options):
        data_folder = options["data_folder"]
        verbose = options.get("verbose", False)
        debug = options.get("debug", False)

        # Configure logging level based on options
        if debug:
            logging.getLogger(
                "service_commercial.fiches_techniques.pages.services"
            ).setLevel(logging.DEBUG)
            logging.getLogger(
                "service_commercial.fiches_techniques.pages.views"
            ).setLevel(logging.DEBUG)

        self.stdout.write(
            self.style.SUCCESS(f"Starting PDF processing from: {data_folder}")
        )

        if verbose:
            self.stdout.write(
                "Verbose mode enabled - detailed error information will be shown"
            )
        if debug:
            self.stdout.write("Debug mode enabled - detailed logging to console")

        try:
            stats = process_all_pdfs_in_data(data_folder)

            # Display comprehensive statistics
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n{'='*60}\n"
                    f"PROCESSING COMPLETED!\n"
                    f"{'='*60}\n"
                    f'Total files found: {stats["total_files"]}\n'
                    f'Successfully processed: {stats["processed_files"]}\n'
                    f'Created new recipes: {stats["created_recipes"]}\n'
                    f'Updated existing recipes: {stats["updated_recipes"]}\n'
                    f'Total errors: {len(stats["errors"])}\n'
                    f'Total warnings: {len(stats.get("warnings", []))}\n'
                    f'Success rate: {(stats["processed_files"]/stats["total_files"]*100) if stats["total_files"] > 0 else 0:.1f}%'
                )
            )

            # Show warnings if any
            if stats.get("warnings"):
                self.stdout.write(
                    self.style.WARNING(f"\n⚠️  WARNINGS ({len(stats['warnings'])}):")
                )
                for warning in stats["warnings"]:
                    self.stdout.write(f"  - {warning}")

            # Show errors if any
            if stats["errors"]:
                self.stdout.write(
                    self.style.WARNING(f"\n❌ ERRORS ({len(stats['errors'])}):")
                )
                for error in stats["errors"]:
                    self.stdout.write(f"  - {error}")

            # Show detailed file statistics if verbose
            if verbose and stats.get("file_stats"):
                self.stdout.write(f"\n📊 DETAILED FILE STATISTICS:")
                self.stdout.write(
                    f"{'Filename':<30} {'Status':<15} {'Product ID':<15} {'Errors':<8} {'Warnings':<8}"
                )
                self.stdout.write(f"{'-'*80}")

                for filename, file_stat in stats["file_stats"].items():
                    status = file_stat.get("status", "unknown")
                    product_id = (
                        file_stat.get("product_id", "N/A")[:12] + "..."
                        if len(file_stat.get("product_id", "")) > 12
                        else file_stat.get("product_id", "N/A")
                    )
                    error_count = len(file_stat.get("processing_errors", []))
                    warning_count = len(file_stat.get("warnings", []))

                    # Color code the status
                    if status in ["saved", "processed"]:
                        status_display = self.style.SUCCESS(status)
                    elif status in ["failed", "exception", "db_error", "no_product_id"]:
                        status_display = self.style.ERROR(status)
                    else:
                        status_display = status

                    self.stdout.write(
                        f"{filename[:29]:<30} {status:<15} {product_id:<15} {error_count:<8} {warning_count:<8}"
                    )

            # Show detailed errors if verbose
            if verbose and stats.get("detailed_errors"):
                self.stdout.write(f"\n🔍 DETAILED ERROR BREAKDOWN:")
                for filename, errors in stats["detailed_errors"].items():
                    self.stdout.write(f"\n  📄 {filename}:")
                    for error in errors:
                        self.stdout.write(f"    ❌ {error}")

            # Final summary with recommendations
            self.stdout.write(f"\n💡 RECOMMENDATIONS:")
            if stats["errors"]:
                self.stdout.write(
                    f"  • Review error details above to identify common issues"
                )
                self.stdout.write(f"  • Check PDF file formatting and structure")
                self.stdout.write(
                    f"  • Ensure product IDs are clearly visible in PDF headers"
                )
            if stats.get("warnings"):
                self.stdout.write(f"  • Review warnings for data quality improvements")
            if stats["processed_files"] == stats["total_files"]:
                self.stdout.write(f"  ✅ All files processed successfully!")

            self.stdout.write(f"\n📋 Log files created:")
            self.stdout.write(f"  • recipe_processing.log - Detailed processing log")
            self.stdout.write(f"  • recipe_errors.log - Error-specific log")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Critical error during PDF processing: {str(e)}")
            )
            if debug:
                import traceback

                self.stdout.write(
                    self.style.ERROR(f"Traceback: {traceback.format_exc()}")
                )
            return
