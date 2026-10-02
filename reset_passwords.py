"""One-off utility: give the seeded accounts a usable password.

seed.sql cannot generate a werkzeug hash, so the rows it inserts carry the
literal string 'SET_VIA_SEED_ROUTE' in password_hash. That is not a hash:
check_password_hash() returns False for it against any input, so those
accounts reject every password and cannot be signed into. add_admin.py fixes
the admin account but refuses to run once an admin exists, which leaves the
supervisor and CHW rows permanently unusable.

This script replaces the placeholder on the seeded accounts with a real hash.
It changes nothing else -- not names, roles, phone numbers or active flags --
and leaves any account that already has a working password untouched.

The password is read interactively and is never stored in this file.

Run it yourself so the password prompt reaches you:
    python reset_passwords.py
"""
import getpass
import sys

import psycopg2
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config, raw_database_url

# The accounts seed.sql creates. dheeraj_k and anyone else who registered
# through the app is deliberately absent: those rows hold a real hash already
# and must not be disturbed.
SEEDED_ACCOUNTS = ('admin', 'healthworker1', 'supervisor1')

# The exact placeholder seed.sql writes. Matching on it is what makes the
# script safe to re-run: an account whose password has since been set through
# the app has a real hash here and is skipped.
PLACEHOLDER = 'SET_VIA_SEED_ROUTE'


def prompt_for_password():
    """Ask for one password, twice, and return it as a hash.

    Returns None if the user cancels or the two entries disagree, so the caller
    can exit without touching the database.
    """
    print(f"Setting one password for: {', '.join(SEEDED_ACCOUNTS)}")
    print("It is hashed before storage and is not written to any file.")
    try:
        password = getpass.getpass("  new password:  ")
        if not password:
            print("\nEmpty password. Nothing was changed.")
            return None
        if len(password) < Config.MIN_PASSWORD_LENGTH:
            print(f"\nPassword must be at least "
                  f"{Config.MIN_PASSWORD_LENGTH} characters. Nothing was changed.")
            return None
        if password != getpass.getpass("  confirm:       "):
            print("\nPasswords did not match. Nothing was changed.")
            return None
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled. Nothing was changed.")
        return None

    return generate_password_hash(password)


def main():
    print("Checking seeded accounts in the configured database.")

    cn = psycopg2.connect(raw_database_url())
    try:
        placeholders = ', '.join(['%s'] * len(SEEDED_ACCOUNTS))

        with cn.cursor() as cu:
            cu.execute(
                f"SELECT username, password_hash FROM users "
                f"WHERE username IN ({placeholders})",
                SEEDED_ACCOUNTS,
            )
            seeded = dict(cu.fetchall())

        # Report the plan before asking for anything, so the user can see that
        # an account already carrying a real password is going to be skipped
        # rather than silently overwritten.
        needs_reset, already_fine, missing = [], [], []
        for username in SEEDED_ACCOUNTS:
            if username not in seeded:
                missing.append(username)
            elif seeded[username] == PLACEHOLDER:
                needs_reset.append(username)
            else:
                already_fine.append(username)

        for username in needs_reset:
            print(f"  will reset   {username}")
        for username in already_fine:
            print(f"  skip (set)   {username}")
        for username in missing:
            print(f"  NOT FOUND    {username}")

        if missing:
            print("\nThose accounts do not exist, so this is probably not a "
                  "seeded database. Nothing was changed.")
            return 1

        if not needs_reset:
            print("\nEvery seeded account already has a real password. "
                  "Nothing was changed.")
            return 0

        password_hash = prompt_for_password()
        if password_hash is None:
            return 1

        # Prove the hash verifies before writing it. A hash that does not
        # round-trip would lock the account out, and the whole point of this
        # script is to make these accounts usable.
        try:
            verify = getpass.getpass("\n  re-enter to verify before saving: ")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled. Nothing was changed.")
            return 1
        if not check_password_hash(password_hash, verify):
            print("\nEntries did not match. Nothing was changed.")
            return 1

        with cn.cursor() as cu:
            targets = ', '.join(['%s'] * len(needs_reset))
            cu.execute(
                f"UPDATE users SET password_hash = %s WHERE username IN ({targets})",
                [password_hash] + needs_reset,
            )
            changed = cu.rowcount
        cn.commit()

        # Confirm from the database rather than trusting the update: the point
        # of the script is that these accounts now authenticate.
        with cn.cursor() as cu:
            cu.execute(
                f"SELECT username, role, is_active, "
                f"(password_hash = %s) AS still_placeholder "
                f"FROM users WHERE username IN ({placeholders}) ORDER BY id",
                [PLACEHOLDER] + list(SEEDED_ACCOUNTS),
            )
            rows = cu.fetchall()

        print(f"\npassword_hash updated on {changed} account(s).")
        for username, role, active, still_placeholder in rows:
            state = 'STILL BROKEN' if still_placeholder else 'login enabled'
            print(f"  {username:16} {role:14} active={active}  {state}")

        print("\nDone. Sign in at http://127.0.0.1:5000/login as any of "
              f"{', '.join(SEEDED_ACCOUNTS)} using the password you just set.")
    finally:
        cn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())