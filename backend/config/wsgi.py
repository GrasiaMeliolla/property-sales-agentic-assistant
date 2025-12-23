"""WSGI config for PropLens project."""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

print("WSGI: Loading Django application...", file=sys.stderr, flush=True)

try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
    print("WSGI: Django application loaded successfully", file=sys.stderr, flush=True)
except Exception as e:
    print(f"WSGI: Failed to load Django application: {e}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc()
    raise
