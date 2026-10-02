"""Vercel serverless entry point.

Vercel's Python runtime looks for a WSGI callable named ``app`` in this file.
The real application lives in ../app.py, so the project root is added to the
import path first. Templates and static files are resolved relative to app.py,
which is why vercel.json bundles them with the function.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app  # noqa: E402  (import after sys.path tweak)

__all__ = ['app']
