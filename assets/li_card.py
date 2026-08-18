"""Render the LinkedIn stats card for local-market-scanner.

Usage: python assets/li_card.py <output.png>
Runs headless in CI (GitHub Actions) via the Agg backend.
"""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "local-market-scanner-card.png"

fig = plt.figure(figsize=(12.8, 6.7), dpi=150)
fig.patch.set_facecolor("#0d1117")
ax = fig.add_axes([0, 0, 1, 1])
ax.axis("off")
ax.set_xlim(0, 12.8)
ax.set_ylim(0, 6.7)

ax.text(0.7, 5.75, "local-market-scanner", color="#58a6ff", fontsize=30,
        fontweight="bold", family="monospace")
ax.text(0.7, 5.15, "Open-source lead discovery engine for local healthcare businesses",
        color="#c9d1d9", fontsize=15)
ax.text(0.7, 4.75, "OpenStreetMap data  \u2192  scoring pipeline  \u2192  SQLite / Parquet / PostgreSQL",
        color="#8b949e", fontsize=12.5, family="monospace")

stats = [("989", "businesses scanned\n(live cloud run)"),
         ("785", "qualified leads\nidentified"),
         ("179", "automated tests\nCI green 5/5"),
         ("8", "CLI commands\nend-to-end")]
x = 0.7
for num, label in stats:
    box = FancyBboxPatch((x, 1.9), 2.7, 2.1, boxstyle="round,pad=0.12",
                         fc="#161b22", ec="#30363d", lw=1.5)
    ax.add_patch(box)
    ax.text(x + 1.35, 3.35, num, color="#3fb950", fontsize=32, fontweight="bold", ha="center")
    ax.text(x + 1.35, 2.45, label, color="#c9d1d9", fontsize=11.5, ha="center", va="center")
    x += 3.0

ax.text(0.7, 1.1, "Python \u00b7 OSM Overpass API \u00b7 pandas \u00b7 pytest \u00b7 GitHub Actions CI",
        color="#8b949e", fontsize=12)
ax.text(0.7, 0.55, "github.com/umutseve4/local-market-scanner   \u00b7   v0.3.0",
        color="#58a6ff", fontsize=13, family="monospace")

fig.savefig(OUT, facecolor=fig.get_facecolor())
print(f"PASS: wrote {OUT}")
