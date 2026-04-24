import sys
import os

# Make the project root importable so `from app import app` works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: F401  — Vercel looks for `app` in this file
