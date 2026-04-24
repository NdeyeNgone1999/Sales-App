from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from decimal import Decimal, InvalidOperation
from .models import Recipe
import os
import threading
import uuid
import logging
import traceback
from django.core.cache import cache
import time
from django.http import JsonResponse
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.conf import settings
from django.urls import reverse

# Configure logger for this module
logger = logging.getLogger("service_commercial.fiches_techniques.pages.views")

# Debug mode flags
DEBUG_MODE = getattr(settings, "RECIPE_DEBUG_MODE", True)
DETAILED_ERRORS = getattr(settings, "RECIPE_DETAILED_ERRORS", True)


def progress_status(request, task_id):
    data = cache.get(f"progress_{task_id}")
    if not data:
        return JsonResponse(
            {"status": "unknown", "current": 0, "total": 0, "message": "No task found"},
            status=404,
        )
    return JsonResponse(data)


def home(request):
    """Home page with search functionality."""
    query_params = {}
    all_product_ids = (
        Recipe.objects.exclude(product_id__isnull=True)
        .exclude(product_id__exact="")
        .values_list("product_id", flat=True)
        .distinct()
    )
    valid_product_ids = [
        pid
        for pid in all_product_ids
        if len(pid) >= 3 and "/" not in pid and (not pid.isdigit() or len(pid) >= 3)
    ]

    filter_options = {
        "product_ids": sorted(valid_product_ids),
        "product_names": list(
            Recipe.objects.exclude(product_name__isnull=True)
            .exclude(product_name__exact="")
            .values_list("product_name", flat=True)
            .distinct()
            .order_by("product_name")
        ),
        "portion_sizes": list(
            Recipe.objects.exclude(portion_size__isnull=True)
            .exclude(portion_size__exact="")
            .values_list("portion_size", flat=True)
            .distinct()
            .order_by("portion_size")
        ),
        "protein_sources": Recipe.get_all_protein_sources(),
        "ingredients": Recipe.get_all_ingredients(),
        "allergens": Recipe.get_all_allergens(),
        "tags": Recipe.get_all_tags(),
    }

    if request.GET:
        from django.http import HttpResponseRedirect
        from urllib.parse import urlencode

        query_params = []

        multi_value_fields = [
            "product_id",
            "product_name",
            "portion_size",
            "protein_source",
            "ingredients",
            "ingredients_exclude",
            "allergens",
            "tags",
        ]
        for field in multi_value_fields:
            values = request.GET.getlist(field)
            for value in values:
                if value.strip():
                    query_params.append((field, value))

        single_value_fields = [
            "product_name_keyword",
            "protein_source_keyword",
            "ingredients_keyword",
            "allergens_keyword",
            "kcal_100g_min",
            "kcal_100g_max",
            "kj_100g_min",
            "kj_100g_max",
            "matieres_grasses_100g_min",
            "matieres_grasses_100g_max",
            "lipides_100g_min",
            "lipides_100g_max",
            "acides_gras_satures_100g_min",
            "acides_gras_satures_100g_max",
            "glucides_100g_min",
            "glucides_100g_max",
            "sucres_100g_min",
            "sucres_100g_max",
            "amidon_100g_min",
            "amidon_100g_max",
            "fibres_100g_min",
            "fibres_100g_max",
            "proteines_100g_min",
            "proteines_100g_max",
            "sel_100g_min",
            "sel_100g_max",
        ]
        for field in single_value_fields:
            value = request.GET.get(field, "").strip()
            if value:
                query_params.append((field, value))

        query_string = urlencode(query_params)
        return HttpResponseRedirect(f"{reverse('pages:search_results')}?{query_string}")

    # Preserve GET parameters for form field values
    query_params = {}
    if request.GET:
        # Multi-value fields
        multi_value_fields = [
            "product_id",
            "product_name",
            "portion_size",
            "protein_source",
            "ingredients",
            "ingredients_exclude",
            "allergens",
            "tags",
        ]
        for field in multi_value_fields:
            values = request.GET.getlist(field)
            if values:
                query_params[field] = [v for v in values if v.strip()]

        # Single-value fields (keyword searches)
        single_value_fields = [
            "product_name_keyword",
            "protein_source_keyword",
            "ingredients_keyword",
            "allergens_keyword",
        ]
        for field in single_value_fields:
            value = request.GET.get(field, "").strip()
            if value:
                query_params[field] = value

    context = {
        "total_recipes": Recipe.objects.count(),
        "filter_options": filter_options,
        "user_authenticated": True,
        "query_params": query_params,
    }

    return render(request, "pages/home.html", context)


