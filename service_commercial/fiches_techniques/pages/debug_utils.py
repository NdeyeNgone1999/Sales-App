"""
Debug utilities for recipe processing.
This module provides tools to help debug recipe upload issues.
"""

import logging
import os
from typing import Dict, Any
from django.conf import settings
from service_commercial.fiches_techniques.pages.services import process_single_pdf

logger = logging.getLogger("recipe_upload")


def debug_single_pdf(pdf_path: str, verbose: bool = True) -> Dict[str, Any]:
    """
    Debug a single PDF file processing with detailed logging.

    Args:
        pdf_path: Path to the PDF file
        verbose: If True, print detailed information to console

    Returns:
        Dictionary with processing results and debug information
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"🔍 DEBUGGING PDF: {os.path.basename(pdf_path)}")
        print(f"{'='*60}")
        print(f"File path: {pdf_path}")
        print(f"File exists: {os.path.exists(pdf_path)}")
        if os.path.exists(pdf_path):
            print(f"File size: {os.path.getsize(pdf_path)} bytes")
        print()

    try:
        # Enable debug logging temporarily
        original_level = logger.level
        logger.setLevel(logging.DEBUG)

        # Process the PDF
        result = process_single_pdf(pdf_path)

        if verbose:
            print("📊 PROCESSING RESULTS:")
            print(f"  Product ID: {result.get('product_id', 'NOT FOUND')}")
            print(f"  Product Name: {result.get('product_name', 'NOT FOUND')}")
            print(f"  Portion Size: {result.get('portion_size', 'NOT FOUND')}")
            print(f"  Protein Source: {result.get('protein_source', 'NOT FOUND')}")
            print(f"  Ingredients Count: {len(result.get('ingredients_list', []))}")
            print(f"  Allergens: {result.get('allergens', 'NOT FOUND')}")

            # Show nutritional data
            nutrition_fields = [
                "kcal_100g",
                "kj_100g",
                "matieres_grasses_100g",
                "lipides_100g",
                "acides_gras_satures_100g",
                "glucides_100g",
                "sucres_100g",
                "amidon_100g",
                "fibres_100g",
                "proteines_100g",
                "sel_100g",
            ]
            nutrition_found = []
            for field in nutrition_fields:
                if result.get(field) is not None:
                    nutrition_found.append(f"{field}: {result[field]}")

            print(f"  Nutrition Data: {len(nutrition_found)} fields found")
            if nutrition_found and verbose:
                for item in nutrition_found:
                    print(f"    - {item}")

            # Show processing errors
            if result.get("processing_errors"):
                print(f"\n❌ PROCESSING ERRORS ({len(result['processing_errors'])}):")
                for i, error in enumerate(result["processing_errors"], 1):
                    print(f"  {i}. {error}")

            # Show warnings
            if result.get("warnings"):
                print(f"\n⚠️  WARNINGS ({len(result['warnings'])}):")
                for i, warning in enumerate(result["warnings"], 1):
                    print(f"  {i}. {warning}")

            if not result.get("processing_errors") and not result.get("warnings"):
                print("\n✅ No errors or warnings!")

        # Restore original logging level
        logger.setLevel(original_level)

        return result

    except Exception as e:
        logger.setLevel(original_level)
        error_msg = f"Critical error during debug processing: {str(e)}"
        if verbose:
            print(f"\n💥 CRITICAL ERROR:")
            print(f"  {error_msg}")
            import traceback

            print(f"\nTraceback:")
            print(traceback.format_exc())

        return {
            "source_file": pdf_path,
            "product_id": "",
            "product_name": "",
            "processing_errors": [error_msg],
            "warnings": [],
            "debug_error": True,
        }


def test_pdf_batch(directory_path: str, max_files: int = 5) -> Dict[str, Any]:
    """
    Test a batch of PDF files for debugging purposes.

    Args:
        directory_path: Path to directory containing PDFs
        max_files: Maximum number of files to test

    Returns:
        Dictionary with batch testing results
    """
    print(f"\n🧪 TESTING PDF BATCH FROM: {directory_path}")
    print(f"Max files to test: {max_files}")
    print(f"{'='*80}")

    if not os.path.exists(directory_path):
        print(f"❌ Directory does not exist: {directory_path}")
        return {"error": "Directory not found"}

    # Find PDF files
    pdf_files = []
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
                if len(pdf_files) >= max_files:
                    break
        if len(pdf_files) >= max_files:
            break

    print(f"Found {len(pdf_files)} PDF files to test")

    results = {
        "total_tested": 0,
        "successful": 0,
        "with_errors": 0,
        "with_warnings": 0,
        "files": {},
    }

    for i, pdf_path in enumerate(pdf_files, 1):
        filename = os.path.basename(pdf_path)
        print(f"\n[{i}/{len(pdf_files)}] Testing: {filename}")

        result = debug_single_pdf(pdf_path, verbose=False)
        results["total_tested"] += 1

        has_errors = bool(result.get("processing_errors"))
        has_warnings = bool(result.get("warnings"))

        if has_errors:
            results["with_errors"] += 1
            status = "❌ ERRORS"
        elif has_warnings:
            results["with_warnings"] += 1
            status = "⚠️  WARNINGS"
        else:
            results["successful"] += 1
            status = "✅ SUCCESS"

        print(f"  Status: {status}")
        print(f"  Product ID: {result.get('product_id', 'NOT FOUND')}")

        results["files"][filename] = {
            "status": status,
            "product_id": result.get("product_id", ""),
            "errors": result.get("processing_errors", []),
            "warnings": result.get("warnings", []),
        }

    print(f"\n📈 BATCH TEST SUMMARY:")
    print(f"  Total tested: {results['total_tested']}")
    print(f"  Successful: {results['successful']}")
    print(f"  With errors: {results['with_errors']}")
    print(f"  With warnings: {results['with_warnings']}")
    print(
        f"  Success rate: {(results['successful']/results['total_tested']*100) if results['total_tested'] > 0 else 0:.1f}%"
    )

    return results
