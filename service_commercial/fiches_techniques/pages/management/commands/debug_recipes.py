"""
Debug management command for recipe processing.
"""

from django.core.management.base import BaseCommand
from service_commercial.fiches_techniques.pages.debug_utils import (
    debug_single_pdf,
    test_pdf_batch,
)
import os


class Command(BaseCommand):
    help = "Debug recipe processing for specific PDF files or batches"

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, help="Debug a specific PDF file")
        parser.add_argument(
            "--batch", type=str, help="Debug a batch of PDF files from a directory"
        )
        parser.add_argument(
            "--max-files",
            type=int,
            default=5,
            help="Maximum number of files to test in batch mode (default: 5)",
        )
        parser.add_argument(
            "--quiet", action="store_true", help="Reduce output verbosity"
        )

    def handle(self, *args, **options):
        file_path = options.get("file")
        batch_path = options.get("batch")
        max_files = options.get("max_files", 5)
        quiet = options.get("quiet", False)

        if not file_path and not batch_path:
            self.stdout.write(
                self.style.ERROR(
                    "Please specify either --file or --batch option.\n"
                    "Examples:\n"
                    "  python manage.py debug_recipes --file path/to/recipe.pdf\n"
                    "  python manage.py debug_recipes --batch path/to/pdf/directory"
                )
            )
            return

        if file_path and batch_path:
            self.stdout.write(
                self.style.ERROR("Please specify either --file OR --batch, not both.")
            )
            return

        try:
            if file_path:
                # Debug single file
                if not os.path.exists(file_path):
                    self.stdout.write(self.style.ERROR(f"File not found: {file_path}"))
                    return

                self.stdout.write(f"Debugging single PDF file: {file_path}")
                result = debug_single_pdf(file_path, verbose=not quiet)

                # Summary
                if result.get("product_id"):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Processing successful! Product ID: {result['product_id']}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR("❌ Processing failed - no product ID found")
                    )

            elif batch_path:
                # Debug batch
                if not os.path.exists(batch_path):
                    self.stdout.write(
                        self.style.ERROR(f"Directory not found: {batch_path}")
                    )
                    return

                self.stdout.write(f"Debugging PDF batch from: {batch_path}")
                results = test_pdf_batch(batch_path, max_files)

                if results.get("error"):
                    self.stdout.write(
                        self.style.ERROR(f"Batch test failed: {results['error']}")
                    )
                    return

                # Show detailed results if not quiet
                if not quiet and results.get("files"):
                    self.stdout.write("\n📋 DETAILED RESULTS:")
                    for filename, file_result in results["files"].items():
                        status_style = (
                            self.style.SUCCESS
                            if "SUCCESS" in file_result["status"]
                            else (
                                self.style.WARNING
                                if "WARNING" in file_result["status"]
                                else self.style.ERROR
                            )
                        )
                        self.stdout.write(
                            f"  {status_style(file_result['status'])} {filename}"
                        )
                        if file_result["product_id"]:
                            self.stdout.write(
                                f"    Product ID: {file_result['product_id']}"
                            )
                        if file_result["errors"]:
                            for error in file_result["errors"][
                                :2
                            ]:  # Show first 2 errors
                                self.stdout.write(f"    ❌ {error}")
                        if file_result["warnings"]:
                            for warning in file_result["warnings"][
                                :2
                            ]:  # Show first 2 warnings
                                self.stdout.write(f"    ⚠️  {warning}")

                # Final summary
                success_rate = (
                    (results["successful"] / results["total_tested"] * 100)
                    if results["total_tested"] > 0
                    else 0
                )
                if success_rate >= 80:
                    style = self.style.SUCCESS
                elif success_rate >= 50:
                    style = self.style.WARNING
                else:
                    style = self.style.ERROR

                self.stdout.write(
                    style(f"\n🎯 Final Results: {success_rate:.1f}% success rate")
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Command failed with error: {str(e)}"))
            if not quiet:
                import traceback

                self.stdout.write(f"Traceback: {traceback.format_exc()}")
