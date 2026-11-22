"""Entry point for Gunicorn (``run:app``), the Flask CLI (``flask --app run``)
and local development (``python run.py``)."""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
    )
