from django.contrib import admin
from .models import Recipe


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = [
        "product_id",
        "portion_size",
        "kcal_100g",
        "proteines_100g",
        "lipides_100g",
        "created_at",
        "updated_at",
    ]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["product_id", "ingredients_raw", "allergens"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("product_id", "portion_size", "source_file")},
        ),
        (
            "Ingredients & Allergens",
            {"fields": ("ingredients_raw", "ingredients_list", "allergens")},
        ),
        (
            "Nutritional Values (per 100g)",
            {
                "fields": (
                    ("kcal_100g", "kj_100g"),
                    ("matieres_grasses_100g", "lipides_100g"),
                    ("acides_gras_satures_100g", "glucides_100g"),
                    ("sucres_100g", "amidon_100g"),
                    ("fibres_100g", "proteines_100g", "sel_100g"),
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