def update_recipes(request):
    """Handle recipe updates by accepting uploads (ZIP of PDFs or multiple PDFs).
    This works on Heroku: we save uploads to a temp directory and process from there.
    """
    if request.method != "POST":
        return redirect("pages:update_recipes_form")

    # Prepare a temporary working directory
    import tempfile, shutil

    temp_dir = tempfile.mkdtemp(prefix="pdf_uploads_")
    task_id = str(uuid.uuid4())

    # Initialize progress
    cache.set(
        f"progress_{task_id}",
        {
            "status": "starting",
            "current": 0,
            "total": 0,
            "message": "Initializing...",
            "errors": [],
        },
        timeout=3600,
    )

    uploaded = False
    try:
        # Option A: a single ZIP containing many PDFs
        zip_file = request.FILES.get("zip_file")
        if zip_file and zip_file.size > 0:
            uploaded = True
            zip_path = os.path.join(temp_dir, "recipes.zip")
            with open(zip_path, "wb") as f:
                for chunk in zip_file.chunks():
                    f.write(chunk)
            import zipfile

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)

        # Option B: multiple individual PDFs
        pdf_files = request.FILES.getlist("pdfs")
        if pdf_files:
            uploaded = True
            for f in pdf_files:
                if not f.name.lower().endswith(".pdf"):
                    continue
                dest = os.path.join(temp_dir, os.path.basename(f.name))
                with open(dest, "wb") as out:
                    for chunk in f.chunks():
                        out.write(chunk)

        if not uploaded:
            return JsonResponse(
                {"error": "Please upload a ZIP of PDFs or select PDF files."},
                status=400,
            )

        # Run your existing processing in a background thread
        def process_pdfs_async():
            import shutil
            from .services import process_all_pdfs_in_data

            try:
                logger.info(f"Starting async PDF processing for task {task_id}")
                stats = process_all_pdfs_in_data(temp_dir, task_id)

                # Enhanced completion data with detailed statistics
                completion_data = {
                    "status": "completed",
                    "current": stats["processed_files"],
                    "total": stats["total_files"],
                    "message": f"Processing completed! Created: {stats['created_recipes']}, Updated: {stats['updated_recipes']}",
                    "stats": stats,
                    "errors": stats["errors"],
                    "warnings": stats.get("warnings", []),
                    "detailed_errors": stats.get("detailed_errors", {}),
                    "file_stats": stats.get("file_stats", {}),
                    "success_rate": (
                        (stats["processed_files"] / stats["total_files"] * 100)
                        if stats["total_files"] > 0
                        else 0
                    ),
                }

                cache.set(f"progress_{task_id}", completion_data, timeout=3600)
                logger.info(
                    f"Task {task_id} completed successfully. Processed: {stats['processed_files']}/{stats['total_files']}"
                )

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Task {task_id} failed with error: {error_msg}")

                error_data = {
                    "status": "error",
                    "current": 0,
                    "total": 0,
                    "message": error_msg,
                    "errors": [error_msg],
                }

                if DETAILED_ERRORS:
                    error_data["traceback"] = traceback.format_exc()
                    logger.error(f"Task {task_id} traceback: {traceback.format_exc()}")

                cache.set(f"progress_{task_id}", error_data, timeout=3600)

            finally:
                # Clean temp dir on Heroku
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.debug(f"Cleaned up temp directory for task {task_id}")
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to cleanup temp directory for task {task_id}: {str(cleanup_error)}"
                    )

        logger.info(f"Starting background processing thread for task {task_id}")
        threading.Thread(target=process_pdfs_async, daemon=True).start()
        return JsonResponse({"task_id": task_id})

    except Exception as e:
        try:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        return JsonResponse({"error": str(e)}, status=500)


def update_recipes_form(request):
    """Show the form to input data folder for updating recipes."""
    from datetime import datetime, timedelta

    total_recipes = Recipe.objects.count()
    recent_updates = Recipe.objects.filter(
        updated_at__gte=datetime.now() - timedelta(hours=24)
    ).count()

    context = {
        "total_recipes": total_recipes,
        "recent_updates": recent_updates,
    }
    return render(request, "pages/update_recipes.html", context)


