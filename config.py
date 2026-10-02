import os


def _normalise_database_url(url):
    """Turn whatever connection string the host hands over into one SQLAlchemy
    can use with the psycopg2 driver.

    Neon (and Vercel's Neon integration) give out ``postgresql://...`` or the
    older ``postgres://...``. SQLAlchemy 2.x rejects the ``postgres://`` alias
    and would pick the driver by default for the other, so both are rewritten
    to the explicit ``postgresql+psycopg2://`` form. Neon requires TLS, so
    ``sslmode=require`` is added when the string does not already say so.
    """
    if not url:
        return url
    url = url.strip()
    for prefix in ('postgres://', 'postgresql://'):
        if url.startswith(prefix):
            url = 'postgresql+psycopg2://' + url[len(prefix):]
            break

    if url.startswith('postgresql') and 'sslmode=' not in url:
        # Local Postgres rarely has TLS; only force it for remote hosts.
        host_part = url.split('@')[-1]
        is_local = host_part.startswith(('localhost', '127.0.0.1', '[::1]'))
        if not is_local:
            url += ('&' if '?' in url else '?') + 'sslmode=require'
    return url


def _database_url_from_env():
    """First connection string found among the variables Vercel/Neon set."""
    for name in ('DATABASE_URL', 'POSTGRES_URL', 'POSTGRES_PRISMA_URL', 'NEON_DATABASE_URL'):
        value = os.environ.get(name)
        if value:
            return _normalise_database_url(value)
    # Local development fallback. Override with DATABASE_URL.
    return 'postgresql+psycopg2://postgres:postgres@localhost:5432/chw_system'


ON_VERCEL = bool(os.environ.get('VERCEL'))


class Config:
    # Sessions are signed with this key. It is read from the environment so the
    # real value never has to live in version control; the fallback is a
    # development convenience only.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-change-me')

    SQLALCHEMY_DATABASE_URI = _database_url_from_env()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Serverless-friendly pooling: every function instance serves one request
    # at a time, so a big pool only wastes Neon connections. pool_pre_ping
    # revives a connection that Neon closed while the compute was suspended.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 240,
        'pool_size': 1,
        'max_overflow': 4,
        'connect_args': {
            'connect_timeout': 15,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5,
        },
    }

    # --- Session cookie hardening ---
    # HttpOnly keeps the cookie away from JavaScript; SameSite=Lax blocks it on
    # cross-site form posts. Secure is switched on automatically on Vercel
    # (always HTTPS) and can be forced elsewhere with HTTPS_ONLY=1.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = ON_VERCEL or os.environ.get('HTTPS_ONLY', '0') == '1'

    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    # Refuse oversized form posts outright (Vercel itself caps bodies at 4.5 MB).
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB

    # Minimum password length enforced at registration.
    MIN_PASSWORD_LENGTH = 8


# The literal used when SECRET_KEY is unset. It is a published string, so
# anyone can forge a session cookie signed with it. Fine on a laptop, unsafe
# on a host other people can reach, hence the startup warning below.
_DEV_SECRET_KEY = 'dev-only-change-me'


def using_dev_secret_key():
    """True when the app is running on the throwaway development key."""
    return Config.SECRET_KEY == _DEV_SECRET_KEY


def raw_database_url():
    """Connection string in the plain form psycopg2.connect() understands.

    The maintenance scripts talk to the database through psycopg2 directly, and
    libpq does not know the ``+psycopg2`` driver suffix SQLAlchemy uses.
    """
    return Config.SQLALCHEMY_DATABASE_URI.replace('postgresql+psycopg2://', 'postgresql://', 1)


def startup_warnings():
    """Report settings that are fine locally but unsafe in public hosting."""
    notes = []
    if using_dev_secret_key():
        notes.append(
            "SECRET_KEY is the built-in development default. Sessions can be "
            "forged by anyone who knows it. Set a real SECRET_KEY before "
            "deploying anywhere public."
        )
    return notes
