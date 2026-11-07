"""Build the HTML report from reports/research/results.json.

    python -m research.html_report

Writes reports/research/expected_returns.html (self-contained: data inline,
charts drawn in the browser).
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).resolve().parent / "report_template.html"
RESULTS = ROOT / "reports" / "research" / "results.json"
OUT = ROOT / "reports" / "research" / "expected_returns.html"


def main():
    data = json.loads(RESULTS.read_text())
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", blob)
    OUT.write_text(html)
    print(f"wrote {OUT} ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
