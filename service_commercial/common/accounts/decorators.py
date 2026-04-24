from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


def role_required(allowed_roles=None):
    """
    Decorator to restrict access to users with specific roles.

    Usage:
    @role_required(['admin', 'manager'])
    def my_view(request):
        ...
    """
    if allowed_roles is None:
        allowed_roles = []

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user

            # Superuser has access to everything
            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Check if user has profile and role
            if not hasattr(user, "profile") or not user.profile.role:
                messages.error(
                    request,
                    "You do not have permission to access this page. No role assigned.",
                )
                return redirect("pages:home")

            # Check if user's role is in allowed roles
            if user.profile.role.name not in allowed_roles:
                messages.error(
                    request, "You do not have permission to access this page."
                )
                return redirect("pages:home")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def admin_required(view_func):
    """Decorator to restrict access to admin users only"""
    return role_required(["admin"])(view_func)


def manager_required(view_func):
    """Decorator to restrict access to managers and admins"""
    return role_required(["admin", "manager"])(view_func)


def editor_required(view_func):
    """Decorator to restrict access to editors, managers, and admins"""
    return role_required(["admin", "manager", "editor"])(view_func)


def check_user_role(user, required_roles):
    """
    Helper function to check if user has required role

    Args:
        user: User object
        required_roles: List of role names

    Returns:
        bool: True if user has required role, False otherwise
    """
    if user.is_superuser:
        return True

    if not hasattr(user, "profile") or not user.profile.role:
        return False

    return user.profile.role.name in required_roles


def get_user_role(user):
    """
    Helper function to get user's role name

    Args:
        user: User object

    Returns:
        str: Role name or None
    """
    if hasattr(user, "profile") and user.profile.role:
        return user.profile.role.name
    return None
