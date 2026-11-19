"""matplotlib charts, returned as PNG bytes so Flask can serve them directly."""
import io

import matplotlib

matplotlib.use("Agg")  # no display needed on a web server
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import cm  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402

BLUE = "#0b5cad"
GREEN = "#1fa64a"


def _to_png(fig):
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return buf.getvalue()


def _empty(title):
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.text(0.5, 0.5, "No appointments yet", ha="center", va="center", fontsize=13, color="#666")
    ax.set_title(title)
    ax.axis("off")
    return _to_png(fig)


def department_load_chart(dept_df):
    title = "Department load"
    if dept_df.empty:
        return _empty(title)
    data = dept_df.sort_values("appointments")
    fig, ax = plt.subplots(figsize=(7, 3.8))
    bars = ax.barh(data["department"], data["appointments"], color=BLUE)
    ax.bar_label(bars, padding=3, fontsize=9)
    ax.set_xlabel("Booked appointments")
    ax.set_title(title)
    ax.spines[["top", "right"]].set_visible(False)
    ax.margins(x=0.12)
    return _to_png(fig)


def daily_chart(daily):
    title = "Daily appointments"
    if daily.empty:
        return _empty(title)
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(daily.index, daily.values, marker="o", markersize=3, color=BLUE, linewidth=1.8)
    ax.fill_between(daily.index, daily.values, color=BLUE, alpha=0.08)
    ax.set_ylabel("Appointments")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.autofmt_xdate()
    return _to_png(fig)


def hourly_heat_chart(hours):
    """Bar per hour, coloured from pale to dark by how busy the hour is."""
    title = "Appointments by hour"
    if hours.empty:
        return _empty(title)
    norm = Normalize(vmin=0, vmax=max(hours.max(), 1))
    cmap = matplotlib.colormaps["YlOrRd"]
    labels = [f"{h:02d}:00-{h + 1:02d}:00" for h in hours.index]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    bars = ax.bar(labels, hours.values, color=[cmap(norm(v)) for v in hours.values], edgecolor="#999")
    ax.bar_label(bars, padding=2, fontsize=9)
    fig.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, label="Load")
    ax.set_ylabel("Appointments")
    ax.set_title(title)
    ax.spines[["top", "right"]].set_visible(False)
    return _to_png(fig)


def weekday_chart(weekdays_df):
    title = "Average appointments per weekday"
    if weekdays_df.empty:
        return _empty(title)
    fig, ax = plt.subplots(figsize=(7, 3.5))
    bars = ax.bar(weekdays_df["weekday"].astype(str).str[:3], weekdays_df["average_per_day"], color=GREEN)
    ax.bar_label(bars, padding=2, fontsize=9)
    ax.set_ylabel("Average per OPD day")
    ax.set_title(title)
    ax.spines[["top", "right"]].set_visible(False)
    return _to_png(fig)
