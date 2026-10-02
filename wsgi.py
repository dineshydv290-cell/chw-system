"""WSGI entry point for non-Vercel hosts (gunicorn, waitress, ...).

    gunicorn --bind 0.0.0.0:$PORT wsgi:app

On Vercel the entry point is api/index.py instead.
"""
from app import app

__all__ = ['app']
