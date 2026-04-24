from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from service_commercial.common.accounts.models import (
    UserProfile,
    approve_user,
    reject_user,
)


class Command(BaseCommand):
    help = "Manage user approval status"

    def add_arguments(self, parser):
        parser.add_argument(
            "action", choices=["list", "approve", "reject"], help="Action to perform"
        )
        parser.add_argument(
            "--username", type=str, help="Username for approve/reject actions"
        )
        parser.add_argument(
            "--admin-username", type=str, help="Admin username performing the action"
        )
        parser.add_argument(
            "--notes", type=str, default="", help="Admin notes for rejection"
        )

    def handle(self, *args, **options):
        action = options["action"]

        if action == "list":
            self.list_pending_users()
        elif action in ["approve", "reject"]:
            if not options["username"]:
                self.stdout.write(
                    self.style.ERROR("Username is required for approve/reject actions")
                )
                return

            admin_user = None
            if options["admin_username"]:
                try:
                    admin_user = User.objects.get(username=options["admin_username"])
                except User.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Admin user '{options['admin_username']}' not found"
                        )
                    )
                    return

            if action == "approve":
                self.approve_user(options["username"], admin_user)
            else:
                self.reject_user(options["username"], options["notes"], admin_user)

    def list_pending_users(self):
        """List all users pending approval"""
        pending_profiles = UserProfile.objects.filter(approval_status="pending")

        if not pending_profiles:
            self.stdout.write(self.style.SUCCESS("No users pending approval"))
            return

        self.stdout.write(
            self.style.WARNING(f"Users pending approval ({pending_profiles.count()}):")
        )
        self.stdout.write("")

        for profile in pending_profiles:
            user = profile.user
            self.stdout.write(f"Username: {user.username}")
            self.stdout.write(f"  Name: {user.first_name} {user.last_name}")
            self.stdout.write(f"  Email: {user.email}")
            self.stdout.write(f"  Department: {profile.department or 'Not specified'}")
            self.stdout.write(f"  Role: {profile.role or 'Not specified'}")
            self.stdout.write(
                f"  Registered: {user.date_joined.strftime('%Y-%m-%d %H:%M')}"
            )
            if profile.registration_notes:
                self.stdout.write(f"  Notes: {profile.registration_notes}")
            self.stdout.write("")

    def approve_user(self, username, admin_user):
        """Approve a user"""
        try:
            user = User.objects.get(username=username)
            profile = user.profile

            if profile.approval_status != "pending":
                self.stdout.write(
                    self.style.WARNING(
                        f"User '{username}' is not pending approval (status: {profile.approval_status})"
                    )
                )
                return

            approve_user(profile, admin_user)
            self.stdout.write(
                self.style.SUCCESS(f"Successfully approved user '{username}'")
            )

        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{username}' not found"))

    def reject_user(self, username, notes, admin_user):
        """Reject a user"""
        try:
            user = User.objects.get(username=username)
            profile = user.profile

            if profile.approval_status != "pending":
                self.stdout.write(
                    self.style.WARNING(
                        f"User '{username}' is not pending approval (status: {profile.approval_status})"
                    )
                )
                return

            reject_user(profile, notes)
            self.stdout.write(
                self.style.SUCCESS(f"Successfully rejected user '{username}'")
            )

        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{username}' not found"))
