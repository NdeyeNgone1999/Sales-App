from .decorators import get_user_role, check_user_role
from .models import AdminNotification, UserProfile


def user_role_context(request):
    """
    Context processor to add user role information to all templates
    """
    context = {
        "user_role": None,
        "is_admin": False,
        "is_manager": False,
        "is_editor": False,
        "is_viewer": False,
        "unread_notifications_count": 0,
        "pending_registrations_count": 0,
    }

    if request.user.is_authenticated:
        user_role = get_user_role(request.user)
        context["user_role"] = user_role

        # Set role flags
        context["is_admin"] = (
            check_user_role(request.user, ["admin"]) or request.user.is_superuser
        )
        context["is_manager"] = (
            check_user_role(request.user, ["admin", "manager"])
            or request.user.is_superuser
        )
        context["is_editor"] = (
            check_user_role(request.user, ["admin", "manager", "editor"])
            or request.user.is_superuser
        )
        context["is_viewer"] = (
            check_user_role(request.user, ["admin", "manager", "editor", "viewer"])
            or request.user.is_superuser
        )

        # Add notification counts for staff users
        if request.user.is_staff:
            # Count unread notifications
            unread_notifications = AdminNotification.objects.exclude(
                read_by=request.user
            ).filter(is_read=False)
            context["unread_notifications_count"] = unread_notifications.count()

            # Count pending registrations
            pending_registrations = UserProfile.objects.filter(
                approval_status="pending"
            )
            context["pending_registrations_count"] = pending_registrations.count()

    return context
