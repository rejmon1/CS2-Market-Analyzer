"""
Punkt wejścia serwisu ingestion.
Uruchamia asynchroniczną pętlę schedulera pobierającą ceny z rynków CS2.
"""

import asyncio

from shared.logger import get_logger

logger = get_logger("ingestion")


def main() -> None:
    from scheduler import run

    logger.info("Ingestion service starting (decoupled market polling)")
    asyncio.run(run())


if __name__ == "__main__":
    main()
