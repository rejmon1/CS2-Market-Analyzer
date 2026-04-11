"""
Punkt wejścia serwisu ingestion.
Uruchamia asynchroniczną pętlę schedulera pobierającą ceny z rynków CS2.
"""

import asyncio

import config

from shared.logger import get_logger

logger = get_logger("ingestion")


def main() -> None:
    from scheduler import run

    poll_interval = config.get_poll_interval()
    logger.info("Ingestion service starting (poll_interval=%ds)", poll_interval)
    asyncio.run(run(poll_interval))


if __name__ == "__main__":
    main()
