from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import User


class Role(models.Model):
    """Model for user roles"""

    ROLE_CHOICES = [
        ("admin", "Administrator"),
        ("manager", "Manager"),
        ("viewer", "Viewer"),
        ("editor", "Editor"),
    ]

    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_name_display()

    class Meta:
        ordering = ["name"]


class UserProfile(models.Model):
    """Extended user profile model"""

    APPROVAL_STATUS_CHOICES = [
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default="pending",
        help_text="Admin approval status for new registrations",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_users",
        help_text="Admin who approved this user",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    registration_notes = models.TextField(
        blank=True, help_text="Notes from user during registration"
    )
    admin_notes = models.TextField(blank=True, help_text="Admin notes about this user")

    def __str__(self):
        return (
            f"{self.user.username} - {self.role} ({self.get_approval_status_display()})"
        )

    @property
    def is_approved(self):
        """Check if user is approved and active"""
        return self.approval_status == "approved" and self.is_active

    class Meta:
        ordering = ["user__username"]


class AdminNotification(models.Model):
    """Model for in-app admin notifications"""

    NOTIFICATION_TYPES = [
        ("new_registration", "New User Registration"),
        ("user_approved", "User Approved"),
        ("user_rejected", "User Rejected"),
        ("user_deleted", "User Deleted"),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    related_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications_about",
        help_text="User this notification is about",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_by = models.ManyToManyField(
        User,
        blank=True,
        related_name="read_notifications",
        help_text="Staff users who have read this notification",
    )

    def __str__(self):
        return f"{self.title} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def unread_count_for_staff(self):
        """Get count of staff users who haven't read this notification"""
        staff_users = User.objects.filter(is_staff=True, is_active=True)
        return staff_users.exclude(id__in=self.read_by.all()).count()

    class Meta:
        ordering = ["-created_at"]


# Signal to create UserProfile when User is created
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Create profile with pending approval status
        profile = UserProfile.objects.create(user=instance, approval_status="pending")

        # Set user as inactive until approved
        instance.is_active = False
        instance.save()

        # Create in-app notification for admins
        create_admin_notification(instance)

        # Send notification email to admins
        send_admin_notification_email(instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, "profile"):
        instance.profile.save()


def create_admin_notification(user):
    """Create in-app notification for admins about new user registration"""
    try:
        notification = AdminNotification.objects.create(
            title=f"New Registration: {user.username}",
            message=f"{user.first_name} {user.last_name} ({user.email}) has requested access to the system. "
            f"Registration notes: {user.profile.registration_notes or 'None provided'}",
            notification_type="new_registration",
            related_user=user,
        )
        return notification
    except Exception as e:
        # Log error but don't break the registration process
        print(f"Failed to create admin notification: {e}")
        return None


def send_admin_notification_email(user):
    """Send email notification to admins about new user registration"""
    try:
        # Get admin users
        admin_users = User.objects.filter(is_staff=True, is_active=True)
        admin_emails = [admin.email for admin in admin_users if admin.email]

        if not admin_emails:
            # Fallback to settings-defined admin email
            admin_emails = (
                [settings.DEFAULT_FROM_EMAIL]
                if hasattr(settings, "DEFAULT_FROM_EMAIL")
                else []
            )

        if admin_emails:
            subject = f"New User Registration Pending Approval - {user.username}"
            message = f"""
A new user has registered and requires approval:

Username: {user.username}
Email: {user.email}
First Name: {user.first_name}
Last Name: {user.last_name}
Registration Date: {user.date_joined.strftime('%Y-%m-%d %H:%M')}

To approve or reject this user, please log in to the admin panel:
{settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://your-site.com'}/admin/accounts/userprofile/

Best regards,
Bariatrix Recipe System
            """

            send_mail(
                subject=subject,
                message=message,
                from_email=(
                    settings.DEFAULT_FROM_EMAIL
                    if hasattr(settings, "DEFAULT_FROM_EMAIL")
                    else "noreply@bariatrix.com"
                ),
                recipient_list=admin_emails,
                fail_silently=True,  # Don't break registration if email fails
            )
    except Exception as e:
        # Log error but don't break the registration process
        print(f"Failed to send admin notification email: {e}")


def approve_user(user_profile, approved_by_user):
    """Approve a user registration"""
    user_profile.approval_status = "approved"
    user_profile.approved_by = approved_by_user
    user_profile.approved_at = timezone.now()
    user_profile.save()

    # Activate the user account
    user_profile.user.is_active = True
    user_profile.user.save()

    # Create in-app notification
    if approved_by_user:
        AdminNotification.objects.create(
            title=f"User Approved: {user_profile.user.username}",
            message=f"{user_profile.user.username} has been approved by {approved_by_user.username}",
            notification_type="user_approved",
            related_user=user_profile.user,
        )

    # Send approval email to user
    send_approval_email(user_profile.user)


def reject_user(user_profile, admin_notes=""):
    """Reject a user registration"""
    user_profile.approval_status = "rejected"
    user_profile.admin_notes = admin_notes
    user_profile.save()

    # Create in-app notification
    AdminNotification.objects.create(
        title=f"User Rejected: {user_profile.user.username}",
        message=f"{user_profile.user.username} has been rejected. Reason: {admin_notes or 'No reason provided'}",
        notification_type="user_rejected",
        related_user=user_profile.user,
    )

    # Send rejection email to user
    send_rejection_email(user_profile.user, admin_notes)


def send_approval_email(user):
    """Send approval email to user"""
    try:
        subject = "Your Bariatrix Recipe System Account Has Been Approved"
        message = f"""
Hello {user.first_name or user.username},

Great news! Your account for the Bariatrix Recipe System has been approved.

You can now log in and access all recipe search features:
{settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://your-site.com'}/accounts/login/

Welcome to Bariatrix Europe!

Best regards,
The Bariatrix Team
        """

        send_mail(
            subject=subject,
            message=message,
            from_email=(
                settings.DEFAULT_FROM_EMAIL
                if hasattr(settings, "DEFAULT_FROM_EMAIL")
                else "noreply@bariatrix.com"
            ),
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"Failed to send approval email: {e}")


def send_rejection_email(user, admin_notes=""):
    """Send rejection email to user"""
    try:
        subject = "Your Bariatrix Recipe System Account Registration"
        message = f"""
Hello {user.first_name or user.username},

Thank you for your interest in the Bariatrix Recipe System.

Unfortunately, we are unable to approve your account registration at this time.

{f"Additional information: {admin_notes}" if admin_notes else ""}

If you believe this is an error or have questions, please contact your administrator.

Best regards,
The Bariatrix Team
        """

        send_mail(
            subject=subject,
            message=message,
            from_email=(
                settings.DEFAULT_FROM_EMAIL
                if hasattr(settings, "DEFAULT_FROM_EMAIL")
                else "noreply@bariatrix.com"
            ),
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"Failed to send rejection email: {e}")
