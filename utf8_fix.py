"""
utf8_fix.py
===========
Forces stdout and stderr to UTF-8 encoding on Windows.

Windows uses cp1252 (charmap) by default, which cannot encode emoji or
Unicode box-drawing characters used in print() calls throughout this project.

Import this module at the very top of any file that uses print() with emoji:
    import utf8_fix  # noqa: F401
"""
import sys
try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
