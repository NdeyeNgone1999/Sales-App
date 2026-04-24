from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # Authentication URLs
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    # Profile URLs
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.edit_profile_view, name="edit_profile"),
    # User management URLs (admin only)
    path("users/", views.user_list_view, name="user_list"),
    path("users/<int:user_id>/", views.user_detail_view, name="user_detail"),
    path("users/<int:user_id>/edit/", views.edit_user_view, name="edit_user"),
    path(
        "users/<int:user_id>/toggle-status/",
        views.toggle_user_status_view,
        name="toggle_user_status",
    ),
    path(
        "users/<int:user_id>/delete/",
        views.delete_user_view,
        name="delete_user",
    ),
    path(
        "users/<int:user_id>/change-password/",
        views.change_password_view,
        name="change_password",
    ),
    # Role management URLs (admin only)
    path("roles/", views.role_list_view, name="role_list"),
    path("roles/create/", views.create_role_view, name="create_role"),
    path("roles/<int:role_id>/edit/", views.edit_role_view, name="edit_role"),
    path("roles/<int:role_id>/delete/", views.delete_role_view, name="delete_role"),
    # Documentation
    path("guide/", views.user_guide_view, name="user_guide"),
    # Notifications
    path("notifications/", views.notifications_view, name="notifications"),
]
