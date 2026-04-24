from django.core.management.base import BaseCommand
from service_commercial.common.accounts.models import Role


class Command(BaseCommand):
    help = "Create initial roles for the application"

    def handle(self, *args, **options):
        roles_data = [
            {
                "name": "admin",
                "description": "Administrator with full access to all features including user management, role management, and system configuration.",
            },
            {
                "name": "manager",
                "description": "Manager who can manage content and view reports. Limited administrative privileges.",
            },
            {
                "name": "editor",
                "description": "Editor who can create, edit, and manage content. Cannot access user management features.",
            },
            {
                "name": "viewer",
                "description": "Viewer with read-only access to content. Cannot make any changes to the system.",
            },
        ]

        created_count = 0
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_data["name"],
                defaults={"description": role_data["description"]},
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully created role: {role.get_name_display()}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Role already exists: {role.get_name_display()}"
                    )
                )

        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"\nCreated {created_count} new roles.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("\nAll roles already exist."))
