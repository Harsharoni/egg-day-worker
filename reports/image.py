import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from processors.gains import compute_gains


def _rank_arrow(start: int, end: int) -> str:
    if end < start:
        return f"{start} ↗ {end}"
    if end > start:
        return f"{start} ↘ {end}"
    return f"{start} → {end}"


def _mer_arrow(start: float, end: float) -> str:
    if end > start:
        return f"{start} ↗ {end}"
    if end < start:
        return f"{start} ↘ {end}"
    return f"{start} → {end}"


def _format_se(raw: float) -> str:
    if raw >= 1e21:
        return f"{raw / 1e21:.2f}s"
    return f"{int(raw / 1e18)}Q"


def generate_gains_image(hours: int = 1, limit: int | None = None) -> str | None:
    gains = compute_gains(hours=hours, limit=limit)
    if gains.empty:
        print("[report] no gains data — skipping image")
        return None

    end_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=hours)
    start_ts = start_time.strftime("%Y-%m-%d %H:%M")
    end_ts = end_time.strftime("%Y-%m-%d %H:%M")

    display = pd.DataFrame({
        "#":            range(1, len(gains) + 1),
        "Name":         gains["discord_name"],
        "Farmed":       gains["se_gain"].apply(_format_se),
        "Leaderboard":  gains.apply(lambda r: _rank_arrow(int(r["rank_start"]), int(r["rank_end"])), axis=1),
        start_ts:       gains["se_start"].apply(_format_se),
        end_ts:         gains["se_end"].apply(_format_se),
        "MER":          gains.apply(lambda r: _mer_arrow(r["mer_start"], r["mer_end"]), axis=1),
    })

    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, max(4, len(display) * 0.35 + 1)))
    fig.patch.set_visible(False)
    ax.axis("off")

    table = ax.table(
        cellText=display.values,
        colLabels=display.columns,
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.3, 2)

    cell_dict = table.get_celld()
    for i, col in enumerate(display.columns):
        max_len = max(display[col].astype(str).map(len).max(), len(col))
        for j in range(len(display) + 1):
            cell_dict[j, i].set_width(0.08 + 0.01 * max_len)

    for (i, j), cell in cell_dict.items():
        cell.set_edgecolor("black")
        if i == 0:
            cell.set_text_props(weight="bold", color="white")
            cell.set_facecolor("#F28A02")
        else:
            cell.set_facecolor("#F9EBC8" if i % 2 == 0 else "#FFF4EB")

    os.makedirs("gains", exist_ok=True)
    path = f"gains/se_gains_{start_ts}_to_{end_ts}.png"
    plt.savefig(path, bbox_inches="tight", dpi=90)
    plt.close(fig)
    print(f"[report] saved {path}")
    return path