def search_results(request):
    """Display search results page."""
    recipes = Recipe.objects.all()  # Start with all recipes
    query_params = {}
    has_valid_filters = False  # Track if any valid filters are applied

    # Get filter options for the search form
    all_product_ids = (
        Recipe.objects.exclude(product_id__isnull=True)
        .exclude(product_id__exact="")
        .values_list("product_id", flat=True)
        .distinct()
    )
    # Filter out obvious invalid product IDs (dates, very short numbers)
    valid_product_ids = [
        pid
        for pid in all_product_ids
        if len(pid) >= 3 and "/" not in pid and (not pid.isdigit() or len(pid) >= 3)
    ]

    filter_options = {
        "product_ids": sorted(valid_product_ids),
        "product_names": list(
            Recipe.objects.exclude(product_name__isnull=True)
            .exclude(product_name__exact="")
            .values_list("product_name", flat=True)
            .distinct()
            .order_by("product_name")
        ),
        "portion_sizes": list(
            Recipe.objects.exclude(portion_size__isnull=True)
            .exclude(portion_size__exact="")
            .values_list("portion_size", flat=True)
            .distinct()
            .order_by("portion_size")
        ),
        "protein_sources": Recipe.get_all_protein_sources(),
        "ingredients": Recipe.get_all_ingredients(),
        "allergens": Recipe.get_all_allergens(),
        "tags": Recipe.get_all_tags(),
    }

    if request.GET:
        # Get search parameters (supporting multiple values)
        product_ids = request.GET.getlist("product_id")  # Multiple values
        product_names = request.GET.getlist("product_name")  # Multiple values
        portion_sizes = request.GET.getlist("portion_size")  # Multiple values
        protein_sources = request.GET.getlist("protein_source")  # Multiple values
        ingredients = request.GET.getlist("ingredients")  # Multiple values
        ingredients_exclude = request.GET.getlist(
            "ingredients_exclude"
        )  # Multiple values
        allergens = request.GET.getlist("allergens")  # Multiple values

        # Get keyword search parameters (free text search)
        product_name_keyword = request.GET.get("product_name_keyword", "").strip()
        protein_source_keyword = request.GET.get("protein_source_keyword", "").strip()
        ingredients_keyword = request.GET.get("ingredients_keyword", "").strip()
        allergens_keyword = request.GET.get("allergens_keyword", "").strip()

        # Build query
        # recipes = Recipe.objects.all()  # Already initialized above

        # Handle multiple product IDs
        if product_ids and any(pid.strip() for pid in product_ids):
            valid_product_ids = [pid.strip() for pid in product_ids if pid.strip()]
            product_q = Q()
            for pid in valid_product_ids:
                product_q |= Q(product_id__icontains=pid)
            recipes = recipes.filter(product_q)
            query_params["product_id"] = valid_product_ids
            has_valid_filters = True

        # Handle multiple product names
        if product_names and any(pn.strip() for pn in product_names):
            valid_product_names = [pn.strip() for pn in product_names if pn.strip()]
            product_name_q = Q()
            for pn in valid_product_names:
                product_name_q |= Q(product_name__icontains=pn)
            recipes = recipes.filter(product_name_q)
            query_params["product_name"] = valid_product_names
            has_valid_filters = True

        # Handle multiple portion sizes
        if portion_sizes and any(ps.strip() for ps in portion_sizes):
            valid_portion_sizes = [ps.strip() for ps in portion_sizes if ps.strip()]
            portion_q = Q()
            for ps in valid_portion_sizes:
                portion_q |= Q(portion_size__icontains=ps)
            recipes = recipes.filter(portion_q)
            query_params["portion_size"] = valid_portion_sizes
            has_valid_filters = True

        # Handle multiple protein sources
        if protein_sources and any(ps.strip() for ps in protein_sources):
            valid_protein_sources = [ps.strip() for ps in protein_sources if ps.strip()]
            protein_q = Q()
            for ps in valid_protein_sources:
                protein_q |= Q(protein_source__icontains=ps)
            recipes = recipes.filter(protein_q)
            query_params["protein_source"] = valid_protein_sources
            has_valid_filters = True

        # Handle multiple ingredients (multiple values)
        if ingredients and any(ing.strip() for ing in ingredients):
            valid_ingredients = [ing.strip() for ing in ingredients if ing.strip()]
            ingredients_q = Q()
            for ingredient in valid_ingredients:
                ingredients_q |= Q(ingredients_raw__icontains=ingredient) | Q(
                    ingredients_list__icontains=ingredient
                )
            recipes = recipes.filter(ingredients_q)
            query_params["ingredients"] = valid_ingredients
            has_valid_filters = True

        # Handle ingredient exclusion (multiple values)
        if ingredients_exclude and any(ing.strip() for ing in ingredients_exclude):
            valid_ingredients_exclude = [
                ing.strip() for ing in ingredients_exclude if ing.strip()
            ]
            for ingredient in valid_ingredients_exclude:
                # Exclude recipes that contain this ingredient
                recipes = recipes.exclude(
                    Q(ingredients_raw__icontains=ingredient)
                    | Q(ingredients_list__icontains=ingredient)
                )
            query_params["ingredients_exclude"] = valid_ingredients_exclude
            has_valid_filters = True

        # Handle multiple allergens (multiple values)
        if allergens and any(allergen.strip() for allergen in allergens):
            valid_allergens = [
                allergen.strip() for allergen in allergens if allergen.strip()
            ]
            allergens_q = Q()
            for allergen in valid_allergens:
                allergens_q |= Q(allergens__icontains=allergen)
            recipes = recipes.filter(allergens_q)
            query_params["allergens"] = valid_allergens
            has_valid_filters = True

        # Handle tag filtering
        selected_tags = request.GET.getlist("tags")  # Multiple values
        if selected_tags and any(tag.strip() for tag in selected_tags):
            valid_tags = [tag.strip() for tag in selected_tags if tag.strip()]
            tags_q = Q()
            for tag in valid_tags:
                tags_q |= Q(tags__icontains=tag)
            recipes = recipes.filter(tags_q)
            query_params["tags"] = valid_tags
            has_valid_filters = True

        # Handle keyword searches (free text input)
        if product_name_keyword:
            recipes = recipes.filter(product_name__icontains=product_name_keyword)
            query_params["product_name_keyword"] = product_name_keyword
            has_valid_filters = True

        if protein_source_keyword:
            recipes = recipes.filter(protein_source__icontains=protein_source_keyword)
            query_params["protein_source_keyword"] = protein_source_keyword
            has_valid_filters = True

        if ingredients_keyword:
            recipes = recipes.filter(
                Q(ingredients_raw__icontains=ingredients_keyword)
                | Q(ingredients_list__icontains=ingredients_keyword)
            )
            query_params["ingredients_keyword"] = ingredients_keyword
            has_valid_filters = True

        if allergens_keyword:
            recipes = recipes.filter(allergens__icontains=allergens_keyword)
            query_params["allergens_keyword"] = allergens_keyword
            has_valid_filters = True

        # Nutritional value filters
        nutritional_fields = [
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

        for field in nutritional_fields:
            min_val = request.GET.get(f"{field}_min", "").strip()
            max_val = request.GET.get(f"{field}_max", "").strip()

            if min_val:
                try:
                    min_decimal = Decimal(min_val)
                    recipes = recipes.filter(**{f"{field}__gte": min_decimal})
                    query_params[f"{field}_min"] = min_val
                    has_valid_filters = True
                except (InvalidOperation, ValueError):
                    pass

            if max_val:
                try:
                    max_decimal = Decimal(max_val)
                    recipes = recipes.filter(**{f"{field}__lte": max_decimal})
                    query_params[f"{field}_max"] = max_val
                    has_valid_filters = True
                except (InvalidOperation, ValueError):
                    pass

    # Group recipes by tags for better organization
    grouped_recipes = {}
    recipes_without_tags = []

    for recipe in recipes:
        if recipe.tags:
            # Group by the first tag (primary category)
            primary_tag = recipe.tags[0] if recipe.tags else "Other"
            if primary_tag not in grouped_recipes:
                grouped_recipes[primary_tag] = []
            grouped_recipes[primary_tag].append(recipe)
        else:
            recipes_without_tags.append(recipe)

    # If there are recipes without tags, add them to "Other" group
    if recipes_without_tags:
        grouped_recipes["Other"] = recipes_without_tags

    # Sort groups by tag name for consistent display
    sorted_groups = sorted(grouped_recipes.items())

    # Pagination - we'll paginate the entire result set but display grouped
    paginator = Paginator(
        recipes, 24
    )  # Show more recipes per page since we're grouping
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "grouped_recipes": sorted_groups,
        "query_params": query_params,
        "total_recipes": Recipe.objects.count(),
        "filtered_count": recipes.count(),
        "has_filters": has_valid_filters,
        "show_grouped": True,  # Flag to indicate we want grouped display
        "filter_options": filter_options,  # Add filter options for refinement
    }

    return render(request, "pages/search_results.html", context)


