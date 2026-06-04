"""Run the admin Mini App backend:

    uv run python -m presentations.http_api

Set host/port via env or use uvicorn CLI directly for prod tuning.
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    uvicorn.run("presentations.http_api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
