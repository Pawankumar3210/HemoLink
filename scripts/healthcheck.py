"""Container HEALTHCHECK: exit 0 only when the app and database are ready."""

import os
import sys
import urllib.request


def main():
    url = "http://127.0.0.1:%s/health/ready" % os.environ.get("PORT", "8000")
    try:
        with urllib.request.urlopen(url, timeout=4) as response:  # noqa: S310
            return 0 if response.status == 200 else 1
    except Exception:  # noqa: BLE001
        return 1


if __name__ == "__main__":
    sys.exit(main())
