"""
Entry point. Loads config and starts Uvicorn.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import uvicorn

from api.router import create_app
from config.settings import get_settings


def main() -> None:
    settings = get_settings()
    app = create_app(settings)

    uvicorn.run(
        app,
        host=settings.listen_host,
        port=settings.listen_port,
        # TLS is terminated at the nginx reverse proxy in production.
        # To run with TLS directly (e.g. dev), add:
        #   ssl_certfile="certs/fullchain.pem",
        #   ssl_keyfile="certs/privkey.pem",
        log_config=None,  # We configure logging ourselves
        access_log=False,  # Avoid logging request details (PII)
        server_header=False,  # Don't leak server version
    )


if __name__ == "__main__":
    main()
