"""Block until the database accepts queries (a started container is not yet ready)."""

import os
import sys
import time

from sqlalchemy import text

from app import create_app
from app.extensions import db


def main():
    attempts = int(os.environ.get("DB_WAIT_ATTEMPTS", "30"))
    delay = float(os.environ.get("DB_WAIT_SECONDS", "2"))
    app = create_app()
    for attempt in range(1, attempts + 1):
        try:
            with app.app_context():
                db.session.execute(text("SELECT 1"))
        except Exception as error:  # noqa: BLE001 - any failure means "not yet"
            # Only the error type is printed: messages can contain connection details.
            print(
                "waiting for database (%d/%d): %s"
                % (attempt, attempts, type(error).__name__),
                flush=True,
            )
            time.sleep(delay)
        else:
            print("database is ready", flush=True)
            return 0
    print("database did not become ready in time", file=sys.stderr, flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
