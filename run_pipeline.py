#!/usr/bin/env python3
"""Run the BillReady Phase 1 pipeline."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="BillReady wound care billing triage pipeline")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip reading from SQLite cache (still writes fresh data)",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear cached API responses before running",
    )
    parser.add_argument(
        "--llm-verify",
        action="store_true",
        help="Run LLM suggestions on Needs Review cases (requires OPENAI_API_KEY)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    from billready.pipeline import run_pipeline

    asyncio.run(
        run_pipeline(
            use_cache=not args.no_cache,
            clear_cache=args.clear_cache,
            llm_verify=args.llm_verify,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
