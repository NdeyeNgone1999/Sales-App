from django.core.management.base import BaseCommand
from service_commercial.fiches_techniques.pages.models import Recipe
import re


class Command(BaseCommand):
    help = (
        "Populate recipe tags based on product names, ingredients, and characteristics"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        recipes = Recipe.objects.all()
        updated_count = 0

        for recipe in recipes:
            tags = []

            # Extract tags from product name
            if recipe.product_name:
                product_name = recipe.product_name.lower()

                # Food type tags
                if any(word in product_name for word in ["soup", "broth"]):
                    tags.append("Soup")
                elif any(
                    word in product_name for word in ["pudding", "mousse", "dessert"]
                ):
                    tags.append("Dessert")
                elif any(
                    word in product_name for word in ["drink", "milkshake", "beverage"]
                ):
                    tags.append("Beverage")
                elif any(
                    word in product_name for word in ["dish", "meal", "parmentier"]
                ):
                    tags.append("Main Dish")
                elif any(word in product_name for word in ["bar", "biscuit", "cookie"]):
                    tags.append("Snack")

                # Flavor tags
                if any(word in product_name for word in ["chocolate", "cocoa"]):
                    tags.append("Chocolate")
                elif any(word in product_name for word in ["vanilla"]):
                    tags.append("Vanilla")
                elif any(word in product_name for word in ["coffee", "cappuccino"]):
                    tags.append("Coffee")
                elif any(word in product_name for word in ["strawberry", "berry"]):
                    tags.append("Berry")
                elif any(word in product_name for word in ["lemon", "citrus"]):
                    tags.append("Citrus")
                elif any(word in product_name for word in ["caramel"]):
                    tags.append("Caramel")
                elif any(word in product_name for word in ["onion"]):
                    tags.append("Savory")

                # Texture/preparation tags
                if any(word in product_name for word in ["croutons", "toasted"]):
                    tags.append("Crunchy")
                elif any(word in product_name for word in ["cold"]):
                    tags.append("Cold")
                elif any(word in product_name for word in ["hot", "warm"]):
                    tags.append("Hot")

            # Extract tags from protein source
            if recipe.protein_source:
                protein = recipe.protein_source.lower()
                if "soy" in protein:
                    tags.append("Soy Protein")
                elif "milk" in protein or "dairy" in protein:
                    tags.append("Dairy Protein")
                elif "whey" in protein:
                    tags.append("Whey Protein")
                elif "pea" in protein:
                    tags.append("Pea Protein")
                elif "plant" in protein or "vegetable" in protein:
                    tags.append("Plant Protein")

            # Nutritional characteristic tags
            if recipe.proteines_100g:
                try:
                    protein_content = float(recipe.proteines_100g)
                    if protein_content >= 20:
                        tags.append("High Protein")
                    elif protein_content >= 15:
                        tags.append("Medium Protein")
                except (ValueError, TypeError):
                    pass

            if recipe.kcal_100g:
                try:
                    calorie_content = float(recipe.kcal_100g)
                    if calorie_content <= 100:
                        tags.append("Low Calorie")
                    elif calorie_content >= 400:
                        tags.append("High Calorie")
                except (ValueError, TypeError):
                    pass

            if recipe.lipides_100g:
                try:
                    fat_content = float(recipe.lipides_100g)
                    if fat_content <= 3:
                        tags.append("Low Fat")
                    elif fat_content >= 15:
                        tags.append("High Fat")
                except (ValueError, TypeError):
                    pass

            # Remove duplicates and sort
            tags = sorted(list(set(tags)))

            if tags:
                if dry_run:
                    self.stdout.write(
                        f"Recipe {recipe.product_id}: Would add tags {tags}"
                    )
                else:
                    recipe.tags = tags
                    recipe.save()
                    self.stdout.write(f"Recipe {recipe.product_id}: Added tags {tags}")
                updated_count += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN: Would update {updated_count} recipes with tags"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully updated {updated_count} recipes with tags"
                )
            )
