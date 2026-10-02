"""One-off utility: create the default admin account in the configured PostgreSQL database.

Inserts exactly one row and touches no existing data. The password is read
interactively and is never stored in this file.

Run it yourself so the password prompt reaches you:
    python add_admin.py
"""
import getpass
import sys

import psycopg2
from werkzeug.security import generate_password_hash

from config import raw_database_url


def main():
    print("Creating the default 'admin' account in the configured database.")
    print("Enter the password you want for it (it is hashed, not stored).")
    try:
        password = getpass.getpass("  admin password: ")
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled. Nothing was changed.")
        return 1

    if not password:
        print("Empty password. Nothing was changed.")
        return 1
    if len(password) < 8:
        print("Password must be at least 8 characters. Nothing was changed.")
        return 1
    if password != getpass.getpass("  confirm:        "):
        print("Passwords did not match. Nothing was changed.")
        return 1

    # Optional. An admin can still fill this in later from User Management, but
    # collecting it here saves an account being born with a blank contact field.
    phone = input("  contact number (optional): ").strip()
    if phone and (not phone.isdigit() or len(phone) != 10):
        print("Contact number must be exactly 10 digits, or blank. Nothing was changed.")
        return 1
    phone = phone or None

    cn = psycopg2.connect(raw_database_url())
    try:
        with cn.cursor() as cu:
            # Refuse rather than collide if an admin already exists.
            cu.execute("SELECT id FROM users WHERE username = %s", ('admin',))
            if cu.fetchone():
                print("A user named 'admin' already exists. Nothing was changed.")
                return 1

            cu.execute("SELECT COUNT(*) FROM users")
            before = cu.fetchone()[0]

            cu.execute(
                "INSERT INTO users "
                "(username, password_hash, full_name, role, phone, is_active, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, NOW())",
                ('admin', generate_password_hash(password),
                 'System Administrator', 'admin', phone, True),
            )
        cn.commit()

        with cn.cursor() as cu:
            cu.execute("SELECT COUNT(*) FROM users")
            after = cu.fetchone()[0]
            cu.execute("SELECT username, role, is_active FROM users ORDER BY id")
            rows = cu.fetchall()

        print(f"\nusers before: {before} -> after: {after}")
        for username, role, active in rows:
            print(f"  {username:16} {role:14} active={active}")
        print("\nDone. Log in at http://127.0.0.1:5000/login as 'admin'.")
    finally:
        cn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
