"""python -m dashboard [--no-serve] [--port 8000] [--out DIR] [--open]"""

import argparse
import sys

from .build import DEFAULT_SITE, build
from .serve import serve


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m dashboard", description="Build the offline dashboard and serve it on localhost.")
    ap.add_argument("--no-serve", action="store_true", help="only build the static site")
    ap.add_argument("--port", type=int, default=8000, help="port for the local server (default 8000)")
    ap.add_argument("--out", default=str(DEFAULT_SITE), help="output directory (default dashboard/site)")
    ap.add_argument("--portfolio", default=None, help="portfolio.json to read (default reports/final/portfolio.json)")
    ap.add_argument("--open", action="store_true", help="open the page in the default browser")
    a = ap.parse_args(argv)
    try:
        build(a.out, portfolio_path=a.portfolio)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not a.no_serve:
        serve(a.out, a.port, a.open)
    return 0


if __name__ == "__main__":
    sys.exit(main())
