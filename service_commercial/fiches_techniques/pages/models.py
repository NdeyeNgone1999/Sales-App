from django.db import models
from django.core.validators import MinValueValidator
import json
import re


class Recipe(models.Model):
    product_id = models.CharField(max_length=100, unique=True, db_index=True)
    product_name = models.CharField(max_length=200, blank=True, null=True)
    portion_size = models.CharField(max_length=50, blank=True, null=True)

    # Use TextField for ingredients as it can be long
    ingredients_raw = models.TextField(
        blank=True, null=True, help_text="Raw ingredients text"
    )
    ingredients_list = models.JSONField(
        default=list, blank=True, help_text="List of ingredients"
    )

    allergens = models.TextField(blank=True, null=True)

    # Protein source extracted from ingredients
    protein_source = models.CharField(max_length=200, blank=True, null=True)

    # Tags for recipe categorization
    tags = models.JSONField(
        default=list, blank=True, help_text="List of tags for the recipe"
    )

    # Nutritional values per 100g
    kcal_100g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    kj_100g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    matieres_grasses_100g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    lipides_100g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    acides_gras_satures_100g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    glucides_100g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    sucres_100g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    amidon_100g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    fibres_100g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    proteines_100g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    sel_100g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    # Metadata
    source_file = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product_id"]
        verbose_name = "Recipe"
        verbose_name_plural = "Recipes"

    def __str__(self):
        return f"{self.product_id}"

    @property
    def ingredients_display(self):
        """Return a formatted string of ingredients for display"""
        if self.ingredients_list:
            return "; ".join(self.ingredients_list)
        return self.ingredients_raw or ""

    @property
    def tags_display(self):
        """Return a formatted string of tags for display"""
        if self.tags:
            return ", ".join(self.tags)
        return ""

    @classmethod
    def get_all_tags(cls):
        """Get all unique tags across all recipes"""
        all_tags = set()
        recipes_with_tags = cls.objects.exclude(tags__isnull=True).exclude(tags=[])
        for recipe in recipes_with_tags:
            if recipe.tags:
                all_tags.update(recipe.tags)
        return sorted(list(all_tags))

    @classmethod
    def get_all_ingredients(cls):
        """Get all unique ingredients across all recipes"""
        all_ingredients = set()
        recipes_with_ingredients = cls.objects.exclude(
            ingredients_list__isnull=True
        ).exclude(ingredients_list=[])
        for recipe in recipes_with_ingredients:
            if recipe.ingredients_list:
                for ingredient in recipe.ingredients_list:
                    # Clean ingredient: remove '&' character and extra whitespace
                    cleaned = ingredient.replace("&", "").strip()
                    if cleaned:  # Only add non-empty ingredients
                        all_ingredients.add(cleaned)
        return sorted(list(all_ingredients))

    @classmethod
    def get_all_allergens(cls):
        """Get all unique allergens across all recipes"""
        all_allergens = set()

        # Define unwanted terms to exclude
        unwanted_terms = {
            "contient",
            "none",
            "none contain",
            "no contain",
            "no contains",
            "no contains",
            "contain",
            "contains",
            ". contient",
        }

        recipes_with_allergens = cls.objects.exclude(allergens__isnull=True).exclude(
            allergens__exact=""
        )
        for recipe in recipes_with_allergens:
            if recipe.allergens:
                # Split by semicolon and comma, clean up
                allergen_parts = recipe.allergens.replace(";", ",").split(",")
                for part in allergen_parts:
                    cleaned = part.strip()
                    if cleaned:
                        # Remove unwanted suffixes like ". Contient"
                        cleaned = re.sub(
                            r"\s*\.\s*contient.*$", "", cleaned, flags=re.IGNORECASE
                        )
                        cleaned = re.sub(
                            r"\s*\.\s*gluten.*$", "", cleaned, flags=re.IGNORECASE
                        )
                        cleaned = cleaned.strip()

                        # Skip unwanted terms
                        if cleaned.lower() not in unwanted_terms and cleaned:
                            # Normalize capitalization (first letter uppercase, rest lowercase)
                            normalized = cleaned.lower().capitalize()
                            all_allergens.add(normalized)

        return sorted(list(all_allergens))

    @classmethod
    def get_all_protein_sources(cls):
        """Get all unique protein sources across all recipes"""
        all_protein_sources = set()
        protein_mapping = {}  # To track singular forms and avoid duplicates

        recipes_with_protein_sources = cls.objects.exclude(
            protein_source__isnull=True
        ).exclude(protein_source__exact="")

        for recipe in recipes_with_protein_sources:
            if recipe.protein_source:
                # Split by semicolon and comma, clean up
                protein_parts = recipe.protein_source.replace(";", ",").split(",")
                for part in protein_parts:
                    cleaned = part.strip()
                    if cleaned:
                        # Normalize capitalization (first letter uppercase, rest lowercase)
                        normalized = cleaned.lower().capitalize()

                        # Handle plurals - convert to singular form for comparison
                        singular_key = normalized.lower()
                        if singular_key.endswith("s") and len(singular_key) > 3:
                            # Remove 's' for basic plurals (proteins -> protein)
                            singular_key = singular_key[:-1]

                        # If we haven't seen this singular form, or if current is singular, use it
                        if (
                            singular_key not in protein_mapping
                            or not normalized.lower().endswith("s")
                        ):
                            protein_mapping[singular_key] = normalized

        return sorted(list(protein_mapping.values()))
