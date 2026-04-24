from django.db.backends.sqlite3._functions import register as register_functions
from django.db.backends.sqlite3.base import (
    Database,
    DatabaseWrapper as SQLiteDatabaseWrapper,
)
from django.utils.asyncio import async_unsafe


class DatabaseWrapper(SQLiteDatabaseWrapper):
    @async_unsafe
    def get_new_connection(self, conn_params):
        conn = Database.connect(**conn_params)
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        register_functions(conn)
        conn.execute("PRAGMA legacy_alter_table = OFF")
        return conn
