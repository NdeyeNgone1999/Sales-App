from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.html import format_html
from .models import Role, UserProfile, AdminNotification, approve_user, reject_user


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin interface for Role model"""

    list_display = ["name", "description", "created_at", "updated_at"]
    list_filter = ["name", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile"""

    model = UserProfile
    fk_name = "user"  # Specify which ForeignKey to use
    can_delete = False
    verbose_name_plural = "Profile"
    fields = [
        "role",
        "phone_number",
        "department",
        "is_active",
        "approval_status",
        "approved_by",
        "approved_at",
        "registration_notes",
        "admin_notes",
    ]
    readonly_fields = ["approved_at"]


class CustomUserAdmin(UserAdmin):
    """Custom User admin with profile inline"""

    inlines = (UserProfileInline,)
    list_display = [
        "username",
        "email",
        "first_name",
        "last_name",
        "get_role",
        "get_approval_status",
        "is_active",
        "date_joined",
    ]
    list_filter = [
        "is_active",
        "is_staff",
        "date_joined",
        "profile__role",
        "profile__approval_status",
    ]
    search_fields = ["username", "first_name", "last_name", "email"]

    def get_role(self, obj):
        """Get user role for admin display"""
        return (
            obj.profile.role
            if hasattr(obj, "profile") and obj.profile.role
            else "No Role"
        )

    def get_approval_status(self, obj):
        """Get user approval status for admin display"""
        if hasattr(obj, "profile"):
            status = obj.profile.get_approval_status_display()
            if obj.profile.approval_status == "pending":
                return f"🟡 {status}"
            elif obj.profile.approval_status == "approved":
                return f"🟢 {status}"
            elif obj.profile.approval_status == "rejected":
                return f"🔴 {status}"
        return "❓ Unknown"

    get_role.short_description = "Role"
    get_approval_status.short_description = "Approval Status"


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface for UserProfile model"""

    list_display = [
        "user",
        "get_full_name",
        "get_email",
        "role",
        "department",
        "get_approval_status_display",
        "is_active",
        "created_at",
    ]
    list_filter = ["approval_status", "role", "is_active", "department", "created_at"]
    search_fields = [
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "department",
    ]
    readonly_fields = ["created_at", "updated_at", "approved_at", "get_user_info"]

    fieldsets = (
        (
            "User Information",
            {"fields": ("get_user_info", "role", "phone_number", "department")},
        ),
        (
            "Approval Status",
            {"fields": ("approval_status", "approved_by", "approved_at")},
        ),
        ("Notes", {"fields": ("registration_notes", "admin_notes")}),
        ("Settings", {"fields": ("is_active",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    actions = ["approve_users", "reject_users"]

    def get_full_name(self, obj):
        """Get user's full name"""
        return (
            f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
        )

    def get_email(self, obj):
        """Get user's email"""
        return obj.user.email

    def get_user_info(self, obj):
        """Display comprehensive user information"""
        return format_html(
            "<strong>Username:</strong> {}<br>"
            "<strong>Email:</strong> {}<br>"
            "<strong>Name:</strong> {} {}<br>"
            "<strong>Date Joined:</strong> {}",
            obj.user.username,
            obj.user.email,
            obj.user.first_name,
            obj.user.last_name,
            obj.user.date_joined.strftime("%Y-%m-%d %H:%M"),
        )

    def get_approval_status_display(self, obj):
        """Display approval status with icons"""
        if obj.approval_status == "pending":
            return format_html('<span style="color: orange;">🟡 Pending</span>')
        elif obj.approval_status == "approved":
            return format_html('<span style="color: green;">🟢 Approved</span>')
        elif obj.approval_status == "rejected":
            return format_html('<span style="color: red;">🔴 Rejected</span>')
        return obj.get_approval_status_display()

    def approve_users(self, request, queryset):
        """Admin action to approve selected users"""
        approved_count = 0
        for profile in queryset.filter(approval_status="pending"):
            approve_user(profile, request.user)
            approved_count += 1

        self.message_user(request, f"Successfully approved {approved_count} user(s).")

    def reject_users(self, request, queryset):
        """Admin action to reject selected users"""
        rejected_count = 0
        for profile in queryset.filter(approval_status="pending"):
            reject_user(profile, "Rejected by admin")
            rejected_count += 1

        self.message_user(request, f"Successfully rejected {rejected_count} user(s).")

    get_full_name.short_description = "Full Name"
    get_email.short_description = "Email"
    get_user_info.short_description = "User Information"
    get_approval_status_display.short_description = "Status"
    approve_users.short_description = "✅ Approve selected users"
    reject_users.short_description = "❌ Reject selected users"

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return (
            super().get_queryset(request).select_related("user", "role", "approved_by")
        )


@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    """Admin interface for AdminNotification model"""

    list_display = [
        "title",
        "get_related_user_info",
        "notification_type",
        "created_at",
        "get_read_status",
    ]
    list_filter = ["notification_type", "created_at", "is_read"]
    search_fields = [
        "title",
        "message",
        "related_user__username",
        "related_user__email",
    ]
    readonly_fields = ["created_at"]
    actions = ["mark_as_read", "approve_related_users", "reject_related_users"]

    def get_related_user_info(self, obj):
        """Display related user information"""
        user = obj.related_user
        return format_html(
            "<strong>{}</strong><br>" "<small>{} | {}</small>",
            user.username,
            user.email,
            f"{user.first_name} {user.last_name}".strip() or "No name",
        )

    def get_read_status(self, obj):
        """Display read status"""
        if obj.is_read:
            return format_html('<span style="color: green;">✅ Read</span>')
        else:
            return format_html('<span style="color: orange;">🟡 Unread</span>')

    def mark_as_read(self, request, queryset):
        """Mark notifications as read"""
        for notification in queryset:
            notification.read_by.add(request.user)
            if not notification.is_read:
                notification.is_read = True
                notification.save()
        self.message_user(
            request, f"Marked {queryset.count()} notification(s) as read."
        )

    def approve_related_users(self, request, queryset):
        """Approve users related to selected notifications"""
        approved_count = 0
        for notification in queryset.filter(notification_type="new_registration"):
            user = notification.related_user
            if hasattr(user, "profile") and user.profile.approval_status == "pending":
                approve_user(user.profile, request.user)
                notification.read_by.add(request.user)
                approved_count += 1

        self.message_user(
            request,
            f"Successfully approved {approved_count} user(s) and marked notifications as read.",
        )

    def reject_related_users(self, request, queryset):
        """Reject users related to selected notifications"""
        rejected_count = 0
        for notification in queryset.filter(notification_type="new_registration"):
            user = notification.related_user
            if hasattr(user, "profile") and user.profile.approval_status == "pending":
                reject_user(user.profile, "Rejected via notification")
                notification.read_by.add(request.user)
                rejected_count += 1

        self.message_user(
            request,
            f"Successfully rejected {rejected_count} user(s) and marked notifications as read.",
        )

    get_related_user_info.short_description = "User"
    get_read_status.short_description = "Status"
    mark_as_read.short_description = "📖 Mark as read"
    approve_related_users.short_description = "✅ Approve related users"
    reject_related_users.short_description = "❌ Reject related users"

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related("related_user")
