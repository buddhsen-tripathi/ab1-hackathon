#!/usr/bin/env python3
"""Start the BillReady FastAPI backend."""

import uvicorn


def main() -> None:
    uvicorn.run(
        "billready.api.server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
