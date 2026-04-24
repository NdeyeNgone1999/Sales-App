from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from service_commercial.common.accounts.models import Role


class Command(BaseCommand):
    help = "Create a demo superuser and assign admin role"

    def handle(self, *args, **options):
        # Create superuser if it doesn't exist
        username = "admin"
        email = "admin@bariatrix.com"
        password = "admin123"

        if not User.objects.filter(username=username).exists():
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name="Admin",
                last_name="User",
            )

            # Assign admin role
            try:
                admin_role = Role.objects.get(name="admin")
                user.profile.role = admin_role
                user.profile.department = "IT Administration"
                user.profile.save()

                self.stdout.write(
                    self.style.SUCCESS(f"Successfully created superuser: {username}")
                )
                self.stdout.write(self.style.SUCCESS(f"Email: {email}"))
                self.stdout.write(self.style.SUCCESS(f"Password: {password}"))
                self.stdout.write(self.style.SUCCESS(f"Role: {admin_role}"))
            except Role.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        "Admin role not found. Please run setup_roles command first."
                    )
                )
        else:
            self.stdout.write(self.style.WARNING(f"User {username} already exists."))
