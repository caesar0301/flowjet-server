"""CLI entry: run uvicorn."""

from __future__ import annotations

import uvicorn

from flowjet_server.config import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "flowjet_server.http.app:app",
        host=settings.host,
        port=settings.port,
        factory=False,
        reload=False,
    )


if __name__ == "__main__":
    main()