def recipe_detail(request, recipe_id):
    """Display detailed recipe information."""
    recipe = get_object_or_404(Recipe, id=recipe_id)

    # Handle tag operations
    if request.method == "POST":
        if "add_tag" in request.POST:
            new_tag = request.POST.get("new_tag", "").strip()
            if new_tag and new_tag not in (recipe.tags or []):
                if recipe.tags is None:
                    recipe.tags = []
                recipe.tags.append(new_tag)
                recipe.save()
                messages.success(request, f"Tag '{new_tag}' added successfully!")
            elif new_tag in (recipe.tags or []):
                messages.warning(
                    request, f"Tag '{new_tag}' already exists for this recipe."
                )
            else:
                messages.error(request, "Please enter a valid tag.")

        elif "remove_tag" in request.POST:
            tag_to_remove = request.POST.get("remove_tag", "").strip()
            if tag_to_remove and recipe.tags and tag_to_remove in recipe.tags:
                recipe.tags.remove(tag_to_remove)
                recipe.save()
                messages.success(
                    request, f"Tag '{tag_to_remove}' removed successfully!"
                )

        return redirect("pages:recipe_detail", recipe_id=recipe_id)

    # Get all existing tags for autocomplete
    all_tags = Recipe.get_all_tags()

    context = {
        "recipe": recipe,
        "all_tags": all_tags,
    }

    return render(request, "pages/recipe_detail.html", context)


