# Dashboard screenshots

No screenshots are committed here: Playwright is not installed in this project, and a screenshot is only worth
keeping if it comes from the real, running dashboard.

To take them:

1. `python -m dashboard` (builds `dashboard/site/` and serves it at http://localhost:8000).
2. Open each page in a browser at a laptop-size window (about 1366 x 768) and save a screenshot:
   `index.html` (Overview), `positions.html` (one card, for example `#card-2330_TW`), `compare.html`,
   `frontier.html`, `whatif.html`, `method.html`.
3. Save the images in this folder as `overview.png`, `positions.png`, `compare.png`, `frontier.png`,
   `whatif.png`, `method.png`.

To print a position card to PDF, click "Print this card" on the Positions page and choose "Save as PDF".
