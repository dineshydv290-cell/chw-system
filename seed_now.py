"""One-off helper: load schema.sql + seed.sql into the configured PostgreSQL database.

    python seed_now.py

It refuses to run if any table already holds rows, so it cannot overwrite data
you have already entered. Needs DATABASE_URL (your Neon connection string).
"""
import sys

import psycopg2

from config import raw_database_url

connection = psycopg2.connect(raw_database_url())
connection.autocommit = True
cursor = connection.cursor()

# --- Refuse to clobber existing data -------------------------------------
cursor.execute(
    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
)
tables = [row[0] for row in cursor.fetchall()]
existing = 0
for table in tables:
    cursor.execute('SELECT COUNT(*) FROM public."%s"' % table.replace('"', '""'))
    existing += cursor.fetchone()[0]

if existing:
    print("STOPPED: the database already holds %d rows." % existing)
    print("Nothing was changed. Clear it yourself if you want a clean reload.")
    sys.exit(1)

print("Database is empty -- loading schema.sql and seed.sql.")

for path in ("schema.sql", "seed.sql"):
    with open(path, encoding="utf-8") as handle:
        cursor.execute(handle.read())
    print("  applied %s" % path)

cursor.execute(
    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
)
total = 0
print("\nrow counts")
for (table,) in cursor.fetchall():
    cursor.execute('SELECT COUNT(*) FROM public."%s"' % table)
    count = cursor.fetchone()[0]
    total += count
    print("   %-26s %d" % (table, count))
print("\n%d rows loaded" % total)

connection.close()
print("\nDone. Next:  python reset_passwords.py")