def check_progress(request, task_id):
    """Check the progress of a PDF processing task."""
    progress_data = cache.get(f"progress_{task_id}")

    if progress_data is None:
        return JsonResponse({"error": "Task not found"}, status=404)

    return JsonResponse(progress_data)


def get_tags(request):
    """Get all existing tags for autocomplete."""
    if request.method == "GET":
        tags = Recipe.get_all_tags()
        return JsonResponse({"tags": tags})
    return JsonResponse({"error": "Method not allowed"}, status=405)


def export_recipe_word(request, recipe_id):
    """Export recipe to Word document with nutritional calculator values."""
    from django.http import HttpResponse
    from docx import Document
    from docx.shared import Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    from docx.oxml.shared import OxmlElement, qn
    from io import BytesIO
    import json

    recipe = get_object_or_404(Recipe, id=recipe_id)

    # Get nutritional calculator values from POST data
    calculator_data = {}
    if request.method == "POST":
        try:
            calculator_json = request.POST.get("calculator_data", "{}")
            calculator_data = json.loads(calculator_json)
        except (json.JSONDecodeError, ValueError):
            calculator_data = {}

    # Create a new Document
    doc = Document()

    # Font configuration - easy to change
    DOCUMENT_FONT = "Calibri"  # Alternative options: 'Arial', 'Segoe UI', 'Helvetica'
    BASE_FONT_SIZE = 11
    TITLE_FONT_SIZE = 16
    HEADING_FONT_SIZE = 14
    SUBHEADING_FONT_SIZE = 13
    FOOTER_FONT_SIZE = 10

    # Set default font for the document
    def set_document_font(doc, font_name=DOCUMENT_FONT):
        """Set the default font for the entire document"""
        # Get the document's style object
        style = doc.styles["Normal"]
        font = style.font
        font.name = font_name
        font.size = Pt(BASE_FONT_SIZE)

        # Also set the font for the document defaults
        element = style.element
        element.rPr.rFonts.set(qn("w:asciiTheme"), font_name)
        element.rPr.rFonts.set(qn("w:eastAsiaTheme"), font_name)
        element.rPr.rFonts.set(qn("w:hAnsiTheme"), font_name)
        element.rPr.rFonts.set(qn("w:cstheme"), font_name)

    # Apply the font setting
    set_document_font(doc, DOCUMENT_FONT)

    # Add title
    title = doc.add_heading("Recipe Summary", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # Set title font
    for run in title.runs:
        run.font.name = DOCUMENT_FONT
        run.font.size = Pt(TITLE_FONT_SIZE)

    # Add product ID and portion size
    product_heading = doc.add_heading(f"Product: {recipe.product_id}", level=1)
    for run in product_heading.runs:
        run.font.name = DOCUMENT_FONT
        run.font.size = Pt(HEADING_FONT_SIZE)

    if recipe.portion_size:
        portion_para = doc.add_paragraph(f"Portion Size: {recipe.portion_size}")
        for run in portion_para.runs:
            run.font.name = DOCUMENT_FONT
            run.font.size = Pt(BASE_FONT_SIZE)

    # Add separator
    separator_para = doc.add_paragraph("=" * 60)
    for run in separator_para.runs:
        run.font.name = DOCUMENT_FONT
        run.font.size = Pt(BASE_FONT_SIZE)

    # Add nutritional information
    nutrition_heading = doc.add_heading("Nutritional Information", level=2)
    for run in nutrition_heading.runs:
        run.font.name = DOCUMENT_FONT
        run.font.size = Pt(SUBHEADING_FONT_SIZE)

    # Create nutritional table
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"

    # Helper function to set font for table cells
    def set_cell_font(
        cell, font_name=DOCUMENT_FONT, font_size=BASE_FONT_SIZE, bold=False
    ):
        """Set font for table cell content"""
        cell_text = cell.text
        for paragraph in cell.paragraphs:
            paragraph.clear()
            run = paragraph.add_run(cell_text)
            run.font.name = font_name
            run.font.size = Pt(font_size)
            if bold:
                run.font.bold = True

    # Add header row
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Nutrient"
    hdr_cells[1].text = "Per 100g"
    hdr_cells[2].text = "Calculated Portion"

    # Set font for header cells
    set_cell_font(hdr_cells[0], DOCUMENT_FONT, BASE_FONT_SIZE, bold=True)
    set_cell_font(hdr_cells[1], DOCUMENT_FONT, BASE_FONT_SIZE, bold=True)
    set_cell_font(hdr_cells[2], DOCUMENT_FONT, BASE_FONT_SIZE, bold=True)

    # Add nutritional data
    nutritional_fields = [
        ("Calories (kcal)", "kcal_100g", "kcal"),
        ("Energy (kJ)", "kj_100g", "kj"),
        ("Fats (g)", "matieres_grasses_100g", "fats"),
        ("Lipids (g)", "lipides_100g", "lipids"),
        ("Saturated Fatty Acids (g)", "acides_gras_satures_100g", "saturated_fats"),
        ("Carbohydrates (g)", "glucides_100g", "carbs"),
        ("Sugars (g)", "sucres_100g", "sugars"),
        ("Starch (g)", "amidon_100g", "starch"),
        ("Fiber (g)", "fibres_100g", "fiber"),
        ("Proteins (g)", "proteines_100g", "proteins"),
        ("Salt (g)", "sel_100g", "salt"),
    ]

    for label, field_name, calc_key in nutritional_fields:
        field_value = getattr(recipe, field_name, None)
        if field_value is not None:
            row_cells = table.add_row().cells
            row_cells[0].text = label
            row_cells[1].text = str(field_value)

            # Add calculated value if available
            calc_value = calculator_data.get(calc_key, "")
            row_cells[2].text = str(calc_value) if calc_value else "N/A"

            # Set font for all cells in this row
            set_cell_font(row_cells[0], DOCUMENT_FONT, BASE_FONT_SIZE)
            set_cell_font(row_cells[1], DOCUMENT_FONT, BASE_FONT_SIZE)
            set_cell_font(row_cells[2], DOCUMENT_FONT, BASE_FONT_SIZE)

    # Add ingredients section
    doc.add_paragraph()
    ingredients_heading = doc.add_heading("Key Ingredients", level=2)
    for run in ingredients_heading.runs:
        run.font.name = DOCUMENT_FONT
        run.font.size = Pt(SUBHEADING_FONT_SIZE)

    if recipe.ingredients_list:
        ingredients_para = doc.add_paragraph(recipe.ingredients_list)
    elif recipe.ingredients_raw:
        ingredients_para = doc.add_paragraph(recipe.ingredients_raw)
    else:
        ingredients_para = doc.add_paragraph("No ingredients information available.")

    for run in ingredients_para.runs:
        run.font.name = DOCUMENT_FONT
        run.font.size = Pt(BASE_FONT_SIZE)

    # Add allergens section
    doc.add_paragraph()
    allergens_heading = doc.add_heading("Allergens", level=2)
    for run in allergens_heading.runs:
        run.font.name = DOCUMENT_FONT
        run.font.size = Pt(SUBHEADING_FONT_SIZE)

    if recipe.allergens:
        allergens_para = doc.add_paragraph(recipe.allergens)
    else:
        allergens_para = doc.add_paragraph("No allergen information available.")

    for run in allergens_para.runs:
        run.font.name = DOCUMENT_FONT
        run.font.size = Pt(BASE_FONT_SIZE)

    # Add tags section
    if recipe.tags:
        doc.add_paragraph()
        tags_heading = doc.add_heading("Tags", level=2)
        for run in tags_heading.runs:
            run.font.name = DOCUMENT_FONT
            run.font.size = Pt(SUBHEADING_FONT_SIZE)

        tags_text = ", ".join(recipe.tags)
        tags_para = doc.add_paragraph(tags_text)
        for run in tags_para.runs:
            run.font.name = DOCUMENT_FONT
            run.font.size = Pt(BASE_FONT_SIZE)

    # Add footer with generation info
    doc.add_paragraph()
    separator2_para = doc.add_paragraph("=" * 60)
    for run in separator2_para.runs:
        run.font.name = DOCUMENT_FONT
        run.font.size = Pt(BASE_FONT_SIZE)

    footer = doc.add_paragraph("Generated by Bariatrix Europe Recipe System")
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in footer.runs:
        run.font.name = DOCUMENT_FONT
        run.font.size = Pt(FOOTER_FONT_SIZE)
        run.font.italic = True

    # Create response
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{recipe.product_id}_recipe_summary.docx"'
    )

    # Save document to response
    doc_io = BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    response.write(doc_io.getvalue())

    return response


