"""Generate the social-media promo card for local-market-scanner.

Run in CI (see .github/workflows/promo-image.yml). Output:
docs/assets/promo_social.png (1280x670, GitHub-dark themed stat card).
"""

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = pathlib.Path("docs/assets/promo_social.png")
OUT.parent.mkdir(parents=True, exist_ok=True)

fig = plt.figure(figsize=(12.8, 6.7), dpi=100)
fig.patch.set_facecolor("#0d1117")
ax = fig.add_axes([0, 0, 1, 1])
ax.axis("off")
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)

ax.add_patch(FancyBboxPatch((3, 88), 4, 8, boxstyle="round,pad=0.2", fc="#2ea043", ec="none"))
ax.text(9, 92, "local-market-scanner", color="#e6edf3", fontsize=30, fontweight="bold", va="center")
ax.text(
    9, 84,
    "Find local businesses with weak digital presence — turn OpenStreetMap into a lead list",
    color="#8b949e", fontsize=14.5, va="center",
)

stats = [
    ("989", "businesses scanned\n(Bursa, health sector)"),
    ("785", "qualified leads\nscored & exported"),
    ("179", "automated tests\nCI green 5/5"),
    ("8", "CLI commands\nSQLite · Parquet · PostgreSQL"),
]
for i, (num, label) in enumerate(stats):
    x = 5 + i * 23.5
    ax.add_patch(
        FancyBboxPatch((x, 38), 20.5, 34, boxstyle="round,pad=1.2", fc="#161b22", ec="#30363d", lw=1.5)
    )
    ax.text(x + 10.2, 62, num, color="#2ea043", fontsize=34, fontweight="bold", ha="center", va="center")
    ax.text(x + 10.2, 47, label, color="#c9d1d9", fontsize=11.5, ha="center", va="center")

ax.text(
    5, 26,
    "Pipeline:  OpenStreetMap  →  scoring engine  →  data layer (SQLite / Parquet / PostgreSQL)  →  ranked leads",
    color="#8b949e", fontsize=13,
)
ax.text(5, 18, "Python · pytest · GitHub Actions CI · open source (v0.3.0)", color="#58a6ff", fontsize=13)
ax.text(5, 8, "github.com/umutseve4/local-market-scanner", color="#e6edf3", fontsize=16, fontweight="bold")
ax.text(95, 8, "@umutseve4", color="#8b949e", fontsize=13, ha="right")

fig.savefig(OUT, dpi=100)
print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
