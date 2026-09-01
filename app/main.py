import os
import sys

from app.api import create_app

try:
    app = create_app()

    # Get port from environment
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting server on port {port}")

except (ValueError, TypeError, KeyError, ImportError, AttributeError, OSError) as e:
    print(f"Error starting server: {e}")
    sys.exit(1)
