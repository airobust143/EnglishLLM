#!/usr/bin/env python3
"""Compatibility entry point for the voice assistant API."""

from mainv import PORT, app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=PORT,
    )
