"""Command line entry points.

Run with, for example:

    python -m app.cli seed
"""

import argparse
import logging
import sys

from app.database import SessionLocal
from app.services.seed import seed_thematic_areas

logger = logging.getLogger(__name__)


def seed() -> int:
    """Seed shared reference data. Safe to run repeatedly."""
    with SessionLocal() as db:
        areas = seed_thematic_areas(db)

    logger.info("Seeded %d thematic streams", len(areas))
    for area in areas:
        logger.info("  %-20s %s", area.code, area.name)

    return 0


COMMANDS = {"seed": seed}


def main(argv: list[str] | None = None) -> int:
    """Dispatch a command."""
    parser = argparse.ArgumentParser(prog="app.cli", description="EPIRO maintenance commands")
    parser.add_argument("command", choices=sorted(COMMANDS), help="the command to run")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return COMMANDS[args.command]()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
