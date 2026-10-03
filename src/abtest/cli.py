"""Command-line entry point: `abtest run --config config/experiment.yaml`."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from abtest import __version__
from abtest.config import ConfigError, load_config
from abtest.data import DataValidationError
from abtest.pipeline import run_analysis
from abtest.report import write_reports

logger = logging.getLogger("abtest")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abtest", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the full analysis and write reports.")
    run.add_argument("--config", type=Path, default=Path("config/experiment.yaml"))
    run.add_argument("--data", type=Path, help="Override the data path from the config.")
    run.add_argument("--output-dir", type=Path, help="Override the output directory.")
    run.add_argument("-v", "--verbose", action="store_true", help="Debug-level logging.")
    return parser


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # matplotlib is chatty at debug level and none of it is useful here
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_logging(args.verbose)

    try:
        config = load_config(args.config)
        if args.data:
            config = replace(config, data_path=args.data)
        if args.output_dir:
            config = replace(config, output_dir=args.output_dir)

        results = run_analysis(config)
        paths = write_reports(results)
    except (ConfigError, DataValidationError, FileNotFoundError) as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Reports written to %s", ", ".join(p.as_posix() for p in paths.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