def recipe_summary(request):
    """Display comprehensive recipe analytics and insights."""
    import plotly.graph_objects as go
    import plotly.express as px
    import pandas as pd
    from django.db.models import Count, Avg, Max, Min, Q
    from collections import Counter
    import json

    # Basic statistics
    total_recipes = Recipe.objects.count()

    # Nutritional statistics
    nutritional_stats = Recipe.objects.aggregate(
        avg_calories=Avg("kcal_100g"),
        max_calories=Max("kcal_100g"),
        min_calories=Min("kcal_100g"),
        avg_protein=Avg("proteines_100g"),
        max_protein=Max("proteines_100g"),
        min_protein=Min("proteines_100g"),
        avg_carbs=Avg("glucides_100g"),
        avg_fats=Avg("lipides_100g"),
    )

    # Product categories analysis
    product_ids = (
        Recipe.objects.exclude(product_id__isnull=True)
        .exclude(product_id__exact="")
        .values_list("product_id", flat=True)
    )

    # Portion size distribution
    portion_sizes = (
        Recipe.objects.exclude(portion_size__isnull=True)
        .exclude(portion_size__exact="")
        .values("portion_size")
        .annotate(count=Count("portion_size"))
        .order_by("-count")[:10]
    )

    # Tags analysis
    all_tags = []
    for recipe in Recipe.objects.exclude(tags__isnull=True):
        if recipe.tags:
            all_tags.extend(recipe.tags)
    tag_counter = Counter(all_tags)
    top_tags = tag_counter.most_common(10)

    # Create visualizations
    charts = {}

    # 1. Nutritional Distribution Charts
    if nutritional_stats["avg_calories"]:
        # Calories distribution
        calories_data = Recipe.objects.exclude(kcal_100g__isnull=True).values_list(
            "kcal_100g", flat=True
        )
        if calories_data:
            calories_fig = px.histogram(
                x=list(calories_data),
                nbins=30,
                title="Calories Distribution (per 100g)",
                labels={"x": "Calories (kcal)", "y": "Number of Recipes"},
                color_discrete_sequence=["#950b39"],
            )
            calories_fig.update_layout(
                plot_bgcolor="white",
                paper_bgcolor="white",
                font=dict(family="Arial", size=12),
                height=400,
            )
            charts["calories_distribution"] = calories_fig.to_html(
                include_plotlyjs="cdn", div_id="calories-chart"
            )

    # 2. Macronutrients comparison
    macro_data = Recipe.objects.filter(
        kcal_100g__isnull=False,
        proteines_100g__isnull=False,
        glucides_100g__isnull=False,
        lipides_100g__isnull=False,
    ).values("product_id", "proteines_100g", "glucides_100g", "lipides_100g")[:20]

    if macro_data:
        df_macro = pd.DataFrame(list(macro_data))
        macro_fig = go.Figure()

        macro_fig.add_trace(
            go.Bar(
                name="Proteins",
                x=df_macro["product_id"],
                y=df_macro["proteines_100g"],
                marker_color="#28a745",
            )
        )
        macro_fig.add_trace(
            go.Bar(
                name="Carbohydrates",
                x=df_macro["product_id"],
                y=df_macro["glucides_100g"],
                marker_color="#ffc107",
            )
        )
        macro_fig.add_trace(
            go.Bar(
                name="Lipids",
                x=df_macro["product_id"],
                y=df_macro["lipides_100g"],
                marker_color="#dc3545",
            )
        )

        macro_fig.update_layout(
            title="Macronutrients Comparison (Top 20 Products)",
            xaxis_title="Product ID",
            yaxis_title="Grams per 100g",
            barmode="group",
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(family="Arial", size=12),
            height=500,
            xaxis_tickangle=-45,
        )
        charts["macronutrients"] = macro_fig.to_html(
            include_plotlyjs="cdn", div_id="macro-chart"
        )

    # 3. Tags popularity chart
    if top_tags:
        tags_df = pd.DataFrame(top_tags, columns=["Tag", "Count"])
        tags_fig = px.bar(
            tags_df,
            x="Count",
            y="Tag",
            orientation="h",
            title="Most Popular Recipe Tags",
            color="Count",
            color_continuous_scale="Viridis",
        )
        tags_fig.update_layout(
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(family="Arial", size=12),
            height=400,
            yaxis={"categoryorder": "total ascending"},
        )
        charts["tags_popularity"] = tags_fig.to_html(
            include_plotlyjs="cdn", div_id="tags-chart"
        )

    # 4. Portion sizes distribution
    if portion_sizes:
        portion_labels = [p["portion_size"] for p in portion_sizes]
        portion_values = [p["count"] for p in portion_sizes]

        portion_fig = px.pie(
            values=portion_values,
            names=portion_labels,
            title="Portion Sizes Distribution",
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        portion_fig.update_layout(
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(family="Arial", size=12),
            height=400,
        )
        charts["portion_sizes"] = portion_fig.to_html(
            include_plotlyjs="cdn", div_id="portion-chart"
        )

    # 5. Nutritional quality scoring
    nutritional_quality = []
    for recipe in Recipe.objects.filter(
        kcal_100g__isnull=False,
        proteines_100g__isnull=False,
        fibres_100g__isnull=False,
        sucres_100g__isnull=False,
    )[:50]:
        # Simple quality score: high protein, high fiber, low sugar
        score = 0
        if recipe.proteines_100g and recipe.proteines_100g > 10:
            score += 2
        if recipe.fibres_100g and recipe.fibres_100g > 3:
            score += 2
        if recipe.sucres_100g and recipe.sucres_100g < 5:
            score += 1

        nutritional_quality.append(
            {
                "product_id": recipe.product_id,
                "quality_score": score,
                "calories": recipe.kcal_100g,
            }
        )

    if nutritional_quality:
        quality_df = pd.DataFrame(nutritional_quality)
        quality_fig = px.scatter(
            quality_df,
            x="calories",
            y="quality_score",
            hover_data=["product_id"],
            title="Nutritional Quality vs Calories",
            labels={"calories": "Calories (kcal)", "quality_score": "Quality Score"},
            color="quality_score",
            color_continuous_scale="RdYlGn",
        )
        quality_fig.update_layout(
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(family="Arial", size=12),
            height=400,
        )
        charts["nutritional_quality"] = quality_fig.to_html(
            include_plotlyjs="cdn", div_id="quality-chart"
        )

    context = {
        "total_recipes": total_recipes,
        "nutritional_stats": nutritional_stats,
        "portion_sizes": portion_sizes,
        "top_tags": top_tags,
        "charts": charts,
    }

    return render(request, "pages/recipe_summary.html", context)


@require_POST
def delete_recipe(request, recipe_id):
    """Delete a recipe from the database."""
    recipe = get_object_or_404(Recipe, id=recipe_id)
    product_id = recipe.product_id

    try:
        recipe.delete()
        messages.success(
            request,
            f"Recipe '{product_id}' has been successfully deleted from the database.",
        )
    except Exception as e:
        messages.error(request, f"Error deleting recipe '{product_id}': {str(e)}")

    # Redirect to search results or home page depending on referrer
    referer = request.META.get("HTTP_REFERER", "")
    if "search-results" in referer:
        return redirect("pages:search_results")
    else:
        return redirect("pages:home")
