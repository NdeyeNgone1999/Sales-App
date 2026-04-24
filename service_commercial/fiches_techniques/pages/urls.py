from django.urls import path
from . import views

app_name = "pages"

urlpatterns = [
    path("", views.home, name="home"),
    path("search-results/", views.search_results, name="search_results"),
    path("recipe/<int:recipe_id>/", views.recipe_detail, name="recipe_detail"),
    path("recipe/<int:recipe_id>/delete/", views.delete_recipe, name="delete_recipe"),
    path(
        "recipe/<int:recipe_id>/export-word/",
        views.export_recipe_word,
        name="export_recipe_word",
    ),
    path("update-recipes/", views.update_recipes_form, name="update_recipes_form"),
    path("update-recipes/process/", views.update_recipes, name="update_recipes"),
    path("recipe-summary/", views.recipe_summary, name="recipe_summary"),
    path("progress/<str:task_id>/", views.check_progress, name="check_progress"),
    path("api/tags/", views.get_tags, name="get_tags"),
]
