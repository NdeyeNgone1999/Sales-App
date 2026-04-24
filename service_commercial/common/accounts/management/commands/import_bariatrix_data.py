import json
import sqlite3
from pathlib import Path

from django.contrib.auth.models import User
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models.signals import post_save
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from service_commercial.common.accounts.models import (
    AdminNotification,
    Role,
    UserProfile,
    create_user_profile,
    save_user_profile,
)
from service_commercial.client_analytics.models import Dataset
from service_commercial.fiches_techniques.pages.models import Recipe


class Command(BaseCommand):
    help = (
        "Importe les données Bariatrix (rôles, utilisateurs, profils, "
        "notifications et recettes) dans la base unifiée de Sales-App."
    )

    help = (
        "Importe les donnees Bariatrix (roles, utilisateurs, profils, "
        "notifications et recettes) dans la base unifiee de Service Commercial."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-db",
            dest="source_db",
            default=None,
            help="Chemin vers la base SQLite Bariatrix à importer.",
        )

    def handle(self, *args, **options):
        source_db = self._resolve_source_db(options.get("source_db"))
        if not source_db.exists():
            raise CommandError(f"Base source introuvable: {source_db}")

        self.stdout.write(f"Import depuis {source_db}")

        post_save.disconnect(create_user_profile, sender=User)
        post_save.disconnect(save_user_profile, sender=User)

        try:
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA journal_mode=MEMORY")
                cursor.execute("PRAGMA synchronous=OFF")
            summary = self._import_data(source_db)
        finally:
            post_save.connect(create_user_profile, sender=User)
            post_save.connect(save_user_profile, sender=User)

        self.stdout.write(
            self.style.SUCCESS(
                "Import terminé "
                f"(roles={summary['roles']}, users={summary['users']}, "
                f"profiles={summary['profiles']}, notifications={summary['notifications']}, "
                f"datasets={summary['datasets']}, "
                f"recipes={summary['recipes']})"
            )
        )

    def _resolve_source_db(self, explicit_path):
        if explicit_path:
            return Path(explicit_path).resolve()
        raise CommandError(
            "Aucune base source par defaut n'est configuree. "
            "Utilise --source-db pour preciser un fichier SQLite a importer."
        )

    @transaction.atomic
    def _import_data(self, source_db):
        conn = sqlite3.connect(source_db)
        conn.row_factory = sqlite3.Row

        summary = {
            "roles": 0,
            "users": 0,
            "profiles": 0,
            "notifications": 0,
            "datasets": 0,
            "recipes": 0,
        }

        try:
            role_rows = self._fetch_rows(conn, "accounts_role")
            role_by_old_id = {}
            for row in role_rows:
                role, _ = Role.objects.update_or_create(
                    name=row["name"],
                    defaults={"description": row["description"] or ""},
                )
                self._restore_timestamps(
                    Role,
                    role.pk,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                role_by_old_id[row["id"]] = role
                summary["roles"] += 1

            user_rows = self._fetch_rows(conn, "auth_user")
            user_by_old_id = {}
            for row in user_rows:
                user, _ = User.objects.update_or_create(
                    username=row["username"],
                    defaults={
                        "password": row["password"],
                        "first_name": row["first_name"],
                        "last_name": row["last_name"],
                        "email": row["email"],
                        "is_staff": bool(row["is_staff"]),
                        "is_active": bool(row["is_active"]),
                        "is_superuser": bool(row["is_superuser"]),
                        "last_login": self._parse_datetime(row["last_login"]),
                        "date_joined": self._parse_datetime(row["date_joined"]),
                    },
                )
                user_by_old_id[row["id"]] = user
                summary["users"] += 1

            profile_rows = self._fetch_rows(conn, "accounts_userprofile")
            for row in profile_rows:
                user = user_by_old_id.get(row["user_id"])
                if not user:
                    continue

                profile, _ = UserProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "role": role_by_old_id.get(row["role_id"]),
                        "phone_number": row["phone_number"] or "",
                        "department": row["department"] or "",
                        "is_active": bool(row["is_active"]),
                        "approval_status": row["approval_status"] or "pending",
                        "approved_by": user_by_old_id.get(row["approved_by_id"]),
                        "approved_at": self._parse_datetime(row["approved_at"]),
                        "registration_notes": row["registration_notes"] or "",
                        "admin_notes": row["admin_notes"] or "",
                    },
                )
                self._restore_timestamps(
                    UserProfile,
                    profile.pk,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                summary["profiles"] += 1

            notification_rows = self._fetch_rows(conn, "accounts_adminnotification")
            notification_by_old_id = {}
            for row in notification_rows:
                related_user = user_by_old_id.get(row["related_user_id"])
                if not related_user:
                    continue

                notification, _ = AdminNotification.objects.get_or_create(
                    title=row["title"],
                    related_user=related_user,
                    created_at=self._parse_datetime(row["created_at"]),
                    defaults={
                        "message": row["message"],
                        "notification_type": row["notification_type"],
                        "is_read": bool(row["is_read"]),
                    },
                )
                AdminNotification.objects.filter(pk=notification.pk).update(
                    message=row["message"],
                    notification_type=row["notification_type"],
                    is_read=bool(row["is_read"]),
                    created_at=self._parse_datetime(row["created_at"]),
                )
                notification_by_old_id[row["id"]] = notification
                summary["notifications"] += 1

            read_by_rows = self._fetch_rows(conn, "accounts_adminnotification_read_by")
            for row in read_by_rows:
                notification = notification_by_old_id.get(row["adminnotification_id"])
                user = user_by_old_id.get(row["user_id"])
                if notification and user:
                    notification.read_by.add(user)

            dataset_rows = self._fetch_rows(conn, "client_analytics_dataset")
            for row in dataset_rows:
                dataset, _ = Dataset.objects.update_or_create(
                    pk=row["id"],
                    defaults={
                        "name": row["name"],
                        "source_type": row["source_type"] or "upload",
                        "file": row["file"] or "",
                        "processing_status": row["processing_status"] or "done",
                    },
                )
                self._restore_timestamps(
                    Dataset,
                    dataset.pk,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                summary["datasets"] += 1

            recipe_rows = self._fetch_rows(conn, "pages_recipe")
            recipe_fields = {
                field.name: field
                for field in Recipe._meta.fields
                if field.name not in {"id", "product_id", "created_at", "updated_at"}
            }
            for row in recipe_rows:
                defaults = {
                    field_name: self._normalize_recipe_value(field_name, row[field_name])
                    for field_name in recipe_fields
                }
                recipe, _ = Recipe.objects.update_or_create(
                    product_id=row["product_id"],
                    defaults=defaults,
                )
                self._restore_timestamps(
                    Recipe,
                    recipe.pk,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                summary["recipes"] += 1
        finally:
            conn.close()

        return summary

    def _fetch_rows(self, conn, table_name):
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT * FROM {table_name}")
        except sqlite3.OperationalError as exc:
            raise CommandError(f"Table absente dans la base source: {table_name}") from exc
        return cursor.fetchall()

    def _parse_datetime(self, value):
        if not value:
            return None
        if hasattr(value, "tzinfo"):
            parsed = value
        else:
            parsed = parse_datetime(value) or value
        if hasattr(parsed, "tzinfo") and settings.USE_TZ and timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    def _normalize_recipe_value(self, field_name, value):
        if field_name in {"ingredients_list", "tags"}:
            if not value:
                return []
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return []
        return value

    def _restore_timestamps(self, model, pk, created_at=None, updated_at=None):
        updates = {}
        field_names = {field.name for field in model._meta.fields}

        if created_at is not None and "created_at" in field_names:
            updates["created_at"] = self._parse_datetime(created_at)
        if updated_at is not None and "updated_at" in field_names:
            updates["updated_at"] = self._parse_datetime(updated_at)

        if updates:
            model.objects.filter(pk=pk).update(**updates)
